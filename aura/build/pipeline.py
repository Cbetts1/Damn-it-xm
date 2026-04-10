# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Build — Pipeline
=====================
The build pipeline stages a component artefact, signs it, and gates
deployment behind the ROOT :class:`~aura.root.approval.ApprovalGate`.

Stages
------
1. **prepare**  — validate inputs and create the artefact directory
2. **build**    — write artefact manifest to disk
3. **sign**     — HMAC-sign the artefact content hash
4. **approve**  — submit to ROOT approval gate (or auto-approve in CI)
5. **deploy**   — mark artefact as deployed after gate approval

A :class:`BuildRun` is returned from :meth:`BuildPipeline.run`.  When
``auto_approve=True`` on the gate (CI mode) the entire pipeline completes
synchronously and the run status will be
:attr:`BuildStatus.DEPLOYED`.  Otherwise the run status will be
:attr:`BuildStatus.PENDING_APPROVAL` and a ROOT operator must call
``ApprovalGate.approve(run.approval_request_id)`` before the artefact
can be deployed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow
from aura.build.signer import ArtefactSigner

_logger = get_logger("aura.build.pipeline")


class BuildStatus(str, Enum):
    RUNNING          = "running"
    PENDING_APPROVAL = "pending_approval"
    DEPLOYED         = "deployed"
    FAILED           = "failed"
    REJECTED         = "rejected"


@dataclass
class Artefact:
    """A signed, staged build artefact."""

    artefact_id: str
    name: str
    version: str
    commit: str
    content_hash: str
    signature: str
    staged_path: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "artefact_id": self.artefact_id,
            "name": self.name,
            "version": self.version,
            "commit": self.commit,
            "content_hash": self.content_hash,
            "has_signature": bool(self.signature),
            "staged_path": self.staged_path,
            "created_at": self.created_at,
        }


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

    stage: str
    status: str  # "ok" | "failed"
    duration_ms: float
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }


@dataclass
class BuildRun:
    """A single pipeline execution."""

    run_id: str
    name: str
    version: str
    commit: str
    status: BuildStatus
    stages: List[dict] = field(default_factory=list)
    artefact: Optional[Artefact] = None
    approval_request_id: Optional[str] = None
    started_at: str = ""
    finished_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "version": self.version,
            "commit": self.commit,
            "status": self.status.value,
            "stages": self.stages,
            "artefact": self.artefact.to_dict() if self.artefact else None,
            "approval_request_id": self.approval_request_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


class BuildPipeline:
    """
    AURa build pipeline.

    Parameters
    ----------
    config:
        A :class:`~aura.config.BuildConfig` instance.
    approval_gate:
        An :class:`~aura.root.approval.ApprovalGate` instance owned by ROOT.
    """

    def __init__(self, config, approval_gate) -> None:
        self._config = config
        self._gate = approval_gate
        self._signer = ArtefactSigner(config.signing_secret)
        self._runs: Dict[str, BuildRun] = {}
        self._lock = threading.RLock()
        os.makedirs(config.artefact_dir, exist_ok=True)
        _logger.info("BuildPipeline initialised (artefact_dir=%s)", config.artefact_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        name: str,
        version: str = "1.0.0",
        commit: str = "HEAD",
    ) -> BuildRun:
        """
        Execute a full build pipeline for *name* at *version*/*commit*.

        Returns a :class:`BuildRun` whose ``status`` reflects the final
        outcome (DEPLOYED, PENDING_APPROVAL, or FAILED).
        """
        run_id = generate_id("build")
        build_run = BuildRun(
            run_id=run_id,
            name=name,
            version=version,
            commit=commit,
            status=BuildStatus.RUNNING,
            started_at=utcnow(),
        )
        with self._lock:
            self._runs[run_id] = build_run

        _logger.info("Build run %s started: %s v%s @ %s", run_id, name, version, commit)

        try:
            # Stage 1: prepare
            self._stage(build_run, "prepare", lambda: self._prepare(build_run))

            # Stage 2: build
            artefact = self._stage(build_run, "build", lambda: self._build(build_run))

            # Stage 3: sign
            self._stage(build_run, "sign", lambda: self._sign(artefact))

            # Stage 4: approve
            self._stage(build_run, "approve", lambda: self._approve(build_run, artefact))

            # Stage 5: deploy (only if already approved)
            if build_run.status != BuildStatus.PENDING_APPROVAL:
                self._stage(build_run, "deploy", lambda: self._deploy(build_run, artefact))

        except Exception as exc:
            build_run.status = BuildStatus.FAILED
            build_run.error = str(exc)
            _logger.error("Build run %s failed: %s", run_id, exc)

        build_run.finished_at = utcnow()
        _logger.info("Build run %s finished: %s", run_id, build_run.status.value)
        return build_run

    def list_runs(self) -> List[dict]:
        """Return all build runs as a list of dicts, newest first."""
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda r: r.started_at,
                reverse=True,
            )
            return [r.to_dict() for r in runs]

    # ------------------------------------------------------------------
    # Internal pipeline stages
    # ------------------------------------------------------------------

    def _stage(self, run: BuildRun, stage_name: str, fn):
        """Execute *fn* as a named stage, record timing and status."""
        t0 = time.monotonic()
        try:
            result = fn()
            duration_ms = (time.monotonic() - t0) * 1000
            run.stages.append(StageResult(stage_name, "ok", duration_ms).to_dict())
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            run.stages.append(
                StageResult(stage_name, "failed", duration_ms, str(exc)).to_dict()
            )
            raise

    def _prepare(self, run: BuildRun) -> None:
        """Validate inputs and ensure artefact directory exists."""
        if not run.name:
            raise ValueError("Build name must not be empty")
        os.makedirs(self._config.artefact_dir, exist_ok=True)

    def _build(self, run: BuildRun) -> Artefact:
        """Write artefact manifest and compute its content hash."""
        artefact_id = generate_id("art")
        manifest = {
            "artefact_id": artefact_id,
            "name": run.name,
            "version": run.version,
            "commit": run.commit,
            "built_at": utcnow(),
        }
        manifest_json = json.dumps(manifest, indent=2)
        content_hash = hashlib.sha256(manifest_json.encode()).hexdigest()

        staged_path = os.path.join(
            self._config.artefact_dir,
            f"{run.name}-{run.version}-{artefact_id}.json",
        )
        with open(staged_path, "w") as fh:
            fh.write(manifest_json)

        artefact = Artefact(
            artefact_id=artefact_id,
            name=run.name,
            version=run.version,
            commit=run.commit,
            content_hash=content_hash,
            signature="",
            staged_path=staged_path,
            created_at=utcnow(),
        )
        run.artefact = artefact
        return artefact

    def _sign(self, artefact: Artefact) -> None:
        """Sign the artefact with the build secret."""
        artefact.signature = self._signer.sign(artefact.artefact_id, artefact.content_hash)

    def _approve(self, run: BuildRun, artefact: Artefact) -> None:
        """Submit to the ROOT approval gate."""
        approval_req = self._gate.request(
            artefact_id=artefact.artefact_id,
            submitter="build-pipeline",
            metadata={
                "run_id": run.run_id,
                "name": run.name,
                "version": run.version,
                "commit": run.commit,
            },
        )
        run.approval_request_id = approval_req.request_id

        from aura.root.approval import ApprovalStatus
        if approval_req.status == ApprovalStatus.APPROVED:
            # Auto-approved (CI mode) — ready to deploy
            pass
        else:
            # Requires manual ROOT approval
            run.status = BuildStatus.PENDING_APPROVAL

    def _deploy(self, run: BuildRun, artefact: Artefact) -> None:
        """Mark the run as deployed."""
        run.status = BuildStatus.DEPLOYED
        _logger.info(
            "Artefact deployed: %s (%s v%s)", artefact.artefact_id, run.name, run.version
        )

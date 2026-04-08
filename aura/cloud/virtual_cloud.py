"""
AURa Virtual Cloud
==================
Simulates a distributed cloud environment that:
  • Manages virtual storage volumes
  • Manages compute node allocation
  • Caches large AI models
  • Handles data replication
  • Provides CDN-like asset delivery

In a production AURa deployment the cloud layer bridges to real infrastructure
(AWS, GCP, Azure, or on-prem Kubernetes).  Here it is a fully self-contained
virtual implementation that the AI OS can orchestrate.
"""

from __future__ import annotations

import os
import time
import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aura.config import CloudConfig
from aura.utils import get_logger, generate_id, utcnow, format_bytes, EVENT_BUS

_logger = get_logger("aura.cloud")


class NodeStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    PROVISIONING = "provisioning"


class VolumeStatus(str, Enum):
    AVAILABLE = "available"
    ATTACHED = "attached"
    CREATING = "creating"
    DELETING = "deleting"


@dataclass
class ComputeNode:
    node_id: str
    status: NodeStatus = NodeStatus.ONLINE
    vcpus: int = 8
    memory_gb: float = 32.0
    used_vcpus: int = 0
    used_memory_gb: float = 0.0
    region: str = "virtual-us-east-1"
    created_at: str = field(default_factory=utcnow)

    @property
    def cpu_utilisation(self) -> float:
        return (self.used_vcpus / self.vcpus) * 100 if self.vcpus else 0.0

    @property
    def memory_utilisation(self) -> float:
        return (self.used_memory_gb / self.memory_gb) * 100 if self.memory_gb else 0.0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "vcpus": self.vcpus,
            "used_vcpus": self.used_vcpus,
            "cpu_utilisation": round(self.cpu_utilisation, 1),
            "memory_gb": self.memory_gb,
            "used_memory_gb": round(self.used_memory_gb, 2),
            "memory_utilisation": round(self.memory_utilisation, 1),
            "region": self.region,
            "created_at": self.created_at,
        }


@dataclass
class StorageVolume:
    volume_id: str
    name: str
    size_gb: float
    status: VolumeStatus = VolumeStatus.AVAILABLE
    path: Optional[str] = None
    attached_to: Optional[str] = None
    created_at: str = field(default_factory=utcnow)

    @property
    def used_bytes(self) -> int:
        if self.path and os.path.exists(self.path):
            total = 0
            for dirpath, _, filenames in os.walk(self.path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            return total
        return 0

    def to_dict(self) -> dict:
        return {
            "volume_id": self.volume_id,
            "name": self.name,
            "size_gb": self.size_gb,
            "status": self.status.value,
            "used_bytes": self.used_bytes,
            "used_human": format_bytes(self.used_bytes),
            "attached_to": self.attached_to,
            "created_at": self.created_at,
        }


class VirtualCloud:
    """
    The AURa Virtual Cloud layer.
    Manages compute nodes, storage volumes, model cache, and replication.
    The AI OS uses this to host large AI models and distribute compute.
    """

    def __init__(self, config: CloudConfig) -> None:
        self._config = config
        self._nodes: Dict[str, ComputeNode] = {}
        self._volumes: Dict[str, StorageVolume] = {}
        self._model_registry: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._logger = get_logger("aura.cloud")
        os.makedirs(config.model_cache_dir, exist_ok=True)
        self._provision_nodes()
        self._logger.info(
            "Virtual Cloud started — %d nodes, region=%s",
            config.compute_nodes,
            config.region,
        )

    # ------------------------------------------------------------------
    # Internal bootstrap
    # ------------------------------------------------------------------

    def _provision_nodes(self) -> None:
        for i in range(self._config.compute_nodes):
            nid = generate_id(f"node-{i:02d}")
            self._nodes[nid] = ComputeNode(
                node_id=nid,
                vcpus=8,
                memory_gb=32.0,
                region=self._config.region,
            )

    # ------------------------------------------------------------------
    # Compute node operations
    # ------------------------------------------------------------------

    def list_nodes(self) -> List[dict]:
        with self._lock:
            return [n.to_dict() for n in self._nodes.values()]

    def get_node(self, node_id: str) -> Optional[dict]:
        with self._lock:
            node = self._nodes.get(node_id)
            return node.to_dict() if node else None

    def add_node(self, vcpus: int = 8, memory_gb: float = 32.0) -> dict:
        n = len(self._nodes)
        nid = generate_id(f"node-{n:02d}")
        node = ComputeNode(node_id=nid, vcpus=vcpus, memory_gb=memory_gb, region=self._config.region)
        with self._lock:
            self._nodes[nid] = node
        EVENT_BUS.publish("cloud.node.added", {"node_id": nid})
        self._logger.info("Node added: %s", nid)
        return node.to_dict()

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                EVENT_BUS.publish("cloud.node.removed", {"node_id": node_id})
                self._logger.info("Node removed: %s", node_id)
                return True
        return False

    # ------------------------------------------------------------------
    # Storage volume operations
    # ------------------------------------------------------------------

    def create_volume(self, name: str, size_gb: float) -> dict:
        vid = generate_id("vol")
        path = os.path.join(self._config.model_cache_dir, "volumes", vid)
        os.makedirs(path, exist_ok=True)
        vol = StorageVolume(volume_id=vid, name=name, size_gb=size_gb, path=path)
        with self._lock:
            self._volumes[vid] = vol
        EVENT_BUS.publish("cloud.volume.created", {"volume_id": vid, "name": name})
        self._logger.info("Volume created: %s (%s, %.1f GB)", vid, name, size_gb)
        return vol.to_dict()

    def list_volumes(self) -> List[dict]:
        with self._lock:
            return [v.to_dict() for v in self._volumes.values()]

    def delete_volume(self, volume_id: str) -> bool:
        with self._lock:
            vol = self._volumes.get(volume_id)
            if vol:
                if vol.path and os.path.exists(vol.path):
                    shutil.rmtree(vol.path, ignore_errors=True)
                del self._volumes[volume_id]
                EVENT_BUS.publish("cloud.volume.deleted", {"volume_id": volume_id})
                self._logger.info("Volume deleted: %s", volume_id)
                return True
        return False

    # ------------------------------------------------------------------
    # Model registry (large AI model storage in cloud)
    # ------------------------------------------------------------------

    def register_model(self, model_id: str, model_name: str, size_bytes: int, backend: str) -> dict:
        entry = {
            "model_id": model_id,
            "model_name": model_name,
            "size_bytes": size_bytes,
            "size_human": format_bytes(size_bytes),
            "backend": backend,
            "registered_at": utcnow(),
            "status": "available",
        }
        with self._lock:
            self._model_registry[model_id] = entry
        EVENT_BUS.publish("cloud.model.registered", entry)
        self._logger.info("Model registered in cloud: %s (%s)", model_name, format_bytes(size_bytes))
        return entry

    def list_models(self) -> List[dict]:
        with self._lock:
            return list(self._model_registry.values())

    # ------------------------------------------------------------------
    # Metrics / status
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            nodes = list(self._nodes.values())
        total_vcpus = sum(n.vcpus for n in nodes)
        used_vcpus = sum(n.used_vcpus for n in nodes)
        total_mem = sum(n.memory_gb for n in nodes)
        used_mem = sum(n.used_memory_gb for n in nodes)
        online = sum(1 for n in nodes if n.status == NodeStatus.ONLINE)
        return {
            "region": self._config.region,
            "nodes_total": len(nodes),
            "nodes_online": online,
            "vcpus_total": total_vcpus,
            "vcpus_used": used_vcpus,
            "cpu_utilisation_pct": round((used_vcpus / total_vcpus * 100) if total_vcpus else 0, 1),
            "memory_total_gb": total_mem,
            "memory_used_gb": round(used_mem, 2),
            "memory_utilisation_pct": round((used_mem / total_mem * 100) if total_mem else 0, 1),
            "volumes_total": len(self._volumes),
            "models_cached": len(self._model_registry),
            "cdn_enabled": self._config.cdn_enabled,
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
        }

# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa AI OS (AIOS)
=================
The central orchestrator and "bridge" of the AURa virtual system.

Responsibilities:
  • Bootstraps and manages all virtual components (Cloud, CPU, Server)
  • Routes queries and tasks to the AI engine
  • Exposes a unified status/metrics API consumed by the Command Center and Shell
  • Handles inter-component events via the shared EventBus
  • Enforces resource policy and health checks
  • Provides a command dispatch interface for the Shell

The AI OS is designed to be the *only physical component* — all compute,
storage, and serving is done through its managed virtual layer.
"""

from __future__ import annotations

import json
import os
import signal
import time
import threading
from typing import Any, Callable, Dict, List, Optional

from aura.config import AURaConfig
from aura.utils import get_logger, format_uptime, utcnow, EVENT_BUS
from aura.ai_engine.engine import AIEngine
from aura.cloud.virtual_cloud import VirtualCloud
from aura.cpu.virtual_cpu import VirtualCPU, TaskPriority
from aura.server.virtual_server import VirtualServer
from aura.adapters.android_bridge import detect_capabilities, AndroidBridge
from aura.persistence.store import PersistenceEngine
from aura.plugins.manager import PluginManager, SystemInfoPlugin, StoragePlugin

# New OS architecture layers
from aura.root.sovereign import ROOTLayer
from aura.hardware.device_manager import DeviceManager
from aura.hardware.vcpu import VCPUDevice
from aura.hardware.vram import VRAMDevice
from aura.hardware.vdisk import VDiskDevice
from aura.hardware.vnet import VNetDevice
from aura.hardware.vbt import VBTDevice
from aura.hardware.vgpu import VGPUDevice
from aura.network.stack import NetworkStack
from aura.compute.dispatcher import ComputeBackend
from aura.boot.bootloader import Bootloader, BootState
from aura.boot.aura_init import AURAInit
from aura.home.userland import HOMELayer
from aura.build.pipeline import BuildPipeline
from aura.identity.crypto import CryptoIdentityEngine, IdentityKind
from aura.identity.registry import IdentityRegistry
from aura.governance.audit import AuditLog

# v2.0.0 kernel services
from aura.kernel.process_manager import ProcessManager
from aura.kernel.ipc import IPCBus
from aura.kernel.syslog import SyslogService
from aura.kernel.secrets_manager import SecretsManager
from aura.kernel.cron import CronService
from aura.kernel.service_manager import ServiceManager

# v2.0.0 filesystem layer
from aura.fs.vfs import VirtualFileSystem
from aura.fs.procfs import ProcFS
from aura.fs.fhs import FHSMapper

# v2.0.0 package manager
from aura.pkg.registry import PackageRegistry
from aura.pkg.installer import PackageInstaller

# v2.0.0 web/remote layer
from aura.web.api import WebAPI
from aura.web.ws import WebSocketHub

# v2.0.0 AI engine enhancements
from aura.ai_engine.model_registry import ModelRegistry
from aura.ai_engine.personality_kernel import PersonalityKernel
from aura.ai_engine.ollama_backend import OllamaBackend
from aura.cloud.cloud_ai_router import CloudAIRouter

# v2.0.0 mirror + intelligence index + branding
from aura.command_center.mirror import MirrorService
from aura.resources.intelligence_index import IntelligenceIndex
from branding.banner import get_boot_banner

_logger = get_logger("aura.os")

# ---------------------------------------------------------------------------
# AIOS
# ---------------------------------------------------------------------------

class AIOS:
    """
    AURa AI Operating System.
    The single physical AI component that bridges all virtual infrastructure.
    """

    VERSION = "2.0.0"

    def __init__(self, config: Optional[AURaConfig] = None) -> None:
        self._config = config or AURaConfig.from_env()
        self._start_time: Optional[float] = None
        self._running = False
        self._lock = threading.Lock()
        self._logger = get_logger("aura.os")

        # Subsystems — initialised lazily in start()
        self._ai_engine: Optional[AIEngine] = None
        self._cloud: Optional[VirtualCloud] = None
        self._cpu: Optional[VirtualCPU] = None
        self._server: Optional[VirtualServer] = None

        # Platform capabilities and bridge
        self._capabilities: dict = {}
        self._bridge: Optional[AndroidBridge] = None

        # Persistence engine
        self._persistence: Optional[PersistenceEngine] = None

        # Plugin manager
        self._plugin_manager: Optional[PluginManager] = None

        # ----------------------------------------------------------------
        # New OS architecture layers
        # ----------------------------------------------------------------
        # ROOT sovereign layer
        self._root: Optional[ROOTLayer] = None
        # /dev/ device manager
        self._device_manager: Optional[DeviceManager] = None
        # Virtual hardware devices
        self._dev_vcpu: Optional[VCPUDevice] = None
        self._dev_vram: Optional[VRAMDevice] = None
        self._dev_vdisk: Optional[VDiskDevice] = None
        self._dev_vnet: Optional[VNetDevice] = None
        self._dev_vbt: Optional[VBTDevice] = None
        self._dev_vgpu: Optional[VGPUDevice] = None
        # HOME userland
        self._home: Optional[HOMELayer] = None
        # Boot chain
        self._aura_init: Optional[AURAInit] = None
        self._bootloader: Optional[Bootloader] = None
        # Build pipeline
        self._build_pipeline: Optional[BuildPipeline] = None
        # Identity & governance
        self._crypto_engine: Optional[CryptoIdentityEngine] = None
        self._identity_registry: Optional[IdentityRegistry] = None
        self._audit_log: Optional[AuditLog] = None

        # OS-level command registry — built-ins are handled in dispatch(),
        # custom commands registered via register_command() live here.
        self._commands: Dict[str, Callable] = {}

        # v2.0.0 kernel services
        self._process_manager: Optional[ProcessManager] = None
        self._ipc_bus: Optional[IPCBus] = None
        self._syslog: Optional[SyslogService] = None
        self._secrets_manager: Optional[SecretsManager] = None
        self._cron: Optional[CronService] = None
        self._service_manager: Optional[ServiceManager] = None

        # v2.0.0 filesystem layer
        self._vfs: Optional[VirtualFileSystem] = None
        self._procfs: Optional[ProcFS] = None
        self._fhs: Optional[FHSMapper] = None

        # v2.0.0 package manager
        self._pkg_registry: Optional[PackageRegistry] = None
        self._pkg_installer: Optional[PackageInstaller] = None

        # v2.0.0 web/remote layer
        self._web_api: Optional[WebAPI] = None
        self._ws_hub: Optional[WebSocketHub] = None

        # v2.0.0 AI engine enhancements
        self._model_registry: Optional[ModelRegistry] = None
        self._personality_kernel: Optional[PersonalityKernel] = None

        # Cloud AI router — routes inference through VirtualCPU/VirtualCloud
        self._cloud_ai_router: Optional[CloudAIRouter] = None

        # v2.0.0 mirror + intelligence index
        self._mirror: Optional[MirrorService] = None
        self._intelligence_index: Optional[IntelligenceIndex] = None

        # Event subscriptions
        EVENT_BUS.subscribe("*", self._on_event)

    # ------------------------------------------------------------------
    # Properties — expose subsystems (read-only after boot)
    # ------------------------------------------------------------------

    @property
    def ai_engine(self) -> AIEngine:
        assert self._ai_engine is not None, "AIOS not started"
        return self._ai_engine

    @property
    def cloud(self) -> VirtualCloud:
        assert self._cloud is not None, "AIOS not started"
        return self._cloud

    @property
    def cpu(self) -> VirtualCPU:
        assert self._cpu is not None, "AIOS not started"
        return self._cpu

    @property
    def server(self) -> VirtualServer:
        assert self._server is not None, "AIOS not started"
        return self._server

    @property
    def capabilities(self) -> dict:
        """Host platform capabilities detected at boot time."""
        return self._capabilities

    @property
    def persistence(self) -> PersistenceEngine:
        assert self._persistence is not None, "AIOS not started"
        return self._persistence

    @property
    def plugin_manager(self) -> PluginManager:
        assert self._plugin_manager is not None, "AIOS not started"
        return self._plugin_manager

    # ------------------------------------------------------------------
    # New OS architecture — properties
    # ------------------------------------------------------------------

    @property
    def root(self) -> ROOTLayer:
        assert self._root is not None, "AIOS not started"
        return self._root

    @property
    def device_manager(self) -> DeviceManager:
        assert self._device_manager is not None, "AIOS not started"
        return self._device_manager

    @property
    def dev_vcpu(self) -> VCPUDevice:
        assert self._dev_vcpu is not None, "AIOS not started"
        return self._dev_vcpu

    @property
    def dev_vram(self) -> VRAMDevice:
        assert self._dev_vram is not None, "AIOS not started"
        return self._dev_vram

    @property
    def dev_vdisk(self) -> VDiskDevice:
        assert self._dev_vdisk is not None, "AIOS not started"
        return self._dev_vdisk

    @property
    def dev_vnet(self) -> VNetDevice:
        assert self._dev_vnet is not None, "AIOS not started"
        return self._dev_vnet

    @property
    def dev_vbt(self) -> VBTDevice:
        assert self._dev_vbt is not None, "AIOS not started"
        return self._dev_vbt

    @property
    def dev_vgpu(self) -> VGPUDevice:
        assert self._dev_vgpu is not None, "AIOS not started"
        return self._dev_vgpu

    @property
    def home(self) -> HOMELayer:
        assert self._home is not None, "AIOS not started"
        return self._home

    @property
    def build_pipeline(self) -> BuildPipeline:
        assert self._build_pipeline is not None, "AIOS not started"
        return self._build_pipeline

    @property
    def identity_registry(self) -> IdentityRegistry:
        assert self._identity_registry is not None, "AIOS not started"
        return self._identity_registry

    @property
    def audit_log(self) -> AuditLog:
        assert self._audit_log is not None, "AIOS not started"
        return self._audit_log

    @property
    def bootloader(self) -> Optional[Bootloader]:
        return self._bootloader

    # v2.0.0 kernel service properties

    @property
    def process_manager(self) -> ProcessManager:
        assert self._process_manager is not None, "AIOS not started"
        return self._process_manager

    @property
    def ipc_bus(self) -> IPCBus:
        assert self._ipc_bus is not None, "AIOS not started"
        return self._ipc_bus

    @property
    def syslog(self) -> SyslogService:
        assert self._syslog is not None, "AIOS not started"
        return self._syslog

    @property
    def secrets_manager(self) -> SecretsManager:
        assert self._secrets_manager is not None, "AIOS not started"
        return self._secrets_manager

    @property
    def cron(self) -> CronService:
        assert self._cron is not None, "AIOS not started"
        return self._cron

    @property
    def service_manager(self) -> ServiceManager:
        assert self._service_manager is not None, "AIOS not started"
        return self._service_manager

    @property
    def vfs(self) -> VirtualFileSystem:
        assert self._vfs is not None, "AIOS not started"
        return self._vfs

    @property
    def procfs(self) -> ProcFS:
        assert self._procfs is not None, "AIOS not started"
        return self._procfs

    @property
    def fhs(self) -> FHSMapper:
        assert self._fhs is not None, "AIOS not started"
        return self._fhs

    @property
    def pkg_registry(self) -> PackageRegistry:
        assert self._pkg_registry is not None, "AIOS not started"
        return self._pkg_registry

    @property
    def pkg_installer(self) -> PackageInstaller:
        assert self._pkg_installer is not None, "AIOS not started"
        return self._pkg_installer

    @property
    def web_api(self) -> WebAPI:
        assert self._web_api is not None, "AIOS not started"
        return self._web_api

    @property
    def ws_hub(self) -> WebSocketHub:
        assert self._ws_hub is not None, "AIOS not started"
        return self._ws_hub

    @property
    def model_registry(self) -> ModelRegistry:
        assert self._model_registry is not None, "AIOS not started"
        return self._model_registry

    @property
    def personality_kernel(self) -> PersonalityKernel:
        assert self._personality_kernel is not None, "AIOS not started"
        return self._personality_kernel

    @property
    def mirror(self) -> MirrorService:
        assert self._mirror is not None, "AIOS not started"
        return self._mirror

    @property
    def intelligence_index(self) -> IntelligenceIndex:
        assert self._intelligence_index is not None, "AIOS not started"
        return self._intelligence_index

    @property
    def cloud_ai_router(self) -> CloudAIRouter:
        assert self._cloud_ai_router is not None, "AIOS not started"
        return self._cloud_ai_router

    # ------------------------------------------------------------------
    # Plugin registry — custom shell commands
    # ------------------------------------------------------------------

    def register_command(self, name: str, fn: Callable) -> None:
        """Register a custom shell command.

        ``fn`` receives ``(aios, args)`` where *aios* is this instance and
        *args* is a ``List[str]`` of additional tokens from the shell input.
        It must return a ``str`` that will be printed in the shell.

        Example::

            def cmd_greet(aios, args):
                return "Hello, " + (" ".join(args) or "world") + "!"

            aios.register_command("greet", cmd_greet)
        """
        self._commands[name.lower()] = fn
        self._logger.info("Custom command registered: %s", name)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _state_path(self) -> str:
        return os.path.join(self._config.data_dir, "state.json")

    def _save_state(self) -> None:
        """Persist model registry, conversation history, and task list."""
        if self._ai_engine is None and self._cloud is None and self._cpu is None:
            return
        state: dict = {}
        if self._ai_engine is not None:
            state["conversation_history"] = self._ai_engine.get_history()
        if self._cloud is not None:
            state["model_registry"] = self._cloud.list_models()
        if self._cpu is not None:
            state["tasks"] = self._cpu.list_tasks()
        state["saved_at"] = utcnow()
        try:
            os.makedirs(self._config.data_dir, exist_ok=True)
            with open(self._state_path(), "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, default=str)
            self._logger.info("State saved to %s", self._state_path())
        except OSError as exc:
            self._logger.warning("Could not save state: %s", exc)

    def _load_state(self) -> None:
        """Restore persisted state if a state file exists."""
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            if not isinstance(state, dict):
                self._logger.warning("State file %s is not a JSON object — skipping", path)
                return
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning("Could not load state from %s: %s", path, exc)
            return

        if self._ai_engine is not None:
            history = state.get("conversation_history", [])
            if history:
                self._ai_engine.load_history(history)
                self._logger.info("Restored %d history entries", len(history))

        if self._cloud is not None:
            for entry in state.get("model_registry", []):
                mid = entry.get("model_id")
                if mid and mid not in {m["model_id"] for m in self._cloud.list_models()}:
                    self._cloud.register_model(
                        model_id=mid,
                        model_name=entry.get("model_name", "unknown"),
                        size_bytes=entry.get("size_bytes", 0),
                        backend=entry.get("backend", "builtin"),
                    )
            self._logger.info("Model registry restored")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Boot the AI OS and all virtual components."""
        if self._running:
            return

        self._logger.info("=" * 60)
        self._logger.info("  AURa v%s — Booting AI OS …", self.VERSION)
        self._logger.info("  %s", get_boot_banner(self.VERSION).split("\n")[0])
        self._logger.info("=" * 60)

        # 0a. Platform detection
        self._logger.info("[0a/9] Detecting platform capabilities…")
        self._capabilities = detect_capabilities()
        self._bridge = AndroidBridge(capabilities=self._capabilities)
        self._logger.info(
            "  Platform: %s  Termux: %s  CPUs: %s",
            self._capabilities.get("platform"),
            self._capabilities.get("is_termux"),
            self._capabilities.get("cpu_count"),
        )

        # 0b. Persistence + Plugin init
        self._logger.info("[0b/9] Initialising persistence engine…")
        db_path = os.path.join(self._config.data_dir, "aura.db")
        self._persistence = PersistenceEngine(db_path)

        self._logger.info("[0c/9] Loading plugin manager…")
        self._plugin_manager = PluginManager(aios=self)
        self._plugin_manager.register(SystemInfoPlugin())
        self._plugin_manager.register(StoragePlugin())

        # ----------------------------------------------------------------
        # NEW: Identity, governance, ROOT, /dev/*, HOME, build
        # ----------------------------------------------------------------

        # 0d. Governance audit log (subscribes to EventBus before ROOT starts)
        self._logger.info("[0d/9] Initialising audit log…")
        self._audit_log = AuditLog(
            max_entries=self._config.root.audit_log_max_entries,
            data_dir=self._config.data_dir,
        )

        # 0e. Cryptographic identity
        self._logger.info("[0e/9] Initialising cryptographic identity…")
        self._crypto_engine = CryptoIdentityEngine(self._config.root.root_secret)
        self._identity_registry = IdentityRegistry(self._crypto_engine)
        # Issue ROOT identity token
        self._identity_registry.issue(
            IdentityKind.NODE,
            subject="root",
            metadata={"role": "sovereign", "version": self.VERSION},
        )

        # 0f. v2.0.0 Kernel services
        self._logger.info("[0f/9] Starting kernel services…")
        self._process_manager = ProcessManager()
        self._ipc_bus = IPCBus()
        self._syslog = SyslogService()
        self._secrets_manager = SecretsManager()
        self._cron = CronService()
        self._service_manager = ServiceManager()
        self._cron.start()
        self._syslog.info("aura.kernel", "Kernel services started")

        # 0g. v2.0.0 Filesystem layer
        self._logger.info("[0g/9] Mounting virtual filesystem layers…")
        self._vfs = VirtualFileSystem()
        self._procfs = ProcFS()
        self._fhs = FHSMapper()
        # Register procfs provider for uptime
        self._procfs.register_provider("/proc/aura/version", lambda: self.VERSION)

        # 0h. v2.0.0 Package manager
        self._logger.info("[0h/9] Initialising package manager…")
        self._pkg_registry = PackageRegistry()
        self._pkg_installer = PackageInstaller(self._pkg_registry)

        # 0i. v2.0.0 Web/remote layer
        self._logger.info("[0i/9] Initialising web/remote layer…")
        self._web_api = WebAPI(
            auth_enabled=self._config.web.auth_enabled,
            api_token=self._config.web.api_token,
        )
        self._ws_hub = WebSocketHub()

        # 0j. v2.0.0 AI Engine enhancements
        self._logger.info("[0j/9] Initialising AI engine enhancements…")
        self._model_registry = ModelRegistry()
        self._personality_kernel = PersonalityKernel()

        # 0k. v2.0.0 Mirror + Intelligence Index
        self._logger.info("[0k/9] Initialising mirror service and intelligence index…")
        self._mirror = MirrorService()
        self._intelligence_index = IntelligenceIndex()

        # 1. ROOT sovereign layer
        self._logger.info("[1/9] Bringing ROOT sovereign layer online…")
        self._root = ROOTLayer(self._config)
        self._root.start()

        # 2. AI Engine (the brain — the only "physical" AI component)
        self._logger.info("[2/9] Initialising AI Engine (%s)…", self._config.ai_engine.backend)
        self._ai_engine = AIEngine(self._config.ai_engine)

        # 3. Virtual Cloud (large model storage + distributed compute)
        self._logger.info("[3/9] Provisioning Virtual Cloud (%d nodes)…", self._config.cloud.compute_nodes)
        self._cloud = VirtualCloud(self._config.cloud)

        # 4. Virtual CPU (task scheduler)
        self._logger.info("[4/9] Starting Virtual CPU (%d vCores)…", self._config.cpu.virtual_cores)
        self._cpu = VirtualCPU(self._config.cpu)
        self._cpu.start()

        # 5. Virtual Server (HTTP API + dashboard)
        self._logger.info("[5/9] Starting Virtual Server (port %d)…", self._config.server.port)
        self._server = VirtualServer(self._config.server)
        self._server.start(self)

        # 6. Virtual hardware /dev/* devices
        self._logger.info("[6/9] Claiming /dev/* virtual hardware devices…")
        self._dev_vcpu = VCPUDevice(self._cpu)
        self._dev_vram = VRAMDevice(total_mb=32_768.0)
        vdisk_dir = os.path.join(self._config.data_dir, "vdisk")
        self._dev_vdisk = VDiskDevice(vdisk_dir)
        net_stack = NetworkStack(self._config.network)
        self._dev_vnet = net_stack  # VNetDevice is the NetworkStack
        self._dev_vbt = VBTDevice()
        self._dev_vgpu = VGPUDevice(
            vcpu=self._dev_vcpu,
            cloud=self._cloud,
            spill_threshold_pct=self._config.compute.local_cpu_spill_threshold_pct,
            default_backend=self._config.compute.default_backend,
        )

        # Register all devices with the device manager
        self._device_manager = DeviceManager(root=self._root)
        self._root.bind_device_manager(self._device_manager)
        self._device_manager.register("/dev/vcpu",  "vcpu",  self._dev_vcpu,  "root")
        self._device_manager.register("/dev/vram",  "vram",  self._dev_vram,  "root")
        self._device_manager.register("/dev/vdisk", "vdisk", self._dev_vdisk, "root")
        self._device_manager.register("/dev/vnet",  "vnet",  self._dev_vnet,  "root")
        self._device_manager.register("/dev/vbt",   "vbt",   self._dev_vbt,   "root")
        self._device_manager.register("/dev/vgpu",  "vgpu",  self._dev_vgpu,  "root")

        # 7. HOME userland
        self._logger.info("[7/9] Mounting HOME userland…")
        self._home = HOMELayer(self._config.home)
        self._home.start()
        self._root.mount_home(self._home)

        # 8. Build pipeline
        self._logger.info("[8/9] Initialising build pipeline…")
        self._build_pipeline = BuildPipeline(
            config=self._config.build,
            approval_gate=self._root.approval_gate,
        )

        # ----------------------------------------------------------------
        # aura-init — service manager (PID-1 equivalent)
        # ----------------------------------------------------------------
        self._aura_init = AURAInit()
        # Register core services with aura-init
        self._aura_init.register(
            "virtual-cpu",
            start_fn=lambda: None,   # already started above
            stop_fn=lambda: self._cpu.stop() if self._cpu else None,
            restart_on_failure=False,
        )
        self._aura_init.register(
            "virtual-server",
            start_fn=lambda: None,   # already started above
            stop_fn=lambda: self._server.stop() if self._server else None,
            restart_on_failure=False,
        )
        self._aura_init.register(
            "build-pipeline",
            start_fn=lambda: None,   # stateless, always ready
            restart_on_failure=False,
        )
        # v2.0.0 services
        self._aura_init.register(
            "kernel-cron",
            start_fn=lambda: None,   # already started above
            stop_fn=lambda: self._cron.stop() if self._cron else None,
            restart_on_failure=False,
        )

        # 9. Register services with v2.0.0 service manager
        self._logger.info("[9/9] Registering services…")
        self._service_manager.register(
            "virtual-cpu",
            start_fn=lambda: None,
            stop_fn=lambda: self._cpu.stop() if self._cpu else None,
        )
        self._service_manager.register(
            "kernel-cron",
            start_fn=lambda: None,
            stop_fn=lambda: self._cron.stop() if self._cron else None,
        )
        self._service_manager.register(
            "web-api",
            start_fn=lambda: None,
        )

        # Register the AI model in the cloud registry
        self._cloud.register_model(
            model_id="aura-engine-001",
            model_name=self._config.ai_engine.model_name,
            size_bytes=350_000_000,  # approximate
            backend=self._config.ai_engine.backend,
        )

        # Cloud AI Router — routes inference through VirtualCPU/VirtualCloud so
        # model weights never load into the device's main Python process.
        self._logger.info(
            "[+] Wiring Cloud AI Router (model=%s, url=%s)…",
            self._config.ollama.model,
            self._config.ollama.base_url,
        )
        _ollama_backend = OllamaBackend(self._config.ollama)
        self._cloud_ai_router = CloudAIRouter(
            virtual_cpu=self._cpu,
            virtual_cloud=self._cloud,
            backend=_ollama_backend,
            ollama_config=self._config.ollama,
        )

        # Restore persisted state (history, extra models)
        self._load_state()

        self._start_time = time.monotonic()
        self._running = True

        self._logger.info("=" * 60)
        self._logger.info("  AURa AI OS v%s is ONLINE", self.VERSION)
        self._logger.info("  Dashboard : http://localhost:%d/dashboard", self._config.server.port)
        self._logger.info("  API       : http://localhost:%d/api/v1/", self._config.server.port)
        self._logger.info("  ROOT      : online (policy=deny-by-default)")
        self._logger.info("  HOME      : mounted (%s)", self._config.home.home_dir)
        self._logger.info("  /dev/*    : 6 devices registered")
        self._logger.info("  Kernel    : process_manager, ipc, syslog, secrets, cron, services")
        self._logger.info("  FS        : vfs, procfs, fhs")
        self._logger.info("  Pkg       : registry + installer")
        self._logger.info("  Web       : api + websocket hub")
        self._logger.info(
            "  Cloud AI  : %s @ %s (router=%s)",
            self._config.ollama.model,
            self._config.ollama.base_url,
            "enabled" if self._config.ollama.use_cloud_router else "disabled",
        )
        self._logger.info("=" * 60)

        EVENT_BUS.publish("aios.started", {"version": self.VERSION})

    def stop(self) -> None:
        """Gracefully shut down all virtual components."""
        if not self._running:
            return
        self._logger.info("AURa AI OS shutting down…")
        # Persist state before tearing down subsystems
        self._save_state()
        # Stop v2.0.0 kernel services
        if self._cron:
            self._cron.stop()
        # Flush audit log
        if self._audit_log:
            self._audit_log.flush_to_disk()
        if self._server:
            self._server.stop()
        if self._cloud_ai_router:
            self._cloud_ai_router.shutdown()
        if self._cpu:
            self._cpu.stop()
        # Unmount HOME and stop ROOT
        if self._root:
            if self._root.home_mounted:
                self._root.unmount_home()
            self._root.stop()
        if self._persistence:
            self._persistence.close()
        self._running = False
        EVENT_BUS.publish("aios.stopped", {})
        self._logger.info("AURa AI OS stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # Status & Metrics
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """High-level system status snapshot."""
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "system": "AURa",
            "version": self.VERSION,
            "running": self._running,
            "uptime_seconds": round(uptime, 1),
            "uptime_human": format_uptime(uptime),
            "timestamp": utcnow(),
            "components": {
                "ai_os": "online" if self._running else "offline",
                "ai_engine": "ready" if (self._ai_engine and self._ai_engine.is_ready()) else "not_ready",
                "virtual_cloud": "online" if self._cloud else "offline",
                "virtual_cpu": "running" if (self._cpu and self._cpu._running) else "stopped",
                "virtual_server": "running" if (self._server and self._server._thread and self._server._thread.is_alive()) else "stopped",
                "root": "online" if (self._root and self._root.running) else "offline",
                "home": "mounted" if (self._home and self._home.running) else "offline",
                "dev_vnet": "online" if self._dev_vnet else "offline",
                "dev_vgpu": "online" if self._dev_vgpu else "offline",
            },
        }

    def metrics(self) -> dict:
        """Detailed metrics for all components (consumed by the Command Center)."""
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "version": self.VERSION,
            "uptime_seconds": round(uptime, 1),
            "ai_backend": self._ai_engine.backend_name if self._ai_engine else "none",
            "model_name": self._ai_engine.model_name if self._ai_engine else "none",
            "cloud": self._cloud.metrics() if self._cloud else {},
            "cpu": self._cpu.metrics() if self._cpu else {},
            "server": self._server.metrics() if self._server else {},
            "root": self._root.status() if self._root else {},
            "home": self._home.status() if self._home else {},
            "vram": self._dev_vram.metrics() if self._dev_vram else {},
            "vdisk": self._dev_vdisk.metrics() if self._dev_vdisk else {},
            "vnet": self._dev_vnet.metrics() if self._dev_vnet else {},
            "vgpu": self._dev_vgpu.metrics() if self._dev_vgpu else {},
            "identity": self._identity_registry.metrics() if self._identity_registry else {},
            "audit": self._audit_log.metrics() if self._audit_log else {},
            # v2.0.0 new subsystems
            "kernel": {
                "processes": self._process_manager.metrics() if self._process_manager else {},
                "syslog": self._syslog.metrics() if self._syslog else {},
                "cron_jobs": len(self._cron.list_jobs()) if self._cron else 0,
                "services": self._service_manager.metrics() if self._service_manager else {},
            },
            "fs": {
                "vfs_mounts": len(self._vfs._mounts) if self._vfs else 0,
                "procfs_entries": len(self._procfs.list_entries()) if self._procfs else 0,
                "fhs_mappings": len(self._fhs.list_mappings()) if self._fhs else 0,
            },
            "pkg": {
                "registry_count": self._pkg_registry.count() if self._pkg_registry else 0,
                "installed_count": len(self._pkg_installer.list_installed()) if self._pkg_installer else 0,
            },
            "model_registry": {
                "count": self._model_registry.count() if self._model_registry else 0,
            },
            "intelligence_index": {
                "count": len(self._intelligence_index.list_entries()) if self._intelligence_index else 0,
            },
            "mirror": {
                "count": len(self._mirror.list_mirrors()) if self._mirror else 0,
            },
            "cloud_ai_router": self._cloud_ai_router.metrics() if self._cloud_ai_router else {},
            "timestamp": utcnow(),
        }

    # ------------------------------------------------------------------
    # Command dispatch (used by the Shell)
    # ------------------------------------------------------------------

    def dispatch(self, command: str, args: Optional[List[str]] = None) -> str:
        """
        Dispatch a shell command to the AI OS.
        Returns a string response to display in the shell.
        """
        args = args or []
        cmd = command.strip().lower()

        # Handle !<command> shorthand — treat as "bash <command> [args]"
        if cmd.startswith("!") and cmd != "!":
            shell_cmd_parts = [cmd[1:]] + args
            return self.dispatch("bash", shell_cmd_parts)

        if cmd == "status":
            s = self.status()
            lines = [f"AURa v{s['version']}  |  Uptime: {s['uptime_human']}"]
            for comp, state in s["components"].items():
                icon = "✅" if "online" in state or "ready" in state or "running" in state else "⚠️ "
                lines.append(f"  {icon}  {comp:<20} {state}")
            return "\n".join(lines)

        elif cmd == "metrics":
            m = self.metrics()
            cloud = m["cloud"]
            cpu = m["cpu"]
            lines = [
                f"── Virtual Cloud ──────────────────────────────",
                f"  Nodes      : {cloud.get('nodes_online', '?')}/{cloud.get('nodes_total', '?')} online",
                f"  CPU        : {cloud.get('cpu_utilisation_pct', 0):.1f}%",
                f"  Memory     : {cloud.get('memory_utilisation_pct', 0):.1f}%",
                f"  Region     : {cloud.get('region', '?')}",
                f"── Virtual CPU ────────────────────────────────",
                f"  vCores     : {cpu.get('virtual_cores', '?')} @ {cpu.get('clock_speed_ghz', '?')} GHz",
                f"  Completed  : {cpu.get('tasks_completed', 0)} tasks",
                f"  Throughput : {cpu.get('throughput_tps', 0):.3f} tasks/s",
                f"  Queue depth: {cpu.get('queue_depth', 0)}",
            ]
            return "\n".join(lines)

        elif cmd == "cloud":
            return self.dispatch("metrics")  # alias

        elif cmd == "cpu":
            m = self.cpu.metrics()
            lines = [
                f"Virtual CPU — {m['architecture']}",
                f"  vCores  : {m['virtual_cores']} ({m['virtual_cores'] * m['threads_per_core']} threads)",
                f"  Clock   : {m['clock_speed_ghz']} GHz",
                f"  L3 Cache: {m['l3_cache_mb']} MB",
                f"  Workers active: {m['workers_active']}",
                f"  Queue depth   : {m['queue_depth']}",
                f"  Tasks done    : {m['tasks_completed']}",
                f"  Tasks failed  : {m['tasks_failed']}",
                f"  Uptime        : {format_uptime(m['uptime_seconds'])}",
            ]
            return "\n".join(lines)

        elif cmd == "server":
            m = self.server.metrics()
            return (
                f"Virtual Server\n"
                f"  Host   : {m['host']}:{m['port']}\n"
                f"  Status : {'running' if m['running'] else 'stopped'}\n"
                f"  Uptime : {format_uptime(m['uptime_seconds'])}\n"
                f"  API    : http://localhost:{m['port']}/api/v1/\n"
                f"  Dash   : http://localhost:{m['port']}/dashboard"
            )

        elif cmd in ("ask", "ai"):
            query = " ".join(args) if args else ""
            if not query:
                return "Usage: ask <your question>"
            resp = self.ai_engine.ask(query)
            return resp.text

        elif cmd in ("cloud-ai", "cloudai"):
            sub = args[0].lower() if args else "status"
            rest = args[1:] if len(args) > 1 else []

            if sub == "status":
                info = self._cloud_ai_router.backend_info() if self._cloud_ai_router else {}
                m = self._cloud_ai_router.metrics() if self._cloud_ai_router else {}
                lines = [
                    "── Cloud AI Router ──────────────────────────",
                    f"  Backend    : {info.get('backend_class', '?')}",
                    f"  Model      : {info.get('model_name', '?')}",
                    f"  Server URL : {info.get('base_url', '?')}",
                    f"  Ready      : {'✅ Yes' if info.get('is_ready') else '❌ No (Ollama not running)'}",
                    f"  Server ver : {info.get('server_version') or 'n/a'}",
                    f"  Cloud rtr  : {'enabled' if m.get('cloud_router_enabled') else 'disabled'}",
                    f"  Queries    : {m.get('queries_routed', 0)} routed / "
                    f"{m.get('queries_completed', 0)} done / {m.get('queries_failed', 0)} failed",
                    f"  Uptime     : {m.get('uptime_seconds', 0):.0f}s",
                    "",
                    "  To start Ollama:  ollama serve",
                    f"  To pull model:    aura cloud-ai pull",
                    f"  To ask via cloud: aura cloud-ai ask <question>",
                ]
                return "\n".join(lines)

            elif sub == "ask":
                query = " ".join(rest) if rest else ""
                if not query:
                    return "Usage: cloud-ai ask <your question>"
                if self._cloud_ai_router is None:
                    return "Cloud AI Router not initialised."
                resp = self._cloud_ai_router.route(query)
                return resp.text

            elif sub == "pull":
                model = rest[0] if rest else None
                if self._cloud_ai_router is None:
                    return "Cloud AI Router not initialised."
                target = model or self._config.ollama.model
                ok = self._cloud_ai_router.pull_model(model)
                if ok:
                    return (
                        f"Pull task submitted for model '{target}'.\n"
                        "This runs in the background — check progress with: aura tasks"
                    )
                return f"Failed to submit pull task for '{target}'."

            elif sub == "models":
                models = self._cloud_ai_router.list_cloud_models() if self._cloud_ai_router else []
                if not models:
                    return "No AI models registered in the Virtual Cloud."
                lines = ["Virtual Cloud AI Models:"]
                for m in models:
                    lines.append(f"  • {m['model_name']}  [{m['backend']}]  {m['size_human']}")
                return "\n".join(lines)

            elif sub == "list":
                # List models available on the Ollama server
                if self._cloud_ai_router is None:
                    return "Cloud AI Router not initialised."
                b = self._cloud_ai_router._backend
                if hasattr(b, "list_models"):
                    ollama_models = b.list_models()
                    if not ollama_models:
                        return "No models found on Ollama server (is it running?)"
                    lines = ["Models on Ollama server:"]
                    for m in ollama_models:
                        name = m.get("name", "?")
                        size = m.get("size", 0)
                        from aura.utils import format_bytes
                        lines.append(f"  • {name}  {format_bytes(size)}")
                    return "\n".join(lines)
                return "list not supported by current backend."

            else:
                return (
                    "cloud-ai sub-commands: status | ask <q> | pull [model] | models | list"
                )

        elif cmd == "models":
            models = self.cloud.list_models()
            if not models:
                return "No models registered."
            lines = ["Registered AI models:"]
            for m in models:
                lines.append(f"  • {m['model_name']}  [{m['backend']}]  {m['size_human']}")
            return "\n".join(lines)

        elif cmd == "nodes":
            nodes = self.cloud.list_nodes()
            lines = [f"Cloud Nodes ({len(nodes)} total):"]
            for n in nodes:
                lines.append(
                    f"  {n['node_id']}  {n['status']}  "
                    f"CPU:{n['cpu_utilisation']:.0f}%  MEM:{n['memory_utilisation']:.0f}%"
                )
            return "\n".join(lines)

        elif cmd == "tasks":
            tasks = self.cpu.list_tasks()
            if not tasks:
                return "No tasks recorded."
            lines = [f"CPU Tasks ({len(tasks)} total):"]
            for t in tasks[-20:]:
                lines.append(
                    f"  [{t['status']:<10}] {t['task_id']}  {t['name']}  {t['duration_ms']:.0f}ms"
                )
            return "\n".join(lines)

        elif cmd == "plan":
            task_desc = " ".join(args) if args else "optimise the AURa virtual system"
            resp = self.ai_engine.plan_task(task_desc)
            return resp.text

        elif cmd == "analyse":
            resp = self.ai_engine.analyse_metrics(self.metrics())
            return resp.text

        elif cmd == "history":
            hist = self.ai_engine.get_history()
            if not hist:
                return "No conversation history."
            lines = []
            for msg in hist[-20:]:
                role = "You" if msg["role"] == "user" else "AURa"
                lines.append(f"{role}: {msg['content'][:120]}")
            return "\n".join(lines)

        elif cmd == "clear_history":
            self.ai_engine.clear_history()
            return "Conversation history cleared."

        elif cmd == "version":
            return f"AURa v{self.VERSION} — Autonomous Universal Resource Architecture"

        elif cmd in ("bash", "!"):
            # Execute a shell command via AndroidBridge
            shell_cmd = " ".join(args) if args else ""
            if not shell_cmd:
                return "Usage: bash <command>  (or !<command>)"
            if self._bridge is None:
                return "bash: platform bridge not initialised"
            result = self._bridge.run_shell(shell_cmd)
            parts_out = []
            if result.stdout:
                parts_out.append(result.stdout.rstrip())
            if result.stderr:
                parts_out.append(result.stderr.rstrip())
            if result.timed_out:
                parts_out.append("(command timed out)")
            return "\n".join(parts_out) if parts_out else f"(exit {result.returncode})"

        elif cmd == "platform":
            caps = self._capabilities
            if not caps:
                return "platform: capabilities not yet detected"
            shells_avail = [k for k, v in caps.get("shells", {}).items() if v]
            tools_avail = [k for k, v in caps.get("tools", {}).items() if v]
            return (
                f"Platform   : {caps.get('platform')}\n"
                f"Termux     : {caps.get('is_termux')}\n"
                f"Python     : {caps.get('python_version')}\n"
                f"Arch       : {caps.get('architecture')}\n"
                f"CPUs       : {caps.get('cpu_count')}\n"
                f"Shells     : {', '.join(shells_avail) or '(none)'}\n"
                f"Tools      : {', '.join(tools_avail) or '(none)'}"
            )

        elif cmd == "plugins":
            if self._plugin_manager is None:
                return "plugins: manager not initialised"
            plugins = self._plugin_manager.list_plugins()
            if not plugins:
                return "No plugins registered."
            lines = [f"Registered plugins ({len(plugins)}):"]
            for p in plugins:
                lines.append(f"  • {p['name']:<16} — {p['description']}")
            return "\n".join(lines)

        elif cmd == "kv":
            if self._persistence is None:
                return "kv: persistence engine not initialised"
            sub = args[0].lower() if args else ""
            if sub == "set" and len(args) >= 4:
                ns, key, val = args[1], args[2], " ".join(args[3:])
                self._persistence.set(ns, key, val)
                return f"kv: set {ns}/{key}"
            elif sub == "get" and len(args) >= 3:
                ns, key = args[1], args[2]
                val = self._persistence.get(ns, key)
                return str(val) if val is not None else f"kv: {ns}/{key} not found"
            elif sub == "del" and len(args) >= 3:
                ns, key = args[1], args[2]
                removed = self._persistence.delete(ns, key)
                return f"kv: deleted {ns}/{key}" if removed else f"kv: {ns}/{key} not found"
            elif sub == "list" and len(args) >= 2:
                ns = args[1]
                keys = self._persistence.list_keys(ns)
                return "\n".join(f"  {k}" for k in keys) if keys else f"kv: no keys in {ns}"
            elif sub == "namespaces":
                nss = self._persistence.namespaces()
                return "\n".join(f"  {n}" for n in nss) if nss else "kv: no namespaces"
            else:
                return (
                    "Usage:\n"
                    "  kv set <ns> <key> <value>\n"
                    "  kv get <ns> <key>\n"
                    "  kv del <ns> <key>\n"
                    "  kv list <ns>\n"
                    "  kv namespaces"
                )

        elif cmd in ("help", "?"):
            base = (
                "AURa OS v2.0.0 Commands:\n"
                "  status        — system health overview\n"
                "  metrics       — detailed component metrics\n"
                "  cloud         — virtual cloud metrics\n"
                "  cpu           — virtual CPU metrics\n"
                "  server        — virtual server info\n"
                "  nodes         — list cloud compute nodes\n"
                "  models        — list registered AI models\n"
                "  tasks         — list CPU tasks\n"
                "  ask <query>   — query the AI engine (builtin/transformers)\n"
                "  cloud-ai status           — Cloud AI Router status\n"
                "  cloud-ai ask <question>   — ask the large cloud AI model\n"
                "  cloud-ai pull [model]     — download model to virtual cloud\n"
                "  cloud-ai models           — list models in virtual cloud\n"
                "  cloud-ai list             — list models on Ollama server\n"
                "  plan <task>   — AI-generated task execution plan\n"
                "  analyse       — AI analysis of current metrics\n"
                "  history       — show conversation history\n"
                "  clear_history — clear conversation history\n"
                "  version       — show AURa version\n"
                "  platform      — show detected platform capabilities\n"
                "  plugins       — list registered plugins\n"
                "  bash <cmd>    — run a shell command (!<cmd> also works)\n"
                "  kv …          — key-value persistence store\n"
                "  root          — ROOT sovereign layer status\n"
                "  dev           — list /dev/* virtual hardware devices\n"
                "  net           — network stack status (DHCP/DNS/NAT/FW)\n"
                "  vgpu          — compute dispatcher (/dev/vgpu) status\n"
                "  vram          — virtual RAM device status\n"
                "  vdisk         — virtual disk device status\n"
                "  home          — HOME userland status\n"
                "  fs …          — HOME filesystem (ls/mkdir/write/read/rm/info)\n"
                "  pkg …         — package manager (list/install/remove/git)\n"
                "  git …         — git operations (clone/pull/status)\n"
                "  build …       — build pipeline (run/list/approve/reject)\n"
                "  identity      — identity registry status\n"
                "  audit         — recent audit log entries\n"
                "  kernel        — kernel services status\n"
                "  proc          — process manager status\n"
                "  syslog        — system log viewer\n"
                "  cron …        — cron job management\n"
                "  svc …         — service manager\n"
                "  vfs …         — virtual filesystem operations\n"
                "  apkg …        — AURA package manager (registry/install/list)\n"
                "  mirror        — mirror service status\n"
                "  intel         — intelligence index summary\n"
                "  personality   — AI personality kernel status\n"
                "  modelreg      — AI model registry\n"
                "  banner        — show AURA boot banner\n"
                "  help          — show this help\n"
                "  exit / quit   — exit the AURa shell"
            )
            if self._commands:
                custom = "\n".join(
                    f"  {name:<14}— (custom command)" for name in sorted(self._commands)
                )
                return base + "\n\nCustom commands:\n" + custom
            return base

        elif cmd == "root":
            if self._root is None:
                return "root: ROOT layer not initialised"
            s = self._root.status()
            lines = [
                "── ROOT Sovereign Layer ────────────────────────────",
                f"  Running        : {s['running']}",
                f"  HOME mounted   : {s['home_mounted']}",
                f"  Uptime         : {format_uptime(s['uptime_seconds'])}",
                f"  Policy rules   : {s['policy_rules']}",
                f"  Audit entries  : {s['audit_entries']}",
                f"  Pending approvals : {s['pending_approvals']}",
            ]
            return "\n".join(lines)

        elif cmd == "dev":
            if self._device_manager is None:
                return "dev: device manager not initialised"
            devices = self._device_manager.list_devices()
            lines = [f"── /dev/ Virtual Hardware ({len(devices)} devices) ──────"]
            for d in devices:
                lines.append(
                    f"  {d['path']:<14} kind={d['kind']:<6} claimed_by={d['claimed_by']}"
                )
            return "\n".join(lines)

        elif cmd == "net":
            if self._dev_vnet is None:
                return "net: /dev/vnet not initialised"
            m = self._dev_vnet.metrics()
            dhcp = m["dhcp"]
            dns = m["dns"]
            nat = m["nat"]
            fw = m["firewall"]
            lines = [
                "── /dev/vnet Network Stack ─────────────────────────",
                f"  DHCP subnet    : {dhcp['subnet']}",
                f"  DHCP leases    : {dhcp['active_leases']}/{dhcp['pool_size']}",
                f"  DNS records    : {dns['record_count']} ({dns['zone_count']} zones)",
                f"  NAT            : {'enabled' if nat['enabled'] else 'disabled'}  entries={nat['entry_count']}",
                f"  Firewall rules : {fw['rule_count']}  default={fw['default_verdict']}",
            ]
            return "\n".join(lines)

        elif cmd == "vgpu":
            if self._dev_vgpu is None:
                return "vgpu: /dev/vgpu not initialised"
            m = self._dev_vgpu.metrics()
            lines = [
                "── /dev/vgpu Compute Dispatcher ────────────────────",
                f"  Active backend : {m['active_backend']}",
                f"  Local CPU      : {m['local_cpu_pct']:.1f}%",
                f"  Spill threshold: {m['spill_threshold_pct']:.0f}%",
                f"  Total jobs     : {m['total_jobs']}",
            ]
            for status, count in m.get("by_status", {}).items():
                lines.append(f"  {status:<12}   : {count}")
            return "\n".join(lines)

        elif cmd == "vram":
            if self._dev_vram is None:
                return "vram: /dev/vram not initialised"
            m = self._dev_vram.metrics()
            lines = [
                "── /dev/vram Virtual RAM ───────────────────────────",
                f"  Total          : {m['total_mb']:.0f} MB",
                f"  Used           : {m['used_mb']:.1f} MB",
                f"  Free           : {m['free_mb']:.1f} MB",
                f"  Utilisation    : {m['utilisation_pct']:.1f}%",
                f"  Allocations    : {m['allocation_count']}",
            ]
            return "\n".join(lines)

        elif cmd == "vdisk":
            if self._dev_vdisk is None:
                return "vdisk: /dev/vdisk not initialised"
            m = self._dev_vdisk.metrics()
            vols = self._dev_vdisk.list_volumes()
            lines = [
                "── /dev/vdisk Virtual Disk ─────────────────────────",
                f"  Volumes        : {m['volume_count']}",
                f"  Total GB       : {m['total_gb']:.1f}",
                f"  Used           : {m['used_gb']:.3f} GB",
            ]
            for v in vols:
                mounted = f"→ {v['mount_point']}" if v['mount_point'] else "(not mounted)"
                lines.append(
                    f"  [{v['status']:<10}] {v['name']:<12} {v['size_gb']:.0f}GB {mounted}"
                )
            return "\n".join(lines)

        elif cmd == "home":
            if self._home is None:
                return "home: HOME layer not initialised"
            s = self._home.status()
            lines = [
                "── HOME Userland ───────────────────────────────────",
                f"  Running        : {s['running']}",
                f"  Boot device    : {s['boot_device']}",
                f"  Home dir       : {s['home_dir']}",
                f"  Packages       : {s['packages']}",
                f"  Processes      : {s['processes']}",
            ]
            return "\n".join(lines)

        elif cmd == "fs":
            if self._home is None:
                return "fs: HOME layer not initialised"
            fs = self._home.filesystem
            sub = args[0].lower() if args else ""
            if sub in ("ls", "list", "dir"):
                rel = args[1] if len(args) > 1 else ""
                try:
                    parts_path = [rel] if rel else []
                    entries = fs.ls(*parts_path) if parts_path else fs.ls()
                    return "\n".join(entries) if entries else "(empty)"
                except (ValueError, OSError) as exc:
                    return f"fs ls: {exc}"
            elif sub == "mkdir":
                if len(args) < 2:
                    return "Usage: fs mkdir <path>"
                try:
                    os.makedirs(fs.path(args[1]), exist_ok=True)
                    return f"fs: created {args[1]}"
                except (ValueError, OSError) as exc:
                    return f"fs mkdir: {exc}"
            elif sub in ("write", "mkfile"):
                if len(args) < 3:
                    return "Usage: fs write <path> <content>"
                content = " ".join(args[2:])
                try:
                    fs.write(content, args[1])
                    return f"fs: wrote {len(content)} bytes to {args[1]}"
                except (ValueError, OSError) as exc:
                    return f"fs write: {exc}"
            elif sub in ("read", "cat"):
                if len(args) < 2:
                    return "Usage: fs read <path>"
                try:
                    return fs.read(args[1])
                except (ValueError, OSError) as exc:
                    return f"fs read: {exc}"
            elif sub in ("rm", "del", "delete"):
                if len(args) < 2:
                    return "Usage: fs rm <path>"
                try:
                    removed = fs.delete(args[1])
                    return f"fs: removed {args[1]}" if removed else f"fs: {args[1]} not found"
                except (ValueError, OSError) as exc:
                    return f"fs rm: {exc}"
            elif sub == "info":
                m = fs.metrics()
                total = m["disk_total_bytes"]
                used = m["disk_used_bytes"]
                free = m["disk_free_bytes"]
                pct = (used / total * 100) if total else 0
                return (
                    f"HOME filesystem: {m['base_dir']}\n"
                    f"  Total : {total // (1024**3):.1f} GB\n"
                    f"  Used  : {used // (1024**2):.0f} MB  ({pct:.1f}%)\n"
                    f"  Free  : {free // (1024**2):.0f} MB"
                )
            else:
                return (
                    "Usage:\n"
                    "  fs ls [path]            — list directory\n"
                    "  fs mkdir <path>         — create directory\n"
                    "  fs write <path> <text>  — write/overwrite a file\n"
                    "  fs read <path>          — read a file\n"
                    "  fs rm <path>            — delete a file or directory\n"
                    "  fs info                 — filesystem disk usage"
                )

        elif cmd == "pkg":
            if self._home is None:
                return "pkg: HOME layer not initialised"
            sub = args[0].lower() if args else ""
            if sub == "list":
                pkgs = self._home.list_packages()
                if not pkgs:
                    return "pkg: no packages installed"
                lines = [f"Installed packages ({len(pkgs)}):"]
                for p in pkgs:
                    lines.append(f"  {p['name']:<20} {p['version']:<12} {p['description']}")
                return "\n".join(lines)
            elif sub == "install" and len(args) >= 2:
                name = args[1]
                version = args[2] if len(args) > 2 else "1.0.0"
                desc = " ".join(args[3:]) if len(args) > 3 else ""
                pkg = self._home.install_package(name, version, desc)
                return f"pkg: installed {pkg.name} {pkg.version}"
            elif sub == "remove" and len(args) >= 2:
                name = args[1]
                removed = self._home.remove_package(name)
                return f"pkg: removed {name}" if removed else f"pkg: {name} not installed"
            elif sub == "git" and len(args) >= 2:
                url = args[1]
                name = args[2] if len(args) > 2 else None
                try:
                    pkg = self._home.git_install(url, name)
                    return f"pkg: git installed {pkg.name} from {url}"
                except (RuntimeError, OSError) as exc:
                    return f"pkg git: {exc}"
            else:
                return (
                    "Usage:\n"
                    "  pkg list                       — list installed packages\n"
                    "  pkg install <name> [version]   — register/install a package\n"
                    "  pkg remove <name>              — uninstall a package\n"
                    "  pkg git <url> [name]           — clone & install a git package"
                )

        elif cmd == "git":
            if self._bridge is None:
                return "git: platform bridge not initialised"
            sub = args[0].lower() if args else ""
            if sub == "clone" and len(args) >= 2:
                url = args[1]
                dest = args[2] if len(args) > 2 else None
                git_args = ["git", "clone", "--", url]
                if dest:
                    git_args.append(dest)
                result = self._bridge.run(git_args, timeout=120)
                out_parts = []
                if result.stdout:
                    out_parts.append(result.stdout.rstrip())
                if result.stderr:
                    out_parts.append(result.stderr.rstrip())
                return "\n".join(out_parts) if out_parts else (
                    f"git: cloned {url}" if result.success else f"git: clone failed (rc={result.returncode})"
                )
            elif sub == "pull":
                directory = args[1] if len(args) > 1 else None
                pull_args = ["git", "pull"]
                result = self._bridge.run(pull_args, cwd=directory, timeout=60)
                out_parts = []
                if result.stdout:
                    out_parts.append(result.stdout.rstrip())
                if result.stderr:
                    out_parts.append(result.stderr.rstrip())
                return "\n".join(out_parts) if out_parts else (
                    "git: pull complete" if result.success else f"git: pull failed (rc={result.returncode})"
                )
            elif sub == "status":
                directory = args[1] if len(args) > 1 else None
                result = self._bridge.run(["git", "status", "--short"], cwd=directory, timeout=15)
                return result.stdout.rstrip() or "git: working tree clean"
            else:
                return (
                    "Usage:\n"
                    "  git clone <url> [dir]  — clone a repository\n"
                    "  git pull [dir]         — pull latest changes\n"
                    "  git status [dir]       — show working tree status"
                )

        elif cmd == "build":
            if self._build_pipeline is None:
                return "build: pipeline not initialised"
            sub = args[0].lower() if args else ""
            if sub == "run":
                name = args[1] if len(args) > 1 else "aura"
                version = args[2] if len(args) > 2 else "1.0.0"
                commit = args[3] if len(args) > 3 else "HEAD"
                run = self._build_pipeline.run(
                    name=name, version=version, commit=commit,
                )
                return (
                    f"Build run {run.run_id}: {run.status.value}\n"
                    + "\n".join(
                        f"  [{s['status']}] {s['stage']}  {s['duration_ms']:.0f}ms"
                        for s in run.stages
                    )
                )
            elif sub in ("list", "runs"):
                runs = self._build_pipeline.list_runs()
                if not runs:
                    return "build: no runs yet"
                lines = [f"Build runs ({len(runs)}):"]
                for r in runs[-10:]:
                    lines.append(
                        f"  {r['run_id']}  [{r['status']:<12}]  {r['name']} v{r['version']}"
                    )
                return "\n".join(lines)
            elif sub == "approve" and len(args) >= 2:
                request_id = args[1]
                try:
                    req = self._root.approval_gate.approve(request_id)
                    return f"build: approved {request_id} → artefact ready for deploy"
                except (KeyError, ValueError) as exc:
                    return f"build: {exc}"
            elif sub == "reject" and len(args) >= 2:
                request_id = args[1]
                reason = " ".join(args[2:]) if len(args) > 2 else "Rejected by operator"
                try:
                    req = self._root.approval_gate.reject(request_id, reason)
                    return f"build: rejected {request_id}"
                except (KeyError, ValueError) as exc:
                    return f"build: {exc}"
            elif sub == "approvals":
                from aura.root.approval import ApprovalStatus
                reqs = self._root.approval_gate.list_requests()
                if not reqs:
                    return "build: no approval requests"
                lines = [f"Approval requests ({len(reqs)}):"]
                for r in reqs:
                    lines.append(
                        f"  {r['request_id']}  [{r['status']:<10}]  "
                        f"artefact={r['artefact_id']}  by={r['submitter']}"
                    )
                return "\n".join(lines)
            else:
                return (
                    "Usage:\n"
                    "  build run [name] [version] [commit]\n"
                    "  build list\n"
                    "  build approvals\n"
                    "  build approve <request_id>\n"
                    "  build reject <request_id> [reason]"
                )

        elif cmd == "identity":
            if self._identity_registry is None:
                return "identity: not initialised"
            m = self._identity_registry.metrics()
            lines = [
                "── Identity Registry ───────────────────────────────",
                f"  Total tokens   : {m['total_tokens']}",
                f"  Active         : {m['active']}",
                f"  Revoked        : {m['revoked']}",
                f"  Expired        : {m['expired']}",
            ]
            return "\n".join(lines)

        elif cmd == "audit":
            if self._audit_log is None:
                return "audit: not initialised"
            n = int(args[0]) if args and args[0].isdigit() else 20
            events = self._audit_log.query(last_n=n)
            if not events:
                return "audit: no events recorded"
            lines = [f"Audit log (last {n}):"]
            for e in events:
                lines.append(
                    f"  [{e['ts']}] {e['actor']:<12} {e['action']:<20} "
                    f"{e['resource']:<25} {e['outcome']}"
                )
            return "\n".join(lines)

        elif cmd == "kernel":
            lines = [
                "── Kernel Services (v2.0.0) ────────────────────────",
                f"  ProcessManager : {'online' if self._process_manager else 'offline'}",
                f"  IPCBus         : {'online' if self._ipc_bus else 'offline'}",
                f"  SyslogService  : {'online' if self._syslog else 'offline'}",
                f"  SecretsManager : {'online' if self._secrets_manager else 'offline'}",
                f"  CronService    : {'online' if self._cron else 'offline'}",
                f"  ServiceManager : {'online' if self._service_manager else 'offline'}",
            ]
            if self._service_manager:
                m = self._service_manager.metrics()
                lines.append(f"  Services       : {m.get('total', 0)} total  active={m.get('active', 0)}")
            return "\n".join(lines)

        elif cmd == "proc":
            if self._process_manager is None:
                return "proc: process manager not initialised"
            procs = self._process_manager.list_processes()
            m = self._process_manager.metrics()
            lines = [f"── Processes ({m.get('total', 0)} total) ────────────────────"]
            for p in procs[-20:]:
                lines.append(
                    f"  [{p['state']:<8}] {p['pid']}  {p['name']}"
                )
            return "\n".join(lines) if len(lines) > 1 else "proc: no processes"

        elif cmd == "syslog":
            if self._syslog is None:
                return "syslog: not initialised"
            limit = int(args[0]) if args and args[0].isdigit() else 20
            level = args[1] if len(args) > 1 else None
            entries = self._syslog.query(level=level, limit=limit)
            if not entries:
                return "syslog: no entries"
            lines = [f"Syslog (last {limit}):"]
            for e in entries:
                lines.append(f"  [{e['level']:<5}] {e['timestamp'][:19]}  {e['source']}: {e['message']}")
            return "\n".join(lines)

        elif cmd == "cron":
            if self._cron is None:
                return "cron: not initialised"
            jobs = self._cron.list_jobs()
            if not jobs:
                return "cron: no jobs registered"
            lines = [f"Cron Jobs ({len(jobs)}):"]
            for j in jobs:
                en = "✓" if j["enabled"] else "✗"
                lines.append(
                    f"  [{en}] {j['job_id']}  {j['name']:<20}  every {j['interval_seconds']}s  runs={j['run_count']}"
                )
            return "\n".join(lines)

        elif cmd == "svc":
            if self._service_manager is None:
                return "svc: not initialised"
            sub = args[0].lower() if args else ""
            if sub == "list" or not sub:
                svcs = self._service_manager.list_services()
                if not svcs:
                    return "svc: no services"
                lines = [f"Services ({len(svcs)}):"]
                for s in svcs:
                    lines.append(f"  [{s['state']:<8}] {s['name']}")
                return "\n".join(lines)
            elif sub == "start" and len(args) >= 2:
                ok = self._service_manager.start_service(args[1])
                return f"svc: started {args[1]}" if ok else f"svc: {args[1]} not found"
            elif sub == "stop" and len(args) >= 2:
                ok = self._service_manager.stop_service(args[1])
                return f"svc: stopped {args[1]}" if ok else f"svc: {args[1]} not found"
            elif sub == "restart" and len(args) >= 2:
                ok = self._service_manager.restart_service(args[1])
                return f"svc: restarted {args[1]}" if ok else f"svc: {args[1]} not found"
            else:
                return "Usage: svc [list|start <name>|stop <name>|restart <name>]"

        elif cmd == "vfs":
            if self._vfs is None:
                return "vfs: not initialised"
            sub = args[0].lower() if args else ""
            if sub == "ls" and len(args) >= 2:
                entries = self._vfs.listdir(args[1])
                return "\n".join(entries) if entries else "(empty)"
            elif sub == "mkdir" and len(args) >= 2:
                ok = self._vfs.mkdir(args[1])
                return f"vfs: mkdir {args[1]}" if ok else f"vfs: {args[1]} already exists"
            elif sub == "stat" and len(args) >= 2:
                info = self._vfs.stat(args[1])
                return str(info) if info else f"vfs: {args[1]} not found"
            elif sub == "mounts":
                mounts = list(self._vfs._mounts.keys())
                return "\n".join(mounts) if mounts else "vfs: no mounts"
            else:
                return "Usage: vfs [ls <path>|mkdir <path>|stat <path>|mounts]"

        elif cmd == "apkg":
            if self._pkg_installer is None:
                return "apkg: package manager not initialised"
            sub = args[0].lower() if args else ""
            if sub == "list" or not sub:
                installed = self._pkg_installer.list_installed()
                if not installed:
                    return "apkg: no packages installed"
                lines = [f"Installed AURA packages ({len(installed)}):"]
                for p in installed:
                    lines.append(f"  {p['name']:<24} {p['version']}")
                return "\n".join(lines)
            elif sub == "registry":
                pkgs = self._pkg_registry.list_all() if self._pkg_registry else []
                lines = [f"Package registry ({len(pkgs)} packages):"]
                for p in pkgs:
                    lines.append(f"  {p.name:<24} {p.version}  {p.description}")
                return "\n".join(lines)
            elif sub == "install" and len(args) >= 2:
                result = self._pkg_installer.install(args[1])
                return f"apkg: {result['message']}"
            elif sub == "remove" and len(args) >= 2:
                result = self._pkg_installer.uninstall(args[1])
                return f"apkg: {result['message']}"
            else:
                return "Usage: apkg [list|registry|install <name>|remove <name>]"

        elif cmd == "mirror":
            if self._mirror is None:
                return "mirror: not initialised"
            m = self._mirror.metrics()
            mirrors = self._mirror.list_mirrors()
            lines = [
                f"── Mirror Service ──────────────────────────────────",
                f"  Total mirrors  : {len(mirrors)}",
                f"  Online         : {m.get('by_status', {}).get('online', 0)}",
                f"  Offline        : {m.get('by_status', {}).get('offline', 0)}",
            ]
            primary = self._mirror.get_primary()
            if primary:
                lines.append(f"  Primary        : {primary['name']} ({primary['url']})")
            return "\n".join(lines)

        elif cmd == "intel":
            if self._intelligence_index is None:
                return "intel: not initialised"
            top = self._intelligence_index.top_n(5, sort_by="performance_score")
            lines = [f"── Intelligence Index ({len(self._intelligence_index.list_entries())} entries) ─────"]
            for e in top:
                lines.append(
                    f"  {e['model_name']:<24} safety={e['safety_rating']:.1f}  perf={e['performance_score']:.1f}"
                )
            return "\n".join(lines)

        elif cmd == "personality":
            if self._personality_kernel is None:
                return "personality: not initialised"
            profile = self._personality_kernel.to_dict()
            lines = [
                f"── AI Personality Kernel ───────────────────────────",
                f"  Name           : {profile.get('name')}",
                f"  Tone           : {profile.get('tone')}",
                f"  Verbosity      : {profile.get('verbosity')}/10",
                f"  Empathy        : {profile.get('empathy')}/10",
                f"  Tech depth     : {profile.get('technical_depth')}/10",
                f"  Language       : {profile.get('language')}",
                f"  Traits         : {', '.join(profile.get('traits', []))}",
            ]
            return "\n".join(lines)

        elif cmd == "modelreg":
            if self._model_registry is None:
                return "modelreg: not initialised"
            models = self._model_registry.list_models()
            if not models:
                return "modelreg: no models registered"
            lines = [f"AI Model Registry ({len(models)} models):"]
            for m in models:
                lines.append(
                    f"  {m['model_id']}  {m['name']:<24} [{m['backend']}]  status={m['status']}"
                )
            return "\n".join(lines)

        elif cmd == "banner":
            from branding.banner import get_boot_banner
            return get_boot_banner(self.VERSION)

        elif cmd in self._commands:
            # Custom registered command
            return self._commands[cmd](self, args)

        elif self._plugin_manager is not None and self._plugin_manager.handles(cmd):
            # Plugin-provided command
            return self._plugin_manager.dispatch(cmd, args) or ""

        else:
            # Unknown command → route to AI engine
            resp = self.ai_engine.ask(command + (" " + " ".join(args) if args else ""))
            return resp.text

    # ------------------------------------------------------------------
    # Internal event handler
    # ------------------------------------------------------------------

    def _on_event(self, event_type: str, payload: Any) -> None:
        if event_type != "*":  # avoid double-logging
            self._logger.debug("Event received: %s", event_type)

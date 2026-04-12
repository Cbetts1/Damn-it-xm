# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Configuration
Central configuration for all virtual components and AI engine settings.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CloudConfig:
    """Virtual Cloud configuration."""
    storage_limit_gb: float = 1024.0
    compute_nodes: int = 8
    region: str = "virtual-us-east-1"
    replication_factor: int = 3
    cdn_enabled: bool = True
    model_cache_dir: str = os.path.join(os.path.expanduser("~"), ".aura", "model_cache")


@dataclass
class CPUConfig:
    """Virtual CPU configuration."""
    virtual_cores: int = 64
    clock_speed_ghz: float = 4.2
    architecture: str = "AURa-v1"
    threads_per_core: int = 2
    cache_l3_mb: int = 128
    max_concurrent_tasks: int = 256


@dataclass
class ServerConfig:
    """Virtual Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    max_connections: int = 1000
    tls_enabled: bool = False
    log_level: str = "info"
    auth_enabled: bool = False
    api_token: Optional[str] = None  # set via AURA_API_TOKEN env var


@dataclass
class AIEngineConfig:
    """AI Engine / model configuration."""
    backend: str = "builtin"           # "builtin" | "transformers" | "openai_compatible"
    model_name: str = "aura-assistant" # or HuggingFace model id
    device: str = "cpu"                # "cpu" | "cuda" | "mps"
    max_tokens: int = 512
    temperature: float = 0.7
    api_base_url: Optional[str] = None # for openai_compatible backend
    api_key: Optional[str] = None      # for openai_compatible backend


@dataclass
class CommandCenterConfig:
    """Command Center (web dashboard) configuration."""
    host: str = "0.0.0.0"
    port: int = 7860
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: ["*"])
    auth_enabled: bool = False
    refresh_interval_ms: int = 2000


@dataclass
class ROOTConfig:
    """ROOT sovereign layer configuration."""
    # All-deny firewall by default; explicit permits required
    default_policy: str = "deny"
    # Secret used to sign ROOT approval tokens (override via AURA_ROOT_SECRET)
    root_secret: str = "aura-root-secret-change-me"
    # Maximum pending approval requests before auto-reject
    max_pending_approvals: int = 64
    # Audit log retention (entries in memory)
    audit_log_max_entries: int = 10000


@dataclass
class HOMEConfig:
    """HOME userland configuration."""
    # Base directory for HOME userland filesystem
    home_dir: str = os.path.join(os.path.expanduser("~"), ".aura", "home")
    # Whether HOME may directly call /dev/* without ROOT gate
    direct_device_access: bool = False
    # Maximum number of concurrent HOME processes
    max_processes: int = 64
    # Boot device label (empty = internal storage, or e.g. "/sdcard/aura" for SD-card boot)
    # When set, home_dir is overridden with this path so the entire HOME filesystem
    # lives on the specified device — enabling SD-card or external-storage boot.
    boot_device: str = ""


@dataclass
class NetworkConfig:
    """Virtual network stack (/dev/vnet) configuration."""
    # DHCP lease pool
    dhcp_subnet: str = "10.0.0.0/24"
    dhcp_lease_time_s: int = 3600
    # DNS settings
    dns_upstream: str = "8.8.8.8"
    dns_search_domain: str = "aura.local"
    # NAT masquerade enable
    nat_enabled: bool = True
    # Default firewall policy (deny / allow)
    firewall_default: str = "deny"
    # Pre-allowed port/protocol pairs: list of "tcp:22", "udp:53", etc.
    firewall_allow_rules: List[str] = field(default_factory=lambda: [
        "tcp:22", "tcp:80", "tcp:443", "tcp:8000", "udp:53",
    ])


@dataclass
class BuildConfig:
    """Build pipeline configuration."""
    # Directory where build artefacts are staged
    artefact_dir: str = os.path.join(os.path.expanduser("~"), ".aura", "artefacts")
    # Whether ROOT approval is required before deploy
    require_root_approval: bool = True
    # HMAC secret for artefact signing
    signing_secret: str = "aura-build-signing-secret-change-me"
    # Auto-approve builds in CI (bypass manual ROOT gate)
    auto_approve_ci: bool = False


@dataclass
class ComputeConfig:
    """Compute abstraction (/dev/vgpu) configuration."""
    # Default backend: "local" or "cloud"
    default_backend: str = "local"
    # Threshold at which local tasks spill over to cloud (0–100 %)
    local_cpu_spill_threshold_pct: float = 80.0
    # Cloud region to target when spilling
    cloud_region: str = "virtual-us-east-1"


@dataclass
class KernelConfig:
    """Kernel services configuration."""
    # CronService tick interval
    cron_tick_seconds: float = 1.0
    # SecretsManager — allowed key pattern (alphanumeric + underscore)
    secrets_key_pattern: str = r"^[A-Za-z0-9_]+$"
    # SyslogService — max rolling entries
    syslog_max_entries: int = 10000
    # ProcessManager — max tracked processes
    process_max_tracked: int = 1024


@dataclass
class WebConfig:
    """Web / remote control layer configuration."""
    auth_enabled: bool = False
    api_token: Optional[str] = None
    websocket_enabled: bool = True
    max_ws_clients: int = 64


@dataclass
class PkgConfig:
    """Package Manager configuration."""
    # Directory where installed packages are tracked
    packages_dir: str = os.path.join(os.path.expanduser("~"), ".aura", "packages")
    # Whether to allow installation of unsigned packages
    allow_unsigned: bool = True


@dataclass
class OllamaConfig:
    """Ollama large-model server configuration.

    Ollama runs as a local server process, keeping heavy model weights
    **out of the phone's RAM** and inside the virtual cloud / CPU layer.
    """
    # Base URL of the Ollama REST API (default: local)
    base_url: str = "http://localhost:11434"
    # Default model to use.  llama3.1:8b is the largest capable model
    # that runs on commodity hardware without a GPU.
    model: str = "llama3.1:8b"
    # Hard timeout for a single generate request (seconds)
    timeout_seconds: int = 120
    # Whether to route every inference call through the VirtualCPU task queue
    use_cloud_router: bool = True
    # Directory inside the virtual cloud model cache where Ollama models live
    model_store_subdir: str = "ollama"


@dataclass
class VNodeConfig:
    """Virtual Network Node configuration.

    Each AURa installation is a virtual node in a larger mesh of repos.
    The node registers itself with a Command Center and participates in
    a virtual cluster for orchestration and state sync.
    """
    # Human-readable name for this node (override via AURA_NODE_NAME)
    node_name: str = "aura-node"
    # URL of the Command Center.  Empty = standalone mode (no registration)
    command_center_url: str = ""
    # How often the node sends a heartbeat to the Command Center (seconds)
    heartbeat_interval_seconds: float = 30.0
    # HTTP request timeout for Command Center calls (seconds)
    timeout_seconds: int = 5
    # File to persist the stable node UUID across restarts
    node_id_file: str = os.path.join(os.path.expanduser("~"), ".aura", "node_id")


@dataclass
class RemoteConfig:
    """Remote TCP/HTTP control server configuration.

    A real HTTP server (Python built-in, no extra deps) that exposes the
    AURa WebAPI over a Termux-safe port (>1024, no root required).
    """
    # Whether the remote control server is enabled
    enabled: bool = False
    # Bind address (0.0.0.0 = all interfaces)
    host: str = "0.0.0.0"
    # Listening port.  8765 is the default Termux-safe port for AURa remote
    port: int = 8765
    # When set, all requests must carry a matching Bearer token
    auth_token: Optional[str] = None


@dataclass
class BuilderConfig:
    """Builder/self-expansion engine configuration."""
    # Directory where auto-generated modules and scripts are written
    output_dir: str = os.path.join(os.path.expanduser("~"), ".aura", "builder")


@dataclass
class AURaConfig:
    """Top-level AURa system configuration."""
    system_name: str = "AURa"
    version: str = "2.0.0"
    log_level: str = "INFO"
    data_dir: str = os.path.join(os.path.expanduser("~"), ".aura")

    cloud: CloudConfig = field(default_factory=CloudConfig)
    cpu: CPUConfig = field(default_factory=CPUConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    ai_engine: AIEngineConfig = field(default_factory=AIEngineConfig)
    command_center: CommandCenterConfig = field(default_factory=CommandCenterConfig)

    # New OS architecture layers
    root: ROOTConfig = field(default_factory=ROOTConfig)
    home: HOMEConfig = field(default_factory=HOMEConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    compute: ComputeConfig = field(default_factory=ComputeConfig)

    # v2.0.0 new subsystems
    kernel: KernelConfig = field(default_factory=KernelConfig)
    web: WebConfig = field(default_factory=WebConfig)
    pkg: PkgConfig = field(default_factory=PkgConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)

    # v2.1.0 virtual network node + remote + builder
    vnode: VNodeConfig = field(default_factory=VNodeConfig)
    remote: RemoteConfig = field(default_factory=RemoteConfig)
    builder: BuilderConfig = field(default_factory=BuilderConfig)

    @classmethod
    def from_env(cls) -> "AURaConfig":
        """Load configuration from environment variables."""
        config = cls()
        config.log_level = os.getenv("AURA_LOG_LEVEL", config.log_level)
        raw_data_dir = os.getenv("AURA_DATA_DIR", config.data_dir)
        # Normalise and resolve to prevent path-traversal from env vars.
        config.data_dir = os.path.normpath(os.path.expanduser(raw_data_dir))
        config.ai_engine.backend = os.getenv("AURA_AI_BACKEND", config.ai_engine.backend)
        config.ai_engine.model_name = os.getenv("AURA_MODEL_NAME", config.ai_engine.model_name)
        config.ai_engine.device = os.getenv("AURA_DEVICE", config.ai_engine.device)
        config.ai_engine.api_base_url = os.getenv("AURA_API_BASE_URL", config.ai_engine.api_base_url)
        config.ai_engine.api_key = os.getenv("AURA_API_KEY", config.ai_engine.api_key)
        config.command_center.port = int(os.getenv("AURA_DASHBOARD_PORT", str(config.command_center.port)))
        config.server.port = int(os.getenv("AURA_SERVER_PORT", str(config.server.port)))
        config.server.api_token = os.getenv("AURA_API_TOKEN", config.server.api_token)
        config.root.root_secret = os.getenv("AURA_ROOT_SECRET", config.root.root_secret)
        config.build.signing_secret = os.getenv("AURA_BUILD_SECRET", config.build.signing_secret)
        config.compute.default_backend = os.getenv("AURA_COMPUTE_BACKEND", config.compute.default_backend)
        config.ollama.base_url = os.getenv("AURA_OLLAMA_URL", config.ollama.base_url)
        config.ollama.model = os.getenv("AURA_OLLAMA_MODEL", config.ollama.model)
        config.ollama.use_cloud_router = os.getenv("AURA_OLLAMA_CLOUD_ROUTER", "true").lower() != "false"
        # Virtual node settings
        config.vnode.node_name = os.getenv("AURA_NODE_NAME", config.vnode.node_name)
        config.vnode.command_center_url = os.getenv("AURA_COMMAND_CENTER_URL", config.vnode.command_center_url)
        config.vnode.heartbeat_interval_seconds = float(
            os.getenv("AURA_HEARTBEAT_INTERVAL", str(config.vnode.heartbeat_interval_seconds))
        )
        # Remote control server settings
        config.remote.enabled = os.getenv("AURA_REMOTE_ENABLED", "false").lower() == "true"
        config.remote.host = os.getenv("AURA_REMOTE_HOST", config.remote.host)
        config.remote.port = int(os.getenv("AURA_REMOTE_PORT", str(config.remote.port)))
        config.remote.auth_token = os.getenv("AURA_REMOTE_TOKEN", config.remote.auth_token)
        # Builder settings
        config.builder.output_dir = os.path.normpath(
            os.path.expanduser(os.getenv("AURA_BUILDER_DIR", config.builder.output_dir))
        )
        # SD-card / external-device boot: AURA_BOOT_DEVICE overrides home_dir
        boot_dev = os.getenv("AURA_BOOT_DEVICE", "")
        if boot_dev:
            config.home.boot_device = boot_dev
            config.home.home_dir = os.path.normpath(os.path.expanduser(boot_dev))
        else:
            # Allow direct home_dir override without boot_device label
            config.home.home_dir = os.path.normpath(
                os.path.expanduser(os.getenv("AURA_HOME_DIR", config.home.home_dir))
            )
        return config


# Global default configuration instance
DEFAULT_CONFIG = AURaConfig.from_env()

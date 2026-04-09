"""
AURa Configuration
Central configuration for all virtual components and AI engine settings.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


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
class AURaConfig:
    """Top-level AURa system configuration."""
    system_name: str = "AURa"
    version: str = "1.2.0"
    log_level: str = "INFO"
    data_dir: str = os.path.join(os.path.expanduser("~"), ".aura")

    cloud: CloudConfig = field(default_factory=CloudConfig)
    cpu: CPUConfig = field(default_factory=CPUConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    ai_engine: AIEngineConfig = field(default_factory=AIEngineConfig)
    command_center: CommandCenterConfig = field(default_factory=CommandCenterConfig)

    @classmethod
    def from_env(cls) -> "AURaConfig":
        """Load configuration from environment variables."""
        config = cls()
        config.log_level = os.getenv("AURA_LOG_LEVEL", config.log_level)
        config.data_dir = os.getenv("AURA_DATA_DIR", config.data_dir)
        config.ai_engine.backend = os.getenv("AURA_AI_BACKEND", config.ai_engine.backend)
        config.ai_engine.model_name = os.getenv("AURA_MODEL_NAME", config.ai_engine.model_name)
        config.ai_engine.device = os.getenv("AURA_DEVICE", config.ai_engine.device)
        config.ai_engine.api_base_url = os.getenv("AURA_API_BASE_URL", config.ai_engine.api_base_url)
        config.ai_engine.api_key = os.getenv("AURA_API_KEY", config.ai_engine.api_key)
        config.command_center.port = int(os.getenv("AURA_DASHBOARD_PORT", str(config.command_center.port)))
        config.server.port = int(os.getenv("AURA_SERVER_PORT", str(config.server.port)))
        config.server.api_token = os.getenv("AURA_API_TOKEN", config.server.api_token)
        return config


# Global default configuration instance
DEFAULT_CONFIG = AURaConfig.from_env()

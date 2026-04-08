"""
Tests for the AURa AI Virtual System.
Covers: config, utils, AI engine, virtual cloud, virtual CPU,
        virtual server, AI OS orchestration, and the shell dispatcher.
"""

import time
import threading
import urllib.error
import urllib.request
import pytest


def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
    """Poll until the server responds to /health or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    pytest.fail(f"Server at {host}:{port} did not become ready within {timeout}s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_default_config_loads():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert cfg.version == "1.0.0"
    assert cfg.cloud.compute_nodes == 8
    assert cfg.cpu.virtual_cores == 64
    assert cfg.server.port == 8000
    assert cfg.ai_engine.backend == "builtin"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("AURA_AI_BACKEND", "openai_compatible")
    monkeypatch.setenv("AURA_MODEL_NAME", "mistral")
    monkeypatch.setenv("AURA_SERVER_PORT", "9090")
    from aura.config import AURaConfig
    cfg = AURaConfig.from_env()
    assert cfg.ai_engine.backend == "openai_compatible"
    assert cfg.ai_engine.model_name == "mistral"
    assert cfg.server.port == 9090


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------

def test_generate_id_unique():
    from aura.utils import generate_id
    ids = {generate_id("x") for _ in range(100)}
    assert len(ids) == 100


def test_format_bytes():
    from aura.utils import format_bytes
    assert format_bytes(0) == "0.0 B"
    assert "KB" in format_bytes(1024)
    assert "MB" in format_bytes(1024 ** 2)
    assert "GB" in format_bytes(1024 ** 3)


def test_format_uptime():
    from aura.utils import format_uptime
    assert format_uptime(0) == "00h 00m 00s"
    assert format_uptime(3661) == "01h 01m 01s"


def test_event_bus_publish_subscribe():
    from aura.utils import EventBus
    bus = EventBus()
    received = []
    bus.subscribe("test.event", lambda e, p: received.append((e, p)))
    bus.publish("test.event", {"key": "value"})
    assert len(received) == 1
    assert received[0] == ("test.event", {"key": "value"})


def test_event_bus_unsubscribe():
    from aura.utils import EventBus
    bus = EventBus()
    received = []
    cb = lambda e, p: received.append(p)
    bus.subscribe("ev", cb)
    bus.unsubscribe("ev", cb)
    bus.publish("ev", "data")
    assert len(received) == 0


# ---------------------------------------------------------------------------
# AI Engine — builtin backend
# ---------------------------------------------------------------------------

def test_builtin_backend_ready():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import BuiltinBackend
    be = BuiltinBackend(AIEngineConfig())
    assert be.is_ready() is True


def test_builtin_backend_known_query():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import BuiltinBackend
    be = BuiltinBackend(AIEngineConfig())
    resp = be.generate("show status")
    assert "Virtual" in resp.text or "Running" in resp.text
    assert resp.model == "aura-builtin-1.0"
    assert resp.latency_ms >= 0


def test_builtin_backend_fallback():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import BuiltinBackend
    be = BuiltinBackend(AIEngineConfig())
    resp = be.generate("xyzzy unique unknown query 12345")
    assert resp.text  # fallback is non-empty


def test_ai_engine_ask():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine
    engine = AIEngine(AIEngineConfig())
    resp = engine.ask("hello")
    assert resp.text
    assert len(engine.get_history()) == 2  # user + assistant


def test_ai_engine_history_clear():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine
    engine = AIEngine(AIEngineConfig())
    engine.ask("hello")
    engine.clear_history()
    assert engine.get_history() == []


def test_ai_engine_plan_task():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine
    engine = AIEngine(AIEngineConfig())
    resp = engine.plan_task("deploy a new cloud node")
    assert resp.text


def test_ai_engine_analyse_metrics():
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine
    engine = AIEngine(AIEngineConfig())
    resp = engine.analyse_metrics({"cpu_pct": 10, "memory_pct": 50})
    assert resp.text


# ---------------------------------------------------------------------------
# Virtual Cloud
# ---------------------------------------------------------------------------

def test_virtual_cloud_init():
    from aura.config import CloudConfig
    from aura.cloud.virtual_cloud import VirtualCloud
    cloud = VirtualCloud(CloudConfig(compute_nodes=4))
    nodes = cloud.list_nodes()
    assert len(nodes) == 4
    for n in nodes:
        assert n["status"] == "online"


def test_virtual_cloud_add_remove_node():
    from aura.config import CloudConfig
    from aura.cloud.virtual_cloud import VirtualCloud
    cloud = VirtualCloud(CloudConfig(compute_nodes=2))
    new_node = cloud.add_node(vcpus=4, memory_gb=8.0)
    assert new_node["vcpus"] == 4
    assert len(cloud.list_nodes()) == 3
    assert cloud.remove_node(new_node["node_id"]) is True
    assert len(cloud.list_nodes()) == 2


def test_virtual_cloud_volume_lifecycle():
    from aura.config import CloudConfig
    from aura.cloud.virtual_cloud import VirtualCloud
    cloud = VirtualCloud(CloudConfig(compute_nodes=1))
    vol = cloud.create_volume("test-vol", 10.0)
    assert vol["name"] == "test-vol"
    assert vol["size_gb"] == 10.0
    vols = cloud.list_volumes()
    assert any(v["volume_id"] == vol["volume_id"] for v in vols)
    assert cloud.delete_volume(vol["volume_id"]) is True
    assert not any(v["volume_id"] == vol["volume_id"] for v in cloud.list_volumes())


def test_virtual_cloud_model_registry():
    from aura.config import CloudConfig
    from aura.cloud.virtual_cloud import VirtualCloud
    cloud = VirtualCloud(CloudConfig(compute_nodes=1))
    m = cloud.register_model("m001", "test-model", 1_000_000, "builtin")
    assert m["model_name"] == "test-model"
    assert any(x["model_id"] == "m001" for x in cloud.list_models())


def test_virtual_cloud_metrics_structure():
    from aura.config import CloudConfig
    from aura.cloud.virtual_cloud import VirtualCloud
    cloud = VirtualCloud(CloudConfig(compute_nodes=3))
    m = cloud.metrics()
    assert m["nodes_total"] == 3
    assert "cpu_utilisation_pct" in m
    assert "memory_utilisation_pct" in m
    assert "region" in m


# ---------------------------------------------------------------------------
# Virtual CPU
# ---------------------------------------------------------------------------

def test_virtual_cpu_start_stop():
    from aura.config import CPUConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    cpu = VirtualCPU(CPUConfig(virtual_cores=2, max_concurrent_tasks=2))
    cpu.start()
    assert cpu._running is True
    cpu.stop()
    time.sleep(0.1)
    assert cpu._running is False


def test_virtual_cpu_submit_task():
    from aura.config import CPUConfig
    from aura.cpu.virtual_cpu import VirtualCPU, TaskStatus
    cpu = VirtualCPU(CPUConfig(virtual_cores=2, max_concurrent_tasks=2))
    cpu.start()
    done = threading.Event()
    def work():
        return 42
    tid = cpu.submit(work, name="test_work")
    # Poll for completion
    for _ in range(50):
        t = cpu.get_task(tid)
        if t and t["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    t = cpu.get_task(tid)
    assert t is not None
    assert t["status"] == "completed"
    cpu.stop()


def test_virtual_cpu_failed_task():
    from aura.config import CPUConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    cpu = VirtualCPU(CPUConfig(virtual_cores=2, max_concurrent_tasks=2))
    cpu.start()
    def boom():
        raise ValueError("test error")
    tid = cpu.submit(boom, name="fail_task")
    for _ in range(50):
        t = cpu.get_task(tid)
        if t and t["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    t = cpu.get_task(tid)
    assert t["status"] == "failed"
    assert "test error" in t["error"]
    cpu.stop()


def test_virtual_cpu_metrics():
    from aura.config import CPUConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    cpu = VirtualCPU(CPUConfig(virtual_cores=4))
    cpu.start()
    m = cpu.metrics()
    assert m["virtual_cores"] == 4
    assert "tasks_completed" in m
    assert "throughput_tps" in m
    cpu.stop()


# ---------------------------------------------------------------------------
# Virtual Server
# ---------------------------------------------------------------------------

def test_virtual_server_starts_and_responds():
    """Integration test: start the server and hit /health."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    # Use a non-conflicting port
    cfg = AURaConfig()
    cfg.server.port = 18432
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    cfg.cpu.max_concurrent_tasks = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18432)
        with urllib.request.urlopen("http://127.0.0.1:18432/health", timeout=5) as r:
            data = r.read().decode()
        assert "ok" in data


def test_virtual_server_api_metrics():
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18433
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18433)
        with urllib.request.urlopen("http://127.0.0.1:18433/api/v1/metrics", timeout=5) as r:
            data = json.loads(r.read())
        assert data["version"] == "1.0.0"
        assert "cloud" in data
        assert "cpu" in data


def test_virtual_server_ask_endpoint():
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18434
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18434)
        payload = json.dumps({"prompt": "hello"}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18434/api/v1/ask",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        assert "response" in data
        assert data["response"]


# ---------------------------------------------------------------------------
# AI OS — orchestration
# ---------------------------------------------------------------------------

def test_aios_start_stop():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18435
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    aios = AIOS(cfg)
    aios.start()
    assert aios._running is True
    s = aios.status()
    assert s["running"] is True
    aios.stop()
    assert aios._running is False


def test_aios_dispatch_status():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18436
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("status")
        assert "AURa" in out


def test_aios_dispatch_help():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18437
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("help")
        assert "ask" in out
        assert "status" in out


def test_aios_dispatch_ask():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18438
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("ask", ["hello"])
        assert out


def test_aios_dispatch_version():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18439
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("version")
        assert "1.0.0" in out


def test_aios_metrics_structure():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18440
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        m = aios.metrics()
        assert "cloud" in m
        assert "cpu" in m
        assert "server" in m
        assert m["version"] == "1.0.0"

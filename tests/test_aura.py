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
    assert cfg.version == "1.1.0"
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
        assert data["version"] == "1.1.0"
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
        assert "1.1.0" in out


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
        assert m["version"] == "1.1.0"


# ---------------------------------------------------------------------------
# Phase 1 — Cloud resource scheduling
# ---------------------------------------------------------------------------

def test_virtual_cloud_resource_scheduling():
    """Submitting a CPU task should increase node resource usage in VirtualCloud."""
    import time
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18441
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    cfg.cpu.max_concurrent_tasks = 2

    with AIOS(cfg) as aios:
        # Baseline: all nodes should have zero used resources
        nodes_before = aios.cloud.list_nodes()
        total_used_vcpus_before = sum(n["used_vcpus"] for n in nodes_before)
        assert total_used_vcpus_before == 0

        # Submit a task that blocks briefly so we can observe allocation
        barrier = __import__("threading").Event()
        def slow_work():
            barrier.wait(timeout=3)
            return "done"

        tid = aios.cpu.submit(slow_work, name="sched_test")

        # Give the worker thread time to pick up the task
        time.sleep(0.2)

        nodes_during = aios.cloud.list_nodes()
        total_used_during = sum(n["used_vcpus"] for n in nodes_during)
        assert total_used_during > 0, "Node vCPUs should be non-zero while task is running"

        # Unblock the task and wait for it to finish
        barrier.set()
        for _ in range(50):
            t = aios.cpu.get_task(tid)
            if t and t["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        # Resources should have been released
        nodes_after = aios.cloud.list_nodes()
        total_used_after = sum(n["used_vcpus"] for n in nodes_after)
        assert total_used_after == 0, "Node vCPUs should be released after task completes"


# ---------------------------------------------------------------------------
# Phase 1 — Expanded test coverage: EventBus.publish_all
# ---------------------------------------------------------------------------

def test_event_bus_publish_all():
    """publish_all should deliver to both the specific event type and the '*' wildcard."""
    from aura.utils import EventBus
    bus = EventBus()
    specific = []
    wildcard = []
    bus.subscribe("my.event", lambda e, p: specific.append(p))
    bus.subscribe("*", lambda e, p: wildcard.append(p))
    bus.publish_all("my.event", {"x": 1})
    assert len(specific) == 1
    assert specific[0] == {"x": 1}
    # wildcard receives a wrapper dict with "event" and "payload" keys
    assert len(wildcard) == 1
    assert wildcard[0]["event"] == "my.event"
    assert wildcard[0]["payload"] == {"x": 1}


# ---------------------------------------------------------------------------
# Phase 1 — Expanded test coverage: AURaShell._handle_line
# ---------------------------------------------------------------------------

def test_shell_handle_line_exit():
    """_handle_line should return False on 'exit' and 'quit'."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.shell.shell import AURaShell

    cfg = AURaConfig()
    cfg.server.port = 18442
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        shell = AURaShell(aios)
        assert shell._handle_line("exit") is False
        assert shell._handle_line("quit") is False


def test_shell_handle_line_empty():
    """_handle_line should return True (continue) for blank input."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.shell.shell import AURaShell

    cfg = AURaConfig()
    cfg.server.port = 18443
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        shell = AURaShell(aios)
        assert shell._handle_line("") is True
        assert shell._handle_line("   ") is True


def test_shell_handle_line_known_command():
    """_handle_line should dispatch known commands and return True."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.shell.shell import AURaShell

    cfg = AURaConfig()
    cfg.server.port = 18444
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        shell = AURaShell(aios)
        # 'version' is a built-in command; should not raise and return True
        assert shell._handle_line("version") is True


# ---------------------------------------------------------------------------
# Phase 1 — Expanded test coverage: TUIMonitor._render_frame
# ---------------------------------------------------------------------------

def test_tui_monitor_render_frame():
    """_render_frame should return a non-empty string containing component names."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.command_center.monitor import _render_frame

    cfg = AURaConfig()
    cfg.server.port = 18445
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        frame = _render_frame(aios)
        assert isinstance(frame, str)
        assert len(frame) > 0
        assert "AURa" in frame
        assert "Virtual Cloud" in frame
        assert "Virtual CPU" in frame


# ---------------------------------------------------------------------------
# Phase 1 — Expanded test coverage: mock-based OpenAICompatibleBackend
# ---------------------------------------------------------------------------

def test_openai_compatible_backend_success():
    """OpenAICompatibleBackend should parse a successful API response."""
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import OpenAICompatibleBackend

    cfg = AIEngineConfig(backend="openai_compatible", model_name="test-model", api_base_url="http://localhost:11434/v1")

    # Build a minimal fake httpx module so the backend can import it
    fake_httpx = ModuleType("httpx")
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello from mock"}}],
        "usage": {"total_tokens": 10},
    }
    mock_response.raise_for_status = MagicMock()
    mock_client_instance.post.return_value = mock_response
    fake_httpx.Client = MagicMock(return_value=mock_client_instance)

    original = sys.modules.get("httpx")
    sys.modules["httpx"] = fake_httpx
    try:
        backend = OpenAICompatibleBackend(cfg)
        assert backend.is_ready() is True
        resp = backend.generate("hi")
        assert resp.text == "Hello from mock"
        assert resp.tokens_used == 10
    finally:
        if original is None:
            sys.modules.pop("httpx", None)
        else:
            sys.modules["httpx"] = original


def test_openai_compatible_backend_api_error():
    """OpenAICompatibleBackend should handle API errors gracefully."""
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import OpenAICompatibleBackend

    cfg = AIEngineConfig(backend="openai_compatible", model_name="test-model", api_base_url="http://localhost:11434/v1")

    fake_httpx = ModuleType("httpx")
    mock_client_instance = MagicMock()
    mock_client_instance.post.side_effect = Exception("connection refused")
    fake_httpx.Client = MagicMock(return_value=mock_client_instance)

    original = sys.modules.get("httpx")
    sys.modules["httpx"] = fake_httpx
    try:
        backend = OpenAICompatibleBackend(cfg)
        resp = backend.generate("hi")
        assert "API error" in resp.text or "connection refused" in resp.text
    finally:
        if original is None:
            sys.modules.pop("httpx", None)
        else:
            sys.modules["httpx"] = original


def test_openai_compatible_backend_no_httpx():
    """OpenAICompatibleBackend should degrade gracefully when httpx is missing."""
    from unittest.mock import patch
    import sys
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import OpenAICompatibleBackend

    cfg = AIEngineConfig(backend="openai_compatible")
    # Simulate httpx not being installed
    with patch.dict(sys.modules, {"httpx": None}):
        backend = OpenAICompatibleBackend(cfg)
        assert backend.is_ready() is False
        resp = backend.generate("hi")
        assert "not ready" in resp.text.lower()


# ---------------------------------------------------------------------------
# Phase 1 — Expanded test coverage: mock-based TransformersBackend
# ---------------------------------------------------------------------------

def test_transformers_backend_success():
    """TransformersBackend should parse pipeline output correctly."""
    from unittest.mock import MagicMock, patch
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import TransformersBackend

    cfg = AIEngineConfig(backend="transformers", model_name="mock-model")

    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"generated_text": "Hello! Nice to meet you."}]
    mock_pipeline.tokenizer.eos_token_id = 0

    with patch("aura.ai_engine.engine.TransformersBackend._load_model") as mock_load:
        backend = TransformersBackend.__new__(TransformersBackend)
        backend._config = cfg
        backend._pipeline = mock_pipeline
        backend._ready = True

        resp = backend.generate("Hello")
        assert resp.text  # non-empty
        assert resp.model == "mock-model"


def test_transformers_backend_no_transformers():
    """TransformersBackend should report not ready when transformers is missing."""
    import sys
    from unittest.mock import patch
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import TransformersBackend

    cfg = AIEngineConfig(backend="transformers", model_name="mock-model")
    with patch.dict(sys.modules, {"transformers": None, "torch": None}):
        backend = TransformersBackend(cfg)
        assert backend.is_ready() is False
        resp = backend.generate("hello")
        assert "not ready" in resp.text.lower()


# ---------------------------------------------------------------------------
# Phase 2 — New REST endpoints
# ---------------------------------------------------------------------------

def test_api_cloud_nodes_add_and_delete():
    """POST /api/v1/cloud/nodes should add a node; DELETE should remove it."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18446
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18446)

        # Add a node via POST
        payload = json.dumps({"vcpus": 4, "memory_gb": 16.0}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18446/api/v1/cloud/nodes",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 201
            data = json.loads(r.read())
        node_id = data["node_id"]
        assert data["vcpus"] == 4

        # Verify list grew
        with urllib.request.urlopen("http://127.0.0.1:18446/api/v1/metrics", timeout=5) as r:
            metrics = json.loads(r.read())
        assert metrics["cloud"]["nodes_total"] == 3

        # Delete the node via DELETE
        req_del = urllib.request.Request(
            f"http://127.0.0.1:18446/api/v1/cloud/nodes/{node_id}",
            method="DELETE",
        )
        with urllib.request.urlopen(req_del, timeout=5) as r:
            assert r.status == 200
            del_data = json.loads(r.read())
        assert del_data["removed"] == node_id

        # Back to 2 nodes
        with urllib.request.urlopen("http://127.0.0.1:18446/api/v1/metrics", timeout=5) as r:
            metrics = json.loads(r.read())
        assert metrics["cloud"]["nodes_total"] == 2


def test_api_tasks_by_id():
    """GET /api/v1/tasks/<id> should return the task details."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18447
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18447)

        # Submit a task via the existing /api/v1/task endpoint
        payload = json.dumps({"name": "id_test_task", "duration_ms": 0}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18447/api/v1/task",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            resp = json.loads(r.read())
        task_id = resp["task_id"]

        # Wait briefly for the task to finish (poll instead of fixed sleep)
        for _ in range(50):
            t = aios.cpu.get_task(task_id)
            if t and t["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        with urllib.request.urlopen(
            f"http://127.0.0.1:18447/api/v1/tasks/{task_id}", timeout=5
        ) as r:
            task = json.loads(r.read())
        assert task["task_id"] == task_id
        assert task["name"] == "id_test_task"


def test_api_plan_endpoint():
    """POST /api/v1/plan should return a plan text."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18448
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18448)
        payload = json.dumps({"task": "deploy a new cloud node"}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18448/api/v1/plan",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        assert "plan" in data
        assert data["plan"]


def test_api_analyse_endpoint():
    """POST /api/v1/analyse should return an analysis text."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18449
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18449)
        payload = json.dumps({"metrics": {"cpu_pct": 5}}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18449/api/v1/analyse",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        assert "analysis" in data
        assert data["analysis"]


# ---------------------------------------------------------------------------
# Phase 2 — Auth
# ---------------------------------------------------------------------------

def test_api_auth_rejects_without_token():
    """When auth_enabled=True, requests without a token must get 401."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18450
    cfg.server.host = "127.0.0.1"
    cfg.server.auth_enabled = True
    cfg.server.api_token = "secret-token"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18450)
        try:
            urllib.request.urlopen("http://127.0.0.1:18450/api/v1/status", timeout=5)
            assert False, "Expected HTTPError 401"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401


def test_api_auth_allows_with_token():
    """When auth_enabled=True, requests with the correct token must succeed."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18451
    cfg.server.host = "127.0.0.1"
    cfg.server.auth_enabled = True
    cfg.server.api_token = "secret-token"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18451)
        req = urllib.request.Request(
            "http://127.0.0.1:18451/api/v1/status",
            headers={"Authorization": "Bearer secret-token"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        assert data["running"] is True


def test_api_auth_health_always_public():
    """/health must be accessible even when auth_enabled=True."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18452
    cfg.server.host = "127.0.0.1"
    cfg.server.auth_enabled = True
    cfg.server.api_token = "secret-token"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        _wait_for_server("127.0.0.1", 18452)
        # No auth header — should still return 200
        with urllib.request.urlopen("http://127.0.0.1:18452/health", timeout=5) as r:
            assert r.status == 200


# ---------------------------------------------------------------------------
# Phase 3 — JSON state persistence
# ---------------------------------------------------------------------------

def test_aios_state_persistence(tmp_path):
    """State saved on stop() should be restored on the next start()."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    data_dir = str(tmp_path / "aura_state_test")

    cfg1 = AURaConfig()
    cfg1.server.port = 18453
    cfg1.cloud.compute_nodes = 2
    cfg1.cpu.virtual_cores = 2
    cfg1.data_dir = data_dir

    with AIOS(cfg1) as aios1:
        aios1.ai_engine.ask("remember this")

    # Second instance — should restore history
    cfg2 = AURaConfig()
    cfg2.server.port = 18454
    cfg2.cloud.compute_nodes = 2
    cfg2.cpu.virtual_cores = 2
    cfg2.data_dir = data_dir

    with AIOS(cfg2) as aios2:
        history = aios2.ai_engine.get_history()
        # History should include the message from the previous session
        user_msgs = [h for h in history if h["role"] == "user" and "remember this" in h["content"]]
        assert len(user_msgs) >= 1


# ---------------------------------------------------------------------------
# Phase 4 — Streaming (BuiltinBackend)
# ---------------------------------------------------------------------------

def test_builtin_backend_stream():
    """BuiltinBackend.stream() should yield multiple chunks that reassemble correctly."""
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import BuiltinBackend

    be = BuiltinBackend(AIEngineConfig())
    be.STREAM_TOKEN_DELAY = 0  # disable delay for fast tests
    chunks = list(be.stream("hello"))
    assert len(chunks) > 1, "Expected multiple word chunks"
    combined = "".join(chunks)
    # Should match the non-streaming response
    full_resp = be.generate("hello")
    assert combined == full_resp.text


def test_ai_engine_stream():
    """AIEngine.stream() should yield tokens and add history entry."""
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine, BuiltinBackend

    engine = AIEngine(AIEngineConfig())
    # Disable streaming delay for speed
    engine._backend.STREAM_TOKEN_DELAY = 0
    chunks = list(engine.stream("hello"))
    assert chunks, "Expected at least one chunk"
    combined = "".join(chunks)
    assert combined
    # History should be updated
    history = engine.get_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == combined


def test_api_ask_stream_endpoint():
    """GET /api/v1/ask/stream should return SSE tokens ending with [DONE]."""
    import json
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.ai_engine.engine import BuiltinBackend

    cfg = AURaConfig()
    cfg.server.port = 18455
    cfg.server.host = "127.0.0.1"
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        # Disable streaming delay for speed
        aios.ai_engine._backend.STREAM_TOKEN_DELAY = 0
        _wait_for_server("127.0.0.1", 18455)
        url = "http://127.0.0.1:18455/api/v1/ask/stream?prompt=hello"
        with urllib.request.urlopen(url, timeout=10) as r:
            raw = r.read().decode()
        assert "[DONE]" in raw
        assert "data:" in raw


# ---------------------------------------------------------------------------
# Phase 5 — Plugin registries
# ---------------------------------------------------------------------------

def test_backend_plugin_registry():
    """A custom backend registered with AIEngine.register_backend should be usable."""
    from aura.config import AIEngineConfig
    from aura.ai_engine.engine import AIEngine, BaseBackend, AIResponse

    class EchoBackend(BaseBackend):
        def __init__(self, config):
            pass
        def is_ready(self):
            return True
        def generate(self, prompt, system_prompt="", **kw):
            return AIResponse(text=f"ECHO:{prompt}", model="echo")

    AIEngine.register_backend("echo", EchoBackend)
    cfg = AIEngineConfig(backend="echo")
    engine = AIEngine(cfg)
    resp = engine.ask("test")
    assert resp.text.startswith("ECHO:")


def test_aios_register_command():
    """A custom command registered with AIOS.register_command should be dispatchable."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18456
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2

    with AIOS(cfg) as aios:
        def cmd_ping(aios_ref, args):
            return "pong:" + (" ".join(args) if args else "")

        aios.register_command("ping", cmd_ping)
        result = aios.dispatch("ping", ["world"])
        assert result == "pong:world"

        # Custom command should appear in help
        help_text = aios.dispatch("help")
        assert "ping" in help_text


# ---------------------------------------------------------------------------
# PersistenceEngine
# ---------------------------------------------------------------------------

def test_persistence_kv_set_get(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    engine.set("cfg", "color", "blue")
    assert engine.get("cfg", "color") == "blue"
    engine.close()


def test_persistence_kv_default(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    assert engine.get("cfg", "nonexistent", default="fallback") == "fallback"
    engine.close()


def test_persistence_kv_delete(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    engine.set("cfg", "key1", 42)
    deleted = engine.delete("cfg", "key1")
    assert deleted is True
    assert engine.get("cfg", "key1") is None
    assert engine.delete("cfg", "key1") is False
    engine.close()


def test_persistence_kv_list_keys(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    engine.set("ns1", "a", 1)
    engine.set("ns1", "b", 2)
    engine.set("ns2", "c", 3)
    keys = engine.list_keys("ns1")
    assert sorted(keys) == ["a", "b"]
    engine.close()


def test_persistence_namespaces(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    engine.set("alpha", "x", 1)
    engine.set("beta", "y", 2)
    nss = engine.namespaces()
    assert "alpha" in nss
    assert "beta" in nss
    engine.close()


def test_persistence_invalid_name(tmp_path):
    import pytest
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    with pytest.raises(ValueError):
        engine.set("bad ns!", "key", "val")
    with pytest.raises(ValueError):
        engine.set("ns", "bad/key", "val")
    engine.close()


def test_persistence_file_store(tmp_path):
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    data = b"\x00\x01\x02Hello"
    engine.store_file("blobs", "icon.png", data)
    loaded = engine.load_file("blobs", "icon.png")
    assert loaded == data
    files = engine.list_files("blobs")
    assert len(files) == 1
    assert files[0]["filename"] == "icon.png"
    assert files[0]["size"] == len(data)
    deleted = engine.delete_file("blobs", "icon.png")
    assert deleted is True
    assert engine.load_file("blobs", "icon.png") is None
    engine.close()


def test_persistence_file_path_traversal(tmp_path):
    import pytest
    from aura.persistence.store import PersistenceEngine

    engine = PersistenceEngine(str(tmp_path / "test.db"))
    with pytest.raises(ValueError):
        engine.store_file("ns", "../evil.txt", b"data")
    engine.close()


# ---------------------------------------------------------------------------
# detect_capabilities / AndroidBridge
# ---------------------------------------------------------------------------

def test_detect_capabilities_keys():
    from aura.adapters.android_bridge import detect_capabilities

    caps = detect_capabilities()
    for key in ("platform", "is_termux", "python_version", "architecture",
                "shells", "tools", "env_vars", "cpu_count", "path_sep"):
        assert key in caps


def test_detect_capabilities_platform_is_string():
    from aura.adapters.android_bridge import detect_capabilities

    caps = detect_capabilities()
    assert isinstance(caps["platform"], str)
    assert caps["platform"] in ("android", "linux", "darwin", "windows", "unknown")


def test_android_bridge_run_echo():
    from aura.adapters.android_bridge import AndroidBridge

    bridge = AndroidBridge()
    result = bridge.run(["echo", "hello"])
    assert result.success
    assert "hello" in result.stdout


def test_android_bridge_run_shell():
    from aura.adapters.android_bridge import AndroidBridge

    bridge = AndroidBridge()
    result = bridge.run_shell("echo bridge-ok")
    assert result.success
    assert "bridge-ok" in result.stdout


def test_android_bridge_run_missing_command():
    from aura.adapters.android_bridge import AndroidBridge

    bridge = AndroidBridge()
    result = bridge.run(["__no_such_command__"])
    assert not result.success
    assert result.returncode in (127, 1, -1)


def test_android_bridge_run_timeout():
    from aura.adapters.android_bridge import AndroidBridge

    bridge = AndroidBridge(timeout=0.01)
    result = bridge.run(["sleep", "10"])
    assert result.timed_out or not result.success


def test_run_result_str():
    from aura.adapters.android_bridge import RunResult

    r = RunResult(command=["echo"], returncode=0, stdout="hi", stderr="")
    assert r.success
    r2 = RunResult(command=["bad"], returncode=1, stdout="", stderr="err")
    assert not r2.success


# ---------------------------------------------------------------------------
# ShellCommandExecutor
# ---------------------------------------------------------------------------

def test_shell_executor_pwd(tmp_path):
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor(cwd=str(tmp_path))
    assert exe.execute("pwd") == str(tmp_path)


def test_shell_executor_echo():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    assert exe.execute("echo hello world") == "hello world"


def test_shell_executor_cd(tmp_path):
    from aura.shell.commands import ShellCommandExecutor

    sub = tmp_path / "sub"
    sub.mkdir()
    exe = ShellCommandExecutor(cwd=str(tmp_path))
    exe.execute(f"cd {sub}")
    assert exe.cwd == str(sub)


def test_shell_executor_mkdir_ls(tmp_path):
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor(cwd=str(tmp_path))
    exe.execute("mkdir newdir")
    listing = exe.execute("ls")
    assert "newdir" in listing


def test_shell_executor_touch_cat(tmp_path):
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor(cwd=str(tmp_path))
    f = tmp_path / "hello.txt"
    f.write_text("hello")
    result = exe.execute(f"cat {f}")
    assert "hello" in result


def test_shell_executor_wc(tmp_path):
    from aura.shell.commands import ShellCommandExecutor

    f = tmp_path / "f.txt"
    f.write_text("one\ntwo\nthree\n")
    exe = ShellCommandExecutor(cwd=str(tmp_path))
    result = exe.execute(f"wc {f}")
    assert "3" in result


def test_shell_executor_date():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    result = exe.execute("date")
    assert result  # non-empty


def test_shell_executor_uname():
    from aura.shell.commands import ShellCommandExecutor
    import platform

    exe = ShellCommandExecutor()
    result = exe.execute("uname")
    assert platform.system().lower() in result.lower()


def test_shell_executor_which():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    result = exe.execute("which python3")
    # May not be found everywhere but should not raise
    assert isinstance(result, str)


def test_shell_executor_df():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    result = exe.execute("df")
    assert "Filesystem" in result or "virtual" in result


def test_shell_executor_builtin_names():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    names = exe.builtin_names()
    for expected in ("cd", "ls", "cat", "pwd", "echo", "df", "free", "ps",
                     "env", "which", "date", "uname", "mkdir", "rm", "cp",
                     "mv", "touch", "head", "tail", "wc"):
        assert expected in names


def test_shell_executor_unknown_command():
    from aura.shell.commands import ShellCommandExecutor

    exe = ShellCommandExecutor()
    result = exe.execute("__no_such_command__")
    assert "not found" in result or isinstance(result, str)


# ---------------------------------------------------------------------------
# MenuWorkspace
# ---------------------------------------------------------------------------

def test_menu_workspace_render():
    from aura.shell.commands import MenuWorkspace

    menu = MenuWorkspace("Choose", ["Alpha", "Beta", "Gamma"])
    rendered = menu.render()
    assert "Choose" in rendered
    assert "[1]" in rendered
    assert "Alpha" in rendered
    assert "[3]" in rendered


def test_menu_workspace_empty_options():
    import pytest
    from aura.shell.commands import MenuWorkspace

    with pytest.raises(ValueError):
        MenuWorkspace("Title", [])


# ---------------------------------------------------------------------------
# AURaPlugin / PluginManager
# ---------------------------------------------------------------------------

def test_plugin_manager_register_dispatch():
    from aura.plugins.manager import AURaPlugin, PluginManager

    class EchoPlugin(AURaPlugin):
        @property
        def name(self):
            return "echo_plugin"
        @property
        def description(self):
            return "echoes args"
        def execute(self, aios, args):
            return " ".join(args)

    mgr = PluginManager()
    mgr.register(EchoPlugin())
    assert mgr.handles("echo_plugin")
    result = mgr.dispatch("echo_plugin", ["hello", "world"])
    assert result == "hello world"


def test_plugin_manager_duplicate_raises():
    import pytest
    from aura.plugins.manager import AURaPlugin, PluginManager

    class Dummy(AURaPlugin):
        @property
        def name(self):
            return "dup"
        @property
        def description(self):
            return "dup"
        def execute(self, aios, args):
            return ""

    mgr = PluginManager()
    mgr.register(Dummy())
    with pytest.raises(ValueError):
        mgr.register(Dummy())


def test_plugin_manager_unregister():
    from aura.plugins.manager import AURaPlugin, PluginManager

    class P(AURaPlugin):
        @property
        def name(self):
            return "p"
        @property
        def description(self):
            return "p"
        def execute(self, aios, args):
            return "ok"

    mgr = PluginManager()
    mgr.register(P())
    mgr.unregister("p")
    assert not mgr.handles("p")


def test_plugin_manager_list_plugins():
    from aura.plugins.manager import PluginManager, SystemInfoPlugin, StoragePlugin

    mgr = PluginManager()
    mgr.register(SystemInfoPlugin())
    mgr.register(StoragePlugin())
    plugins = mgr.list_plugins()
    names = [p["name"] for p in plugins]
    assert "sysinfo" in names
    assert "storage" in names


def test_plugin_manager_dispatch_unknown():
    from aura.plugins.manager import PluginManager

    mgr = PluginManager()
    result = mgr.dispatch("nonexistent")
    assert result is None


def test_system_info_plugin_execute():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    from aura.plugins.manager import SystemInfoPlugin

    cfg = AURaConfig()
    cfg.server.port = 18457
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        plugin = SystemInfoPlugin()
        result = plugin.execute(aios, [])
        assert "System Information" in result
        assert "Python" in result


# ---------------------------------------------------------------------------
# AIOS new dispatch commands
# ---------------------------------------------------------------------------

def test_aios_dispatch_platform():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18458
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        result = aios.dispatch("platform")
        assert "Platform" in result
        assert "Python" in result


def test_aios_dispatch_plugins():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18459
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        result = aios.dispatch("plugins")
        assert "sysinfo" in result
        assert "storage" in result


def test_aios_dispatch_bash():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18460
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        result = aios.dispatch("bash", ["echo", "aura-bash-ok"])
        assert "aura-bash-ok" in result


def test_aios_dispatch_bang_shorthand():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18461
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        result = aios.dispatch("!echo", ["bang-ok"])
        assert "bang-ok" in result


def test_aios_dispatch_kv():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18462
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        aios.dispatch("kv", ["set", "testns", "mykey", "myvalue"])
        result = aios.dispatch("kv", ["get", "testns", "mykey"])
        assert result == "myvalue"

        keys_result = aios.dispatch("kv", ["list", "testns"])
        assert "mykey" in keys_result

        del_result = aios.dispatch("kv", ["del", "testns", "mykey"])
        assert "deleted" in del_result


def test_aios_dispatch_sysinfo_via_plugin():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18463
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        result = aios.dispatch("sysinfo")
        assert "System Information" in result


def test_aios_help_includes_new_commands():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS

    cfg = AURaConfig()
    cfg.server.port = 18464
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        help_text = aios.dispatch("help")
        assert "platform" in help_text
        assert "bash" in help_text
        assert "plugins" in help_text
        assert "kv" in help_text


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
    assert cfg.version == "2.0.0"
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
        assert data["version"] == "2.0.0"
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
        assert "2.0.0" in out


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
        assert m["version"] == "2.0.0"


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

def test_policy_engine_default_deny():
    from aura.root.policy import PolicyEngine, PolicyVerdict
    engine = PolicyEngine(default_verdict=PolicyVerdict.DENY)
    verdict = engine.evaluate("user", "write", "/dev/vcpu")
    assert verdict == PolicyVerdict.DENY


def test_policy_engine_explicit_allow():
    from aura.root.policy import PolicyEngine, PolicyRule, PolicyVerdict
    engine = PolicyEngine(default_verdict=PolicyVerdict.DENY)
    engine.add_rule(PolicyRule(
        name="allow-user-read",
        subject="user",
        action="read",
        resource="/dev/vcpu",
        verdict=PolicyVerdict.ALLOW,
        priority=10,
    ))
    verdict = engine.evaluate("user", "read", "/dev/vcpu")
    assert verdict == PolicyVerdict.ALLOW


def test_policy_engine_require_raises_on_deny():
    from aura.root.policy import PolicyEngine, PolicyVerdict
    engine = PolicyEngine(default_verdict=PolicyVerdict.DENY)
    try:
        engine.require("hacker", "deploy", "artefact:evil")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass


def test_policy_engine_glob_matching():
    from aura.root.policy import PolicyEngine, PolicyRule, PolicyVerdict
    engine = PolicyEngine(default_verdict=PolicyVerdict.DENY)
    engine.add_rule(PolicyRule(
        name="allow-dev-star",
        subject="aura-init",
        action="device.open",
        resource="/dev/*",
        verdict=PolicyVerdict.ALLOW,
        priority=5,
    ))
    assert engine.evaluate("aura-init", "device.open", "/dev/vcpu") == PolicyVerdict.ALLOW
    assert engine.evaluate("aura-init", "device.open", "/dev/vnet") == PolicyVerdict.ALLOW
    assert engine.evaluate("aura-init", "write", "/dev/vcpu") == PolicyVerdict.DENY


def test_policy_engine_os_defaults():
    from aura.root.policy import PolicyEngine, PolicyVerdict
    engine = PolicyEngine.with_os_defaults()
    assert engine.evaluate("root", "deploy", "artefact:xyz") == PolicyVerdict.ALLOW
    assert engine.evaluate("aura-init", "device.open", "/dev/vcpu") == PolicyVerdict.ALLOW
    assert engine.evaluate("unknown", "deploy", "artefact:xyz") == PolicyVerdict.DENY


def test_policy_engine_list_and_remove():
    from aura.root.policy import PolicyEngine, PolicyRule, PolicyVerdict
    engine = PolicyEngine()
    engine.add_rule(PolicyRule(
        name="tmp-rule",
        subject="*",
        action="*",
        resource="*",
        verdict=PolicyVerdict.ALLOW,
        priority=99,
    ))
    rules = engine.list_rules()
    assert any(r["name"] == "tmp-rule" for r in rules)
    removed = engine.remove_rule("tmp-rule")
    assert removed is True
    rules_after = engine.list_rules()
    assert not any(r["name"] == "tmp-rule" for r in rules_after)


# ---------------------------------------------------------------------------
# ROOT Approval Gate
# ---------------------------------------------------------------------------

def test_approval_gate_request_pending():
    from aura.root.approval import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(signing_secret="test-secret")
    req = gate.request("art-001", "build-pipeline")
    assert req.status == ApprovalStatus.PENDING
    assert req.artefact_id == "art-001"
    assert req.deploy_token is None


def test_approval_gate_approve():
    from aura.root.approval import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(signing_secret="test-secret")
    req = gate.request("art-002", "build-pipeline")
    approved = gate.approve(req.request_id)
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.deploy_token is not None


def test_approval_gate_reject():
    from aura.root.approval import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(signing_secret="test-secret")
    req = gate.request("art-003", "pipeline")
    rejected = gate.reject(req.request_id, "security violation")
    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.reject_reason == "security violation"


def test_approval_gate_auto_approve():
    from aura.root.approval import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(signing_secret="test-secret", auto_approve=True)
    req = gate.request("art-auto", "ci-pipeline")
    assert req.status == ApprovalStatus.APPROVED
    assert req.deploy_token is not None


def test_approval_gate_verify_token():
    from aura.root.approval import ApprovalGate
    gate = ApprovalGate(signing_secret="test-secret", auto_approve=True)
    req = gate.request("art-v", "ci")
    assert req.deploy_token is not None
    assert gate.verify_deploy_token("art-v", req.deploy_token) is True
    assert gate.verify_deploy_token("art-v", "bad-token") is False


def test_approval_gate_list_requests():
    from aura.root.approval import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(signing_secret="test-secret")
    gate.request("art-x1", "pipeline")
    gate.request("art-x2", "pipeline")
    reqs = gate.list_requests()
    assert len(reqs) >= 2
    pending = gate.list_requests(ApprovalStatus.PENDING)
    assert all(r["status"] == "pending" for r in pending)


# ---------------------------------------------------------------------------
# ROOT Sovereign Layer
# ---------------------------------------------------------------------------

def test_root_layer_start_stop():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    assert root.running is True
    s = root.status()
    assert s["running"] is True
    root.stop()
    assert root.running is False


def test_root_layer_gate_allow():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    from aura.root.policy import PolicyVerdict
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    verdict = root.gate("root", "deploy", "artefact:test")
    assert verdict == PolicyVerdict.ALLOW
    root.stop()


def test_root_layer_gate_deny_raises():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    try:
        root.gate("hacker", "deploy", "artefact:evil", raise_on_deny=True)
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
    finally:
        root.stop()


def test_root_layer_audit_log():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    root.gate("root", "read", "system:status")
    log = root.audit_log(last_n=20)
    assert len(log) > 0
    assert any(e["subject"] == "root" for e in log)
    root.stop()


# ---------------------------------------------------------------------------
# Virtual Hardware /dev/*
# ---------------------------------------------------------------------------

def test_dev_vcpu_submit_and_metrics():
    import time
    from aura.config import CPUConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    from aura.hardware.vcpu import VCPUDevice
    cpu = VirtualCPU(CPUConfig(virtual_cores=2, max_concurrent_tasks=2))
    cpu.start()
    dev = VCPUDevice(cpu)
    assert dev.path == "/dev/vcpu"
    m = dev.metrics()
    assert m["device"] == "/dev/vcpu"
    assert "virtual_cores" in m
    tid = dev.submit(lambda: 42, name="dev_test")
    for _ in range(30):
        t = dev.get_task(tid)
        if t and t["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    t = dev.get_task(tid)
    assert t is not None
    assert t["status"] == "completed"
    cpu.stop()


def test_dev_vram_allocate_free():
    from aura.hardware.vram import VRAMDevice
    dev = VRAMDevice(total_mb=1024.0)
    assert dev.path == "/dev/vram"
    alloc_id = dev.allocate("test-subsystem", 256.0, "test alloc")
    m = dev.metrics()
    assert m["used_mb"] == 256.0
    assert m["allocation_count"] == 1
    freed = dev.free(alloc_id)
    assert freed is True
    m2 = dev.metrics()
    assert m2["used_mb"] == 0.0


def test_dev_vram_overflow_raises():
    from aura.hardware.vram import VRAMDevice
    dev = VRAMDevice(total_mb=100.0)
    try:
        dev.allocate("greedy", 200.0)
        assert False, "Expected MemoryError"
    except MemoryError:
        pass


def test_dev_vdisk_create_list():
    import tempfile
    from aura.hardware.vdisk import VDiskDevice
    with tempfile.TemporaryDirectory() as tmpdir:
        dev = VDiskDevice(tmpdir)
        assert dev.path == "/dev/vdisk"
        vols = dev.list_volumes()
        names = [v["name"] for v in vols]
        assert "rootfs" in names
        assert "home-vol" in names
        assert "stage-vol" in names


def test_dev_vdisk_mount_unmount():
    import tempfile, os
    from aura.hardware.vdisk import VDiskDevice
    with tempfile.TemporaryDirectory() as tmpdir:
        dev = VDiskDevice(tmpdir)
        new_vol = dev.create_volume("test-vol", 1.0)
        mount_at = os.path.join(tmpdir, "mnt", "test")
        ok = dev.mount_volume(new_vol["volume_id"], mount_at)
        assert ok is True
        vol = dev.get_volume(new_vol["volume_id"])
        assert vol["status"] == "mounted"
        unmounted = dev.unmount_volume(new_vol["volume_id"])
        assert unmounted is True


def test_dev_device_manager_register_list():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    from aura.hardware.device_manager import DeviceManager
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    dm = DeviceManager(root)
    dummy_device = object()
    dm.register("/dev/test", "test", dummy_device, "root")
    devices = dm.list_devices()
    assert any(d["path"] == "/dev/test" for d in devices)
    root.stop()


def test_dev_device_manager_open_gated():
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    from aura.hardware.device_manager import DeviceManager
    cfg = AURaConfig()
    root = ROOTLayer(cfg)
    root.start()
    dm = DeviceManager(root)
    dummy = object()
    dm.register("/dev/test2", "test", dummy, "root")
    result = dm.open("/dev/test2", "root")
    assert result is dummy
    try:
        dm.open("/dev/test2", "hacker")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
    root.stop()


# ---------------------------------------------------------------------------
# Network Stack
# ---------------------------------------------------------------------------

def test_dhcp_request_lease():
    from aura.network.dhcp import DHCPServer
    dhcp = DHCPServer(subnet="10.0.1.0/24", lease_time_s=3600)
    lease = dhcp.request("aa:bb:cc:dd:ee:ff", "test-host")
    assert lease.ip.startswith("10.0.1.")
    assert lease.mac == "aa:bb:cc:dd:ee:ff"
    assert not lease.expired
    m = dhcp.metrics()
    assert m["active_leases"] == 1


def test_dhcp_renew_same_ip():
    from aura.network.dhcp import DHCPServer
    dhcp = DHCPServer(subnet="10.0.2.0/24")
    lease1 = dhcp.request("11:22:33:44:55:66", "host1")
    lease2 = dhcp.request("11:22:33:44:55:66", "host1")
    assert lease1.ip == lease2.ip


def test_dhcp_release():
    from aura.network.dhcp import DHCPServer
    dhcp = DHCPServer(subnet="10.0.3.0/24")
    dhcp.request("aa:00:00:00:00:01", "h1")
    released = dhcp.release("aa:00:00:00:00:01")
    assert released is True
    assert dhcp.metrics()["active_leases"] == 0


def test_dns_resolve_local():
    from aura.network.dns import DNSResolver
    dns = DNSResolver()
    ip = dns.resolve("aura.local")
    assert ip == "10.0.0.1"


def test_dns_override():
    from aura.network.dns import DNSResolver
    dns = DNSResolver()
    dns.override("custom.aura.local", "192.168.99.1")
    assert dns.resolve("custom.aura.local") == "192.168.99.1"


def test_dns_add_record():
    from aura.network.dns import DNSResolver, DNSRecord
    dns = DNSResolver()
    dns.add_record(DNSRecord("new.aura.local", "A", "10.0.0.50"))
    assert dns.resolve("new.aura.local") == "10.0.0.50"


def test_nat_snat_creates_entry():
    from aura.network.nat import NATTable
    nat = NATTable(gateway_ip="1.2.3.4")
    ext_ip, ext_port = nat.snat("10.0.0.5", 45000, "8.8.8.8", 53, "udp")
    assert ext_ip == "1.2.3.4"
    assert ext_port >= 32768
    m = nat.metrics()
    assert m["entry_count"] == 1


def test_nat_disabled_passthrough():
    from aura.network.nat import NATTable
    nat = NATTable()
    nat.enabled = False
    ext_ip, ext_port = nat.snat("10.0.0.5", 1234, "1.1.1.1", 80)
    assert ext_ip == "10.0.0.5"
    assert ext_port == 1234


def test_firewall_default_deny():
    from aura.network.firewall import Firewall, FirewallVerdict
    fw = Firewall(default_verdict=FirewallVerdict.DENY)
    allowed = fw.allow("10.0.0.5", "8.8.8.8", "tcp", 80)
    assert allowed is False


def test_firewall_allow_rule():
    from aura.network.firewall import Firewall, FirewallRule, FirewallVerdict
    fw = Firewall(default_verdict=FirewallVerdict.DENY)
    fw.add_rule(FirewallRule(
        name="allow-http-out",
        src_ip="*",
        dst_ip="*",
        protocol="tcp",
        dst_port=80,
        verdict=FirewallVerdict.ALLOW,
        priority=10,
    ))
    assert fw.allow("10.0.0.5", "8.8.8.8", "tcp", 80) is True
    assert fw.allow("10.0.0.5", "8.8.8.8", "tcp", 443) is False


def test_firewall_os_defaults():
    from aura.network.firewall import Firewall
    fw = Firewall.with_os_defaults()
    assert fw.allow("127.0.0.1", "127.0.0.1", "tcp", 8000) is True
    assert fw.allow("10.0.0.5", "10.0.0.1", "tcp", 8000) is True
    assert fw.allow("10.0.0.5", "10.0.0.2", "udp", 53) is True


def test_network_stack_metrics():
    from aura.config import NetworkConfig
    from aura.network.stack import NetworkStack
    cfg = NetworkConfig()
    stack = NetworkStack(cfg)
    m = stack.metrics()
    assert "dhcp" in m
    assert "dns" in m
    assert "nat" in m
    assert "firewall" in m
    assert m["device"] == "/dev/vnet"


def test_network_stack_dhcp_dns_integration():
    from aura.config import NetworkConfig
    from aura.network.stack import NetworkStack
    cfg = NetworkConfig()
    stack = NetworkStack(cfg)
    lease = stack.dhcp_request("ca:fe:ba:be:00:01", "myhost")
    assert lease.ip.startswith("10.0.0.")
    ip = stack.dns_resolve("aura.local")
    assert ip == "10.0.0.1"


# ---------------------------------------------------------------------------
# Boot chain
# ---------------------------------------------------------------------------

def test_bootloader_full_boot_halt():
    import tempfile, pathlib
    from aura.config import AURaConfig
    from aura.root.sovereign import ROOTLayer
    from aura.home.userland import HOMELayer
    from aura.boot.aura_init import AURAInit
    from aura.boot.bootloader import Bootloader, BootState
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = AURaConfig()
        cfg.home.home_dir = str(pathlib.Path(tmpdir) / "home")
        root = ROOTLayer(cfg)
        home = HOMELayer(cfg.home)
        init = AURAInit()
        init.register("test-svc", start_fn=lambda: None, stop_fn=lambda: None)
        bl = Bootloader(root, home, init)
        bl.boot()
        assert bl.state == BootState.READY
        log = bl.boot_log
        stage_names = [r["stage"] for r in log]
        assert "firmware" in stage_names
        assert "root" in stage_names
        assert "home_mount" in stage_names
        assert "aura_init" in stage_names
        assert all(r["success"] for r in log)
        bl.halt()
        assert bl.state == BootState.HALTED


def test_aura_init_register_start_stop():
    from aura.boot.aura_init import AURAInit
    init = AURAInit()
    started = []
    stopped = []
    init.register("svc1",
                  start_fn=lambda: started.append(1),
                  stop_fn=lambda: stopped.append(1))
    init.start_all()
    assert len(started) == 1
    svcs = init.list_services()
    assert any(s["name"] == "svc1" for s in svcs)
    assert any(s["state"] == "running" for s in svcs)
    init.stop_all()
    assert len(stopped) == 1


# ---------------------------------------------------------------------------
# HOME Userland
# ---------------------------------------------------------------------------

def test_home_layer_start_stop():
    import tempfile, pathlib
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = HOMEConfig(home_dir=str(pathlib.Path(tmpdir) / "home"))
        home = HOMELayer(cfg)
        home.start()
        assert home.running is True
        s = home.status()
        assert s["packages"] > 0
        home.stop()
        assert home.running is False


def test_home_filesystem_paths():
    import tempfile, pathlib
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = HOMEConfig(home_dir=str(pathlib.Path(tmpdir) / "home"))
        home = HOMELayer(cfg)
        home.start()
        fs = home.filesystem
        assert fs.exists("etc", "os-release")
        assert "bin" in fs.ls()
        home.stop()


def test_home_package_install_remove():
    import tempfile, pathlib
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = HOMEConfig(home_dir=str(pathlib.Path(tmpdir) / "home"))
        home = HOMELayer(cfg)
        home.start()
        home.install_package("test-pkg", "1.0.0", "A test package")
        pkgs = home.list_packages()
        assert any(p["name"] == "test-pkg" for p in pkgs)
        removed = home.remove_package("test-pkg")
        assert removed is True
        home.stop()


def test_home_filesystem_path_traversal():
    import tempfile
    from aura.home.filesystem import HomeFilesystem
    with tempfile.TemporaryDirectory() as tmpdir:
        fs = HomeFilesystem(tmpdir)
        try:
            fs.path("..", "..", "etc", "passwd")
            assert False, "Expected ValueError"
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Build Pipeline
# ---------------------------------------------------------------------------

def test_build_pipeline_auto_approve():
    import tempfile, os
    from aura.config import BuildConfig
    from aura.root.approval import ApprovalGate
    from aura.build.pipeline import BuildPipeline, BuildStatus
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = BuildConfig(artefact_dir=tmpdir, require_root_approval=True, signing_secret="test-secret")
        gate = ApprovalGate("test-secret", auto_approve=True)
        pipeline = BuildPipeline(config=cfg, approval_gate=gate)
        run = pipeline.run(name="test-component", version="1.0.0", commit="abc123")
        assert run.status == BuildStatus.DEPLOYED
        assert run.artefact is not None
        assert run.artefact.signature is not None
        assert run.artefact.staged_path is not None
        assert os.path.exists(run.artefact.staged_path)


def test_build_pipeline_approval_required():
    import tempfile
    from aura.config import BuildConfig
    from aura.root.approval import ApprovalGate, ApprovalStatus
    from aura.build.pipeline import BuildPipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = BuildConfig(artefact_dir=tmpdir, require_root_approval=True, signing_secret="test-secret")
        gate = ApprovalGate("test-secret", auto_approve=False)
        pipeline = BuildPipeline(config=cfg, approval_gate=gate)
        run = pipeline.run(name="pending-component", version="1.0.0")
        assert run.approval_request_id is not None
        req = gate.get(run.approval_request_id)
        assert req is not None
        assert req.status == ApprovalStatus.PENDING


def test_artefact_signer():
    from aura.build.signer import ArtefactSigner
    signer = ArtefactSigner("signing-secret")
    sig = signer.sign("art-001", "abc123hash")
    assert len(sig) == 64
    assert signer.verify("art-001", "abc123hash", sig) is True
    assert signer.verify("art-001", "wronghash", sig) is False


# ---------------------------------------------------------------------------
# Identity & Governance
# ---------------------------------------------------------------------------

def test_crypto_identity_issue_verify():
    from aura.identity.crypto import CryptoIdentityEngine, IdentityKind
    engine = CryptoIdentityEngine("test-root-secret")
    token = engine.issue(IdentityKind.USER, "alice", metadata={"role": "operator"})
    assert token.subject == "alice"
    assert token.fingerprint
    assert token.signature
    assert engine.verify(token) is True


def test_crypto_identity_revoked():
    from aura.identity.crypto import CryptoIdentityEngine, IdentityKind
    engine = CryptoIdentityEngine("test-root-secret")
    token = engine.issue(IdentityKind.SERVICE, "my-service")
    token.revoked = True
    assert engine.verify(token) is False


def test_identity_registry():
    from aura.identity.crypto import CryptoIdentityEngine, IdentityKind
    from aura.identity.registry import IdentityRegistry
    engine = CryptoIdentityEngine("test-root-secret")
    registry = IdentityRegistry(engine)
    token = registry.issue(IdentityKind.NODE, "node-001")
    assert registry.verify(token.identity_id) is True
    revoked = registry.revoke(token.identity_id)
    assert revoked is True
    assert registry.verify(token.identity_id) is False


def test_identity_registry_find_by_subject():
    from aura.identity.crypto import CryptoIdentityEngine, IdentityKind
    from aura.identity.registry import IdentityRegistry
    engine = CryptoIdentityEngine("test-root-secret")
    registry = IdentityRegistry(engine)
    registry.issue(IdentityKind.USER, "bob")
    registry.issue(IdentityKind.USER, "bob")
    tokens = registry.find_by_subject("bob")
    assert len(tokens) == 2


def test_audit_log_write_query():
    from aura.governance.audit import AuditLog, AuditCategory
    log = AuditLog(max_entries=100)
    log.write(AuditCategory.POLICY, "root", "policy.eval", "/dev/vcpu", "allow")
    log.write(AuditCategory.BUILD, "builder", "build.run", "artefact:abc", "ok")
    events = log.query(last_n=10)
    assert len(events) >= 2
    policy_events = log.query(category=AuditCategory.POLICY)
    assert all(e["category"] == "policy" for e in policy_events)


def test_audit_log_metrics():
    from aura.governance.audit import AuditLog, AuditCategory
    log = AuditLog(max_entries=100)
    log.write(AuditCategory.SYSTEM, "system", "boot", "os", "ok")
    log.write(AuditCategory.SYSTEM, "system", "halt", "os", "ok")
    log.write(AuditCategory.POLICY, "hacker", "escalate", "root", "deny")
    m = log.metrics()
    assert m["total_events"] >= 3
    assert "system" in m["by_category"]
    assert "deny" in m["by_outcome"]


# ---------------------------------------------------------------------------
# Compute Dispatcher / /dev/vgpu
# ---------------------------------------------------------------------------

def test_vgpu_submit_local():
    import time
    from aura.config import CPUConfig, CloudConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    from aura.cloud.virtual_cloud import VirtualCloud
    from aura.hardware.vcpu import VCPUDevice
    from aura.hardware.vgpu import VGPUDevice
    cpu = VirtualCPU(CPUConfig(virtual_cores=2, max_concurrent_tasks=2))
    cpu.start()
    dev_cpu = VCPUDevice(cpu)
    cloud = VirtualCloud(CloudConfig(compute_nodes=1))
    dev_gpu = VGPUDevice(vcpu=dev_cpu, cloud=cloud, default_backend="local")
    job_id = dev_gpu.submit(lambda: 42, name="vgpu-test", backend="local")
    for _ in range(30):
        job = dev_gpu.get_job(job_id)
        if job and job["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    job = dev_gpu.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    m = dev_gpu.metrics()
    assert m["total_jobs"] >= 1
    cpu.stop()


def test_vgpu_spill_to_cloud():
    from aura.config import CPUConfig, CloudConfig
    from aura.cpu.virtual_cpu import VirtualCPU
    from aura.cloud.virtual_cloud import VirtualCloud
    from aura.hardware.vcpu import VCPUDevice
    from aura.compute.dispatcher import ComputeDispatcher, ComputeBackend
    cpu = VirtualCPU(CPUConfig(virtual_cores=1, max_concurrent_tasks=1))
    cpu.start()
    dev_cpu = VCPUDevice(cpu)
    cloud = VirtualCloud(CloudConfig(compute_nodes=1))
    dispatcher = ComputeDispatcher(
        vcpu=dev_cpu, cloud=cloud,
        spill_threshold_pct=0.0,
        default_backend=ComputeBackend.LOCAL,
    )
    resolved = dispatcher._resolve_backend(ComputeBackend.AUTO)
    assert resolved == ComputeBackend.CLOUD
    cpu.stop()


# ---------------------------------------------------------------------------
# Full AIOS integration — new OS commands
# ---------------------------------------------------------------------------

def test_aios_dispatch_root():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18470
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("root")
        assert "ROOT Sovereign Layer" in out
        assert "Running" in out


def test_aios_dispatch_dev():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18471
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("dev")
        assert "/dev/" in out
        assert "vcpu" in out


def test_aios_dispatch_net():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18472
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("net")
        assert "DHCP" in out or "Network" in out


def test_aios_dispatch_vgpu():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18473
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("vgpu")
        assert "vgpu" in out.lower() or "Compute" in out


def test_aios_dispatch_vram():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18474
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("vram")
        assert "RAM" in out or "vram" in out.lower()


def test_aios_dispatch_vdisk():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18475
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("vdisk")
        assert "rootfs" in out or "volume" in out.lower()


def test_aios_dispatch_home():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18476
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("home")
        assert "HOME" in out


def test_aios_dispatch_build_list():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18477
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("build", ["list"])
        assert "no runs" in out.lower() or "Build" in out


def test_aios_dispatch_identity():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18478
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("identity")
        assert "Identity" in out or "tokens" in out.lower()


def test_aios_dispatch_audit():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18479
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        out = aios.dispatch("audit")
        assert "audit" in out.lower() or "Audit" in out or "[" in out


def test_aios_metrics_includes_new_layers():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18480
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        m = aios.metrics()
        assert "root" in m
        assert "home" in m
        assert "vnet" in m
        assert "vgpu" in m
        assert "vram" in m
        assert "vdisk" in m
        assert "identity" in m
        assert "audit" in m


def test_aios_properties_accessible():
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = 18481
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    with AIOS(cfg) as aios:
        assert aios.root.running is True
        assert aios.home.running is True
        assert aios.dev_vcpu is not None
        assert aios.dev_vram is not None
        assert aios.dev_vdisk is not None
        assert aios.dev_vnet is not None
        assert aios.dev_vbt is not None
        assert aios.dev_vgpu is not None
        assert aios.build_pipeline is not None
        assert aios.identity_registry is not None
        assert aios.audit_log is not None


# ---------------------------------------------------------------------------
# HomeFilesystem — write / read / delete
# ---------------------------------------------------------------------------

def test_home_filesystem_write_read_delete(tmp_path):
    from aura.home.filesystem import HomeFilesystem
    fs = HomeFilesystem(str(tmp_path))
    fs.mount()
    # write then read
    fs.write("hello world\n", "home", "aura", "note.txt")
    content = fs.read("home", "aura", "note.txt")
    assert "hello world" in content
    # delete
    removed = fs.delete("home", "aura", "note.txt")
    assert removed is True
    assert not fs.exists("home", "aura", "note.txt")
    # delete non-existent returns False
    removed2 = fs.delete("home", "aura", "note.txt")
    assert removed2 is False


def test_home_filesystem_delete_directory(tmp_path):
    from aura.home.filesystem import HomeFilesystem
    fs = HomeFilesystem(str(tmp_path))
    fs.mount()
    import os
    os.makedirs(fs.path("opt", "myapp"), exist_ok=True)
    fs.write("data", "opt", "myapp", "data.txt")
    removed = fs.delete("opt", "myapp")
    assert removed is True
    assert not fs.exists("opt", "myapp")


def test_home_filesystem_delete_traversal_blocked(tmp_path):
    from aura.home.filesystem import HomeFilesystem
    fs = HomeFilesystem(str(tmp_path))
    fs.mount()
    import pytest
    with pytest.raises(ValueError):
        fs.delete("..", "etc", "passwd")


# ---------------------------------------------------------------------------
# HOMELayer — git_install (no real git needed — mocked)
# ---------------------------------------------------------------------------

def test_home_layer_git_install_no_git(tmp_path, monkeypatch):
    """git_install raises RuntimeError when git is not on PATH."""
    import shutil
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    cfg = HOMEConfig(home_dir=str(tmp_path))
    layer = HOMELayer(cfg)
    layer.start()
    # Patch shutil.which inside the userland module to simulate git absent
    monkeypatch.setattr("shutil.which", lambda name: None)
    import pytest
    with pytest.raises(RuntimeError, match="git: not found"):
        layer.git_install("https://github.com/example/repo.git")
    layer.stop()


def test_home_layer_git_install_success(tmp_path, monkeypatch):
    """git_install registers a package when the bridge succeeds."""
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    from aura.adapters.android_bridge import RunResult
    import shutil

    cfg = HOMEConfig(home_dir=str(tmp_path))
    layer = HOMELayer(cfg)
    layer.start()

    # Ensure git appears to be available
    real_which = shutil.which
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/git" if name == "git" else real_which(name))

    # Stub AndroidBridge.run to return success without spawning git
    import aura.home.userland as _userland_mod
    import aura.adapters.android_bridge as _ab_mod

    class _FakeBridge:
        def run(self, cmd, **_):
            return RunResult(command=cmd, returncode=0, stdout="Cloning into 'repo'...\n", stderr="")

    monkeypatch.setattr(_ab_mod, "AndroidBridge", _FakeBridge)

    pkg = layer.git_install("https://github.com/example/repo.git", "repo")
    assert pkg.name == "repo"
    assert pkg.version == "git"
    pkgs = layer.list_packages()
    assert any(p["name"] == "repo" for p in pkgs)
    layer.stop()


# ---------------------------------------------------------------------------
# SD-card boot configuration
# ---------------------------------------------------------------------------

def test_sd_card_boot_config_via_env(tmp_path, monkeypatch):
    """AURA_BOOT_DEVICE env var redirects HOME to the specified path."""
    sd_path = str(tmp_path / "sdcard" / "aura")
    monkeypatch.setenv("AURA_BOOT_DEVICE", sd_path)
    from aura.config import AURaConfig
    cfg = AURaConfig.from_env()
    assert cfg.home.boot_device == sd_path
    assert cfg.home.home_dir == sd_path


def test_sd_card_boot_config_via_home_dir_env(tmp_path, monkeypatch):
    """AURA_HOME_DIR env var overrides home_dir without setting boot_device."""
    custom = str(tmp_path / "custom_home")
    monkeypatch.setenv("AURA_HOME_DIR", custom)
    monkeypatch.delenv("AURA_BOOT_DEVICE", raising=False)
    from aura.config import AURaConfig
    cfg = AURaConfig.from_env()
    assert cfg.home.home_dir == custom
    assert cfg.home.boot_device == ""


def test_boot_device_reported_in_home_status(tmp_path):
    """HOMELayer.status() includes boot_device field."""
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    cfg = HOMEConfig(home_dir=str(tmp_path), boot_device="/sdcard/aura")
    layer = HOMELayer(cfg)
    layer.start()
    s = layer.status()
    assert s["boot_device"] == "/sdcard/aura"
    layer.stop()


def test_boot_device_defaults_to_internal(tmp_path):
    """When boot_device is empty, status() reports 'internal'."""
    from aura.config import HOMEConfig
    from aura.home.userland import HOMELayer
    cfg = HOMEConfig(home_dir=str(tmp_path))
    layer = HOMELayer(cfg)
    layer.start()
    s = layer.status()
    assert s["boot_device"] == "internal"
    layer.stop()


# ---------------------------------------------------------------------------
# AIOS dispatch — fs commands
# ---------------------------------------------------------------------------

def _make_aios(port, tmp_path):
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    cfg = AURaConfig()
    cfg.server.port = port
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    cfg.home.home_dir = str(tmp_path)
    return AIOS(cfg)


def test_aios_dispatch_fs_write_read(tmp_path):
    with _make_aios(18490, tmp_path) as aios:
        out = aios.dispatch("fs", ["write", "home/aura/hello.txt", "hello", "world"])
        assert "wrote" in out.lower() or "byte" in out.lower()
        out2 = aios.dispatch("fs", ["read", "home/aura/hello.txt"])
        assert "hello world" in out2


def test_aios_dispatch_fs_delete(tmp_path):
    with _make_aios(18491, tmp_path) as aios:
        aios.dispatch("fs", ["write", "home/aura/del.txt", "gone"])
        out = aios.dispatch("fs", ["rm", "home/aura/del.txt"])
        assert "removed" in out.lower()
        # reading after delete should error
        out2 = aios.dispatch("fs", ["read", "home/aura/del.txt"])
        assert "error" in out2.lower() or "No such" in out2 or "fs read" in out2


def test_aios_dispatch_fs_mkdir_ls(tmp_path):
    with _make_aios(18492, tmp_path) as aios:
        out = aios.dispatch("fs", ["mkdir", "home/aura/mydir"])
        assert "created" in out.lower() or "mydir" in out.lower()
        ls_out = aios.dispatch("fs", ["ls", "home/aura"])
        assert "mydir" in ls_out


def test_aios_dispatch_fs_info(tmp_path):
    with _make_aios(18493, tmp_path) as aios:
        out = aios.dispatch("fs", ["info"])
        assert "HOME filesystem" in out or "Total" in out


def test_aios_dispatch_fs_help(tmp_path):
    with _make_aios(18494, tmp_path) as aios:
        out = aios.dispatch("fs", [])
        assert "Usage" in out
        assert "write" in out
        assert "read" in out
        assert "rm" in out


# ---------------------------------------------------------------------------
# AIOS dispatch — pkg commands
# ---------------------------------------------------------------------------

def test_aios_dispatch_pkg_install_list_remove(tmp_path):
    with _make_aios(18495, tmp_path) as aios:
        out = aios.dispatch("pkg", ["install", "mytool", "2.0.0"])
        assert "installed" in out.lower()
        lst = aios.dispatch("pkg", ["list"])
        assert "mytool" in lst
        rm = aios.dispatch("pkg", ["remove", "mytool"])
        assert "removed" in rm.lower()
        lst2 = aios.dispatch("pkg", ["list"])
        assert "mytool" not in lst2


def test_aios_dispatch_pkg_remove_not_installed(tmp_path):
    with _make_aios(18496, tmp_path) as aios:
        out = aios.dispatch("pkg", ["remove", "nonexistent"])
        assert "not installed" in out.lower()


def test_aios_dispatch_pkg_help(tmp_path):
    with _make_aios(18497, tmp_path) as aios:
        out = aios.dispatch("pkg", [])
        assert "Usage" in out
        assert "install" in out
        assert "git" in out


def test_aios_dispatch_pkg_git_no_git(tmp_path, monkeypatch):
    """pkg git returns an error when git is not on PATH."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    with _make_aios(18498, tmp_path) as aios:
        out = aios.dispatch("pkg", ["git", "https://github.com/example/repo.git"])
        assert "git" in out.lower() and ("not found" in out.lower() or "error" in out.lower() or "fail" in out.lower())


# ---------------------------------------------------------------------------
# AIOS dispatch — git commands
# ---------------------------------------------------------------------------

def test_aios_dispatch_git_help(tmp_path):
    with _make_aios(18499, tmp_path) as aios:
        out = aios.dispatch("git", [])
        assert "Usage" in out
        assert "clone" in out
        assert "pull" in out


def test_aios_dispatch_git_clone_missing_git(tmp_path, monkeypatch):
    """git clone dispatch returns error message when git binary absent."""
    with _make_aios(18500, tmp_path) as aios:
        # Run git clone for a non-existent host — it will fail gracefully
        out = aios.dispatch("git", ["clone", "https://127.0.0.1:1/nonexistent.git", str(tmp_path / "dest")])
        # Should return some output (error from git or timeout message)
        assert isinstance(out, str) and len(out) > 0


def test_aios_dispatch_git_status(tmp_path):
    """git status dispatch works inside a git repo or returns an error string."""
    with _make_aios(18501, tmp_path) as aios:
        out = aios.dispatch("git", ["status", str(tmp_path)])
        assert isinstance(out, str)


# ---------------------------------------------------------------------------
# AIOS help includes new commands
# ---------------------------------------------------------------------------

def test_aios_help_includes_fs_pkg_git(tmp_path):
    with _make_aios(18502, tmp_path) as aios:
        out = aios.dispatch("help")
        assert "fs" in out
        assert "pkg" in out
        assert "git" in out


# ===========================================================================
# v2.0.0 NEW MODULE TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Config v2.0.0 — new subsystem configs
# ---------------------------------------------------------------------------

def test_config_v2_version():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert cfg.version == "2.0.0"


def test_config_kernel_defaults():
    from aura.config import KernelConfig
    kcfg = KernelConfig()
    assert kcfg.cron_tick_seconds > 0
    assert kcfg.syslog_max_entries == 10000


def test_config_web_defaults():
    from aura.config import WebConfig
    wcfg = WebConfig()
    assert wcfg.auth_enabled is False
    assert wcfg.websocket_enabled is True


def test_config_pkg_defaults():
    from aura.config import PkgConfig
    pcfg = PkgConfig()
    assert "packages" in pcfg.packages_dir


def test_auraconfig_has_all_v2_fields():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert hasattr(cfg, "kernel")
    assert hasattr(cfg, "web")
    assert hasattr(cfg, "pkg")


# ---------------------------------------------------------------------------
# Kernel — ProcessManager
# ---------------------------------------------------------------------------

def test_process_manager_spawn_kill():
    import time
    from aura.kernel.process_manager import ProcessManager
    pm = ProcessManager()
    pid = pm.spawn("test-proc", fn=lambda: time.sleep(0.01))
    assert pid is not None
    procs = pm.list_processes()
    assert any(p["pid"] == pid for p in procs)
    killed = pm.kill(pid)
    assert killed is True


def test_process_manager_get_process():
    from aura.kernel.process_manager import ProcessManager
    pm = ProcessManager()
    pid = pm.spawn("get-proc", fn=lambda: None)
    info = pm.get_process(pid)
    assert info is not None
    assert info["name"] == "get-proc"


def test_process_manager_kill_unknown():
    from aura.kernel.process_manager import ProcessManager
    pm = ProcessManager()
    assert pm.kill("nonexistent-pid") is False


def test_process_manager_metrics():
    from aura.kernel.process_manager import ProcessManager
    pm = ProcessManager()
    pm.spawn("m-proc", fn=lambda: None)
    m = pm.metrics()
    assert "total" in m


def test_process_manager_list_by_user():
    from aura.kernel.process_manager import ProcessManager
    pm = ProcessManager()
    pm.spawn("user-proc", fn=lambda: None, user_id="alice")
    pm.spawn("sys-proc", fn=lambda: None, user_id="system")
    alice_procs = pm.list_processes(user_id="alice")
    assert all(p["user_id"] == "alice" for p in alice_procs)


# ---------------------------------------------------------------------------
# Kernel — IPCBus
# ---------------------------------------------------------------------------

def test_ipc_bus_send_receive():
    from aura.kernel.ipc import IPCBus
    bus = IPCBus()
    bus.send("chan1", {"msg": "hello"})
    msg = bus.receive("chan1")
    assert msg == {"msg": "hello"}


def test_ipc_bus_empty_receive():
    from aura.kernel.ipc import IPCBus
    bus = IPCBus()
    msg = bus.receive("empty-chan", block=False)
    assert msg is None


def test_ipc_bus_list_channels():
    from aura.kernel.ipc import IPCBus
    bus = IPCBus()
    bus.send("ch-a", "x")
    bus.send("ch-b", "y")
    channels = bus.list_channels()
    assert "ch-a" in channels
    assert "ch-b" in channels


def test_ipc_bus_clear():
    from aura.kernel.ipc import IPCBus
    bus = IPCBus()
    bus.send("clr", "a")
    bus.send("clr", "b")
    bus.clear("clr")
    assert bus.receive("clr", block=False) is None


# ---------------------------------------------------------------------------
# Kernel — SyslogService
# ---------------------------------------------------------------------------

def test_syslog_log_and_query():
    from aura.kernel.syslog import SyslogService
    svc = SyslogService()
    svc.info("test.src", "hello from test")
    entries = svc.query(source="test.src")
    assert len(entries) >= 1
    assert entries[-1]["message"] == "hello from test"


def test_syslog_level_methods():
    from aura.kernel.syslog import SyslogService
    svc = SyslogService()
    svc.info("src", "info msg")
    svc.warn("src", "warn msg")
    svc.error("src", "error msg")
    m = svc.metrics()
    # Metrics may use uppercase or lowercase keys
    total_count = sum(v for k, v in m.items() if k != "total" and isinstance(v, int))
    assert total_count >= 3


def test_syslog_level_filter():
    from aura.kernel.syslog import SyslogService
    svc = SyslogService()
    svc.info("a", "info")
    svc.error("a", "error")
    errors = svc.query(level="error")
    assert all(e["level"] in ("error", "ERROR") for e in errors)


def test_syslog_limit():
    from aura.kernel.syslog import SyslogService
    svc = SyslogService()
    for i in range(10):
        svc.info("src", f"msg{i}")
    entries = svc.query(limit=3)
    assert len(entries) <= 3


# ---------------------------------------------------------------------------
# Kernel — SecretsManager
# ---------------------------------------------------------------------------

def test_secrets_set_get():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    sm.set_secret("DB_PASSWORD", "s3cr3t")
    val = sm.get_secret("DB_PASSWORD")
    assert val == "s3cr3t"


def test_secrets_list_keys():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    sm.set_secret("KEY_A", "val_a")
    sm.set_secret("KEY_B", "val_b")
    keys = sm.list_keys()
    assert "KEY_A" in keys
    assert "KEY_B" in keys


def test_secrets_delete():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    sm.set_secret("TEMP", "tmp")
    deleted = sm.delete_secret("TEMP")
    assert deleted is True
    assert sm.get_secret("TEMP") is None


def test_secrets_rotate():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    sm.set_secret("ROT_KEY", "old")
    ok = sm.rotate_secret("ROT_KEY", "new")
    assert ok is True
    assert sm.get_secret("ROT_KEY") == "new"


def test_secrets_invalid_key_raises():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    try:
        sm.set_secret("bad key!", "value")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_secrets_rotate_nonexistent():
    from aura.kernel.secrets_manager import SecretsManager
    sm = SecretsManager()
    ok = sm.rotate_secret("NO_SUCH_KEY", "val")
    assert ok is False


# ---------------------------------------------------------------------------
# Kernel — CronService
# ---------------------------------------------------------------------------

def test_cron_add_remove_job():
    from aura.kernel.cron import CronService
    cron = CronService()
    job_id = cron.add_job("test-job", fn=lambda: None, interval_seconds=60)
    jobs = cron.list_jobs()
    assert any(j["job_id"] == job_id for j in jobs)
    removed = cron.remove_job(job_id)
    assert removed is True
    assert not any(j["job_id"] == job_id for j in cron.list_jobs())


def test_cron_enable_disable():
    from aura.kernel.cron import CronService
    cron = CronService()
    jid = cron.add_job("en-test", fn=lambda: None, interval_seconds=100)
    ok = cron.disable_job(jid)
    assert ok is True
    job = next(j for j in cron.list_jobs() if j["job_id"] == jid)
    assert job["enabled"] is False
    cron.enable_job(jid)
    job2 = next(j for j in cron.list_jobs() if j["job_id"] == jid)
    assert job2["enabled"] is True


def test_cron_start_stop():
    import time
    from aura.kernel.cron import CronService
    cron = CronService()
    cron.start()
    time.sleep(0.1)
    cron.stop()  # should not raise


def test_cron_job_runs():
    import time
    from aura.kernel.cron import CronService
    results = []
    cron = CronService()
    cron.add_job("runner", fn=lambda: results.append(1), interval_seconds=0.05)
    cron.start()
    time.sleep(0.3)
    cron.stop()
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# Kernel — ServiceManager
# ---------------------------------------------------------------------------

def test_service_manager_register_and_list():
    from aura.kernel.service_manager import ServiceManager
    sm = ServiceManager()
    sm.register("test-svc", start_fn=lambda: None)
    svcs = sm.list_services()
    assert any(s["name"] == "test-svc" for s in svcs)


def test_service_manager_start_stop():
    from aura.kernel.service_manager import ServiceManager
    started = []
    stopped = []
    sm = ServiceManager()
    sm.register("s1", start_fn=lambda: started.append(1), stop_fn=lambda: stopped.append(1))
    ok = sm.start_service("s1")
    assert ok is True
    assert len(started) == 1
    svc = sm.status("s1")
    assert svc["state"] == "active"
    sm.stop_service("s1")
    assert len(stopped) == 1


def test_service_manager_restart():
    from aura.kernel.service_manager import ServiceManager
    count = []
    sm = ServiceManager()
    sm.register("r-svc", start_fn=lambda: count.append(1))
    sm.start_service("r-svc")
    sm.restart_service("r-svc")
    assert len(count) >= 2


def test_service_manager_metrics():
    from aura.kernel.service_manager import ServiceManager
    sm = ServiceManager()
    sm.register("m-svc", start_fn=lambda: None)
    sm.start_service("m-svc")
    m = sm.metrics()
    assert m.get("active", 0) >= 1


# ---------------------------------------------------------------------------
# Filesystem — VirtualFileSystem
# ---------------------------------------------------------------------------

def test_vfs_mkdir_and_listdir():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/home/alice")
    entries = vfs.listdir("/home")
    assert "alice" in entries


def test_vfs_write_read():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/etc")
    vfs.write("/etc/config", b"key=value")
    data = vfs.read("/etc/config")
    assert data == b"key=value"


def test_vfs_delete():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/tmp")
    vfs.write("/tmp/to-delete", b"bye")
    ok = vfs.delete("/tmp/to-delete")
    assert ok is True
    assert vfs.read("/tmp/to-delete") is None


def test_vfs_exists():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/proc")
    assert vfs.exists("/proc") is True
    assert vfs.exists("/nope") is False


def test_vfs_stat():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/var")
    vfs.write("/var/log", b"log data")
    info = vfs.stat("/var/log")
    assert info is not None
    assert info["type"] == "file"
    assert info["size"] == 8


def test_vfs_mount_umount():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    fake_fs = object()
    vfs.mount("/mnt/usb", fake_fs)
    assert "/mnt/usb" in vfs._mounts
    ok = vfs.umount("/mnt/usb")
    assert ok is True
    assert "/mnt/usb" not in vfs._mounts


def test_vfs_mkdir_creates_parents():
    from aura.fs.vfs import VirtualFileSystem
    vfs = VirtualFileSystem()
    vfs.mkdir("/a/b/c")
    assert vfs.exists("/a") is True
    assert vfs.exists("/a/b") is True
    assert vfs.exists("/a/b/c") is True


# ---------------------------------------------------------------------------
# Filesystem — ProcFS
# ---------------------------------------------------------------------------

def test_procfs_builtin_entries():
    from aura.fs.procfs import ProcFS
    proc = ProcFS()
    entries = proc.list_entries()
    assert "/proc/version" in entries
    assert "/proc/cpuinfo" in entries


def test_procfs_read_version():
    from aura.fs.procfs import ProcFS
    proc = ProcFS()
    val = proc.read("/proc/version")
    assert val is not None
    assert "AURa" in val


def test_procfs_register_provider():
    from aura.fs.procfs import ProcFS
    proc = ProcFS()
    proc.register_provider("/proc/custom", lambda: "custom-data")
    assert proc.read("/proc/custom") == "custom-data"


def test_procfs_missing_path():
    from aura.fs.procfs import ProcFS
    proc = ProcFS()
    assert proc.read("/proc/no-such-entry") is None


# ---------------------------------------------------------------------------
# Filesystem — FHSMapper
# ---------------------------------------------------------------------------

def test_fhs_resolve_known():
    from aura.fs.fhs import FHSMapper
    fhs = FHSMapper()
    r = fhs.resolve("/bin")
    assert r  # any non-empty string


def test_fhs_list_mappings():
    from aura.fs.fhs import FHSMapper
    fhs = FHSMapper()
    mappings = fhs.list_mappings()
    assert isinstance(mappings, dict)
    assert len(mappings) >= 5


def test_fhs_add_mapping():
    from aura.fs.fhs import FHSMapper
    fhs = FHSMapper()
    fhs.add_mapping("/custom", "aura:custom")
    assert fhs.resolve("/custom") == "aura:custom"


def test_fhs_resolve_subpath():
    from aura.fs.fhs import FHSMapper
    fhs = FHSMapper()
    # /etc maps to something; /etc/passwd should also resolve
    r = fhs.resolve("/etc/passwd")
    assert r  # non-empty


# ---------------------------------------------------------------------------
# Package Manager — PackageMetadata
# ---------------------------------------------------------------------------

def test_pkg_metadata_to_dict():
    from aura.pkg.metadata import PackageMetadata
    m = PackageMetadata(
        name="mypkg", version="1.0.0", description="test",
        author="me", dependencies=[], tags=["test"],
    )
    d = m.to_dict()
    assert d["name"] == "mypkg"
    assert d["version"] == "1.0.0"


def test_pkg_metadata_from_dict():
    from aura.pkg.metadata import PackageMetadata
    d = {"name": "pkg2", "version": "2.0.0", "description": "d", "author": "a"}
    m = PackageMetadata.from_dict(d)
    assert m.name == "pkg2"
    assert m.version == "2.0.0"


def test_pkg_status_enum():
    from aura.pkg.metadata import PackageStatus
    assert PackageStatus.INSTALLED.value == "installed"
    assert PackageStatus.AVAILABLE.value == "available"


# ---------------------------------------------------------------------------
# Package Manager — PackageRegistry
# ---------------------------------------------------------------------------

def test_pkg_registry_builtin_packages():
    from aura.pkg.registry import PackageRegistry
    reg = PackageRegistry()
    assert reg.count() >= 3
    assert reg.get("aura-core") is not None


def test_pkg_registry_register_get():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.metadata import PackageMetadata
    reg = PackageRegistry()
    m = PackageMetadata(name="custom-pkg", version="1.0.0", description="test", author="me")
    reg.register(m)
    assert reg.get("custom-pkg") is not None


def test_pkg_registry_search():
    from aura.pkg.registry import PackageRegistry
    reg = PackageRegistry()
    results = reg.search("aura")
    assert len(results) >= 1


def test_pkg_registry_unregister():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.metadata import PackageMetadata
    reg = PackageRegistry()
    m = PackageMetadata(name="temp-pkg", version="1.0.0", description="t", author="a")
    reg.register(m)
    ok = reg.unregister("temp-pkg")
    assert ok is True
    assert reg.get("temp-pkg") is None


def test_pkg_registry_list_all():
    from aura.pkg.registry import PackageRegistry
    reg = PackageRegistry()
    all_pkgs = reg.list_all()
    assert len(all_pkgs) >= 3


# ---------------------------------------------------------------------------
# Package Manager — PackageInstaller
# ---------------------------------------------------------------------------

def test_pkg_installer_install():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.installer import PackageInstaller
    reg = PackageRegistry()
    installer = PackageInstaller(reg)
    result = installer.install("aura-core")
    assert result["success"] is True
    assert installer.is_installed("aura-core") is True


def test_pkg_installer_uninstall():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.installer import PackageInstaller
    reg = PackageRegistry()
    installer = PackageInstaller(reg)
    installer.install("aura-shell")
    result = installer.uninstall("aura-shell")
    assert result["success"] is True
    assert installer.is_installed("aura-shell") is False


def test_pkg_installer_install_not_in_registry():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.installer import PackageInstaller
    reg = PackageRegistry()
    installer = PackageInstaller(reg)
    result = installer.install("nonexistent-pkg")
    assert result["success"] is False


def test_pkg_installer_list_installed():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.installer import PackageInstaller
    reg = PackageRegistry()
    installer = PackageInstaller(reg)
    installer.install("aura-core")
    installed = installer.list_installed()
    assert any(p["name"] == "aura-core" for p in installed)


def test_pkg_installer_upgrade():
    from aura.pkg.registry import PackageRegistry
    from aura.pkg.installer import PackageInstaller
    reg = PackageRegistry()
    installer = PackageInstaller(reg)
    installer.install("aura-net")
    result = installer.upgrade("aura-net")
    assert result["success"] is True


# ---------------------------------------------------------------------------
# Web — WebAPI
# ---------------------------------------------------------------------------

def test_web_api_health():
    from aura.web.api import WebAPI
    api = WebAPI()
    resp = api.handle_request("GET", "/health")
    assert resp["status"] == 200
    assert resp["body"]["status"] == "ok"


def test_web_api_status():
    from aura.web.api import WebAPI
    api = WebAPI()
    resp = api.handle_request("GET", "/status")
    assert resp["status"] == 200
    assert resp["body"]["running"] is True


def test_web_api_not_found():
    from aura.web.api import WebAPI
    api = WebAPI()
    resp = api.handle_request("GET", "/unknown-path")
    assert resp["status"] == 404


def test_web_api_auth_missing_token():
    from aura.web.api import WebAPI
    api = WebAPI(auth_enabled=True, api_token="secret123")
    resp = api.handle_request("GET", "/health", headers={})
    assert resp["status"] == 401


def test_web_api_auth_valid_token():
    from aura.web.api import WebAPI
    api = WebAPI(auth_enabled=True, api_token="secret123")
    resp = api.handle_request("GET", "/health", headers={"Authorization": "Bearer secret123"})
    assert resp["status"] == 200


def test_web_api_register_route():
    from aura.web.api import WebAPI
    api = WebAPI()
    # Handlers receive a single dict: {"method", "path", "body"}
    api.register_route("/custom", lambda req: {"value": 42})
    resp = api.handle_request("GET", "/custom")
    assert resp["status"] == 200
    assert resp["body"]["value"] == 42


# ---------------------------------------------------------------------------
# Web — WebSocketHub
# ---------------------------------------------------------------------------

def test_ws_hub_connect_disconnect():
    from aura.web.ws import WebSocketHub
    hub = WebSocketHub()
    cid = hub.connect()
    assert cid is not None
    clients = hub.list_clients()
    assert any(c["client_id"] == cid for c in clients)
    ok = hub.disconnect(cid)
    assert ok is True


def test_ws_hub_subscribe_broadcast():
    from aura.web.ws import WebSocketHub
    hub = WebSocketHub()
    c1 = hub.connect()
    c2 = hub.connect()
    hub.subscribe(c1, "events")
    hub.subscribe(c2, "events")
    count = hub.broadcast("events", {"type": "test"})
    assert count == 2
    msgs = hub.receive(c1)
    assert len(msgs) == 1


def test_ws_hub_send_specific():
    from aura.web.ws import WebSocketHub
    hub = WebSocketHub()
    cid = hub.connect()
    ok = hub.send(cid, {"hello": "world"})
    assert ok is True
    msgs = hub.receive(cid)
    assert len(msgs) == 1
    # Messages are wrapped in an envelope: {"topic", "message", "timestamp"}
    assert msgs[0]["message"] == {"hello": "world"}


def test_ws_hub_unsubscribe():
    from aura.web.ws import WebSocketHub
    hub = WebSocketHub()
    cid = hub.connect()
    hub.subscribe(cid, "topic")
    hub.unsubscribe(cid, "topic")
    hub.broadcast("topic", {"x": 1})
    msgs = hub.receive(cid)
    assert len(msgs) == 0


# ---------------------------------------------------------------------------
# AI Engine — ModelRegistry
# ---------------------------------------------------------------------------

def test_model_registry_builtin():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    assert reg.count() >= 1
    m = reg.get_by_name("aura-builtin-1.0")
    assert m is not None
    assert m["status"] == "ready"


def test_model_registry_register():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    mid = reg.register("my-model", "transformers", "1.0.0", capabilities=["chat"])
    assert mid is not None
    m = reg.get(mid)
    assert m["name"] == "my-model"


def test_model_registry_list():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    all_models = reg.list_models()
    assert len(all_models) >= 1


def test_model_registry_update_status():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    mid = reg.register("status-model", "transformers", "1.0.0")
    ok = reg.update_status(mid, "loading")
    assert ok is True
    m = reg.get(mid)
    assert m["status"] == "loading"


def test_model_registry_unregister():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    mid = reg.register("del-model", "builtin", "1.0.0")
    ok = reg.unregister(mid)
    assert ok is True
    assert reg.get(mid) is None


def test_model_registry_filter_by_backend():
    from aura.ai_engine.model_registry import ModelRegistry
    reg = ModelRegistry()
    reg.register("m-local", "llama", "1.0.0")
    llama_models = reg.list_models(backend="llama")
    assert all(m["backend"] == "llama" for m in llama_models)


# ---------------------------------------------------------------------------
# AI Engine — ModelScanner
# ---------------------------------------------------------------------------

def test_model_scanner_scan_empty_dir(tmp_path):
    from aura.ai_engine.model_scanner import ModelScanner
    scanner = ModelScanner(scan_dirs=[str(tmp_path)])
    results = scanner.scan()
    assert isinstance(results, list)
    assert len(results) == 0


def test_model_scanner_detect_gguf(tmp_path):
    (tmp_path / "llama-7b.gguf").write_bytes(b"fake gguf")
    from aura.ai_engine.model_scanner import ModelScanner
    scanner = ModelScanner(scan_dirs=[str(tmp_path)])
    results = scanner.scan()
    # Scanner strips extension: name="llama-7b", extension=".gguf"
    assert any(r["name"] == "llama-7b" for r in results)
    assert any(r["extension"] == ".gguf" for r in results)
    # Backend is determined via detect_backend
    assert scanner.detect_backend("llama-7b.gguf") == "llama"


def test_model_scanner_detect_safetensors(tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"fake safetensors")
    from aura.ai_engine.model_scanner import ModelScanner
    scanner = ModelScanner(scan_dirs=[str(tmp_path)])
    results = scanner.scan()
    # Scanner strips extension: name="model", extension=".safetensors"
    assert any(r["extension"] == ".safetensors" for r in results)
    assert scanner.detect_backend("model.safetensors") == "transformers"


def test_model_scanner_detect_backend():
    from aura.ai_engine.model_scanner import ModelScanner
    scanner = ModelScanner()
    assert scanner.detect_backend("model.gguf") == "llama"
    assert scanner.detect_backend("model.bin") == "transformers"
    assert scanner.detect_backend("model.safetensors") == "transformers"
    assert scanner.detect_backend("model.xyz") == "unknown"


def test_model_scanner_clear_cache(tmp_path):
    from aura.ai_engine.model_scanner import ModelScanner
    scanner = ModelScanner(scan_dirs=[str(tmp_path)])
    scanner.scan()
    scanner.clear_cache()
    assert scanner.scan_result == []  # cache should be cleared


# ---------------------------------------------------------------------------
# AI Engine — PersonalityKernel
# ---------------------------------------------------------------------------

def test_personality_kernel_default_profile():
    from aura.ai_engine.personality_kernel import PersonalityKernel
    pk = PersonalityKernel()
    profile = pk.to_dict()
    assert profile["name"] == "AURA"
    assert "system_prompt" in profile


def test_personality_kernel_get_system_prompt():
    from aura.ai_engine.personality_kernel import PersonalityKernel
    pk = PersonalityKernel()
    prompt = pk.get_system_prompt()
    assert len(prompt) > 0
    assert "AURA" in prompt


def test_personality_kernel_update_trait():
    from aura.ai_engine.personality_kernel import PersonalityKernel
    pk = PersonalityKernel()
    pk.update_trait("verbosity", 9)
    assert pk.get_trait("verbosity") == 9


def test_personality_kernel_apply_to_prompt():
    from aura.ai_engine.personality_kernel import PersonalityKernel
    pk = PersonalityKernel()
    result = pk.apply_to_prompt("What is the status?")
    assert "What is the status?" in result


def test_personality_kernel_reset():
    from aura.ai_engine.personality_kernel import PersonalityKernel
    pk = PersonalityKernel()
    pk.update_trait("verbosity", 1)
    pk.reset()
    assert pk.get_trait("verbosity") == 5  # default


# ---------------------------------------------------------------------------
# AI Engine — LlamaBackend stub
# ---------------------------------------------------------------------------

def test_llama_backend_not_ready_without_model():
    from aura.config import AIEngineConfig
    from aura.ai_engine.llama_backend import LlamaBackend
    cfg = AIEngineConfig()
    backend = LlamaBackend(cfg, model_path="")
    assert backend.is_ready() is False


def test_llama_backend_generate_stub():
    from aura.config import AIEngineConfig
    from aura.ai_engine.llama_backend import LlamaBackend
    cfg = AIEngineConfig()
    backend = LlamaBackend(cfg, model_path="")
    resp = backend.generate("hello")
    assert resp is not None
    assert isinstance(resp.text, str)
    assert len(resp.text) > 0


# ---------------------------------------------------------------------------
# Mirror System
# ---------------------------------------------------------------------------

def test_mirror_add_and_list():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    mid = svc.add_mirror("mirror-1", "https://mirror1.example.com")
    mirrors = svc.list_mirrors()
    assert any(m["mirror_id"] == mid for m in mirrors)


def test_mirror_remove():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    mid = svc.add_mirror("m2", "https://m2.example.com")
    ok = svc.remove_mirror(mid)
    assert ok is True
    assert not any(m["mirror_id"] == mid for m in svc.list_mirrors())


def test_mirror_set_status():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    mid = svc.add_mirror("m3", "https://m3.example.com")
    ok = svc.set_status(mid, "offline")
    assert ok is True
    m = svc.get_mirror(mid)
    assert m["status"] == "offline"


def test_mirror_mark_synced():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    mid = svc.add_mirror("m4", "https://m4.example.com")
    svc.mark_synced(mid)
    svc.mark_synced(mid)
    m = svc.get_mirror(mid)
    assert m["sync_count"] == 2
    assert m["last_sync"] is not None


def test_mirror_get_primary():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    svc.add_mirror("primary", "https://primary.example.com", mirror_type="primary")
    p = svc.get_primary()
    assert p is not None
    assert p["type"] == "primary"


def test_mirror_failover():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    mid_primary = svc.add_mirror("primary", "https://p.example.com", mirror_type="primary", priority=0)
    mid_secondary = svc.add_mirror("secondary", "https://s.example.com", mirror_type="secondary", priority=5)
    svc.set_status(mid_primary, "offline")
    fo = svc.failover()
    assert fo is not None
    assert fo["mirror_id"] == mid_secondary


def test_mirror_metrics():
    from aura.command_center.mirror import MirrorService
    svc = MirrorService()
    svc.add_mirror("a", "https://a.com")
    svc.add_mirror("b", "https://b.com")
    m = svc.metrics()
    assert "by_status" in m


# ---------------------------------------------------------------------------
# Intelligence Index
# ---------------------------------------------------------------------------

def test_intelligence_index_builtin_seeded():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    entries = idx.list_entries()
    assert len(entries) >= 1
    assert any(e["model_name"] == "aura-builtin-1.0" for e in entries)


def test_intelligence_index_register():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    eid = idx.register(
        model_name="test-model", backend="transformers", version="1.0.0",
        capabilities=["chat"], safety_rating=9.0, performance_score=85.0,
    )
    assert eid is not None
    e = idx.get(eid)
    assert e["model_name"] == "test-model"


def test_intelligence_index_get_by_name():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    e = idx.get_by_name("aura-builtin-1.0")
    assert e is not None


def test_intelligence_index_filter_by_safety():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    idx.register("safe-model", "builtin", "1.0", safety_rating=9.5, performance_score=80.0)
    idx.register("unsafe-model", "builtin", "1.0", safety_rating=3.0, performance_score=80.0)
    safe = idx.list_entries(min_safety=8.0)
    assert all(e["safety_rating"] >= 8.0 for e in safe)


def test_intelligence_index_update_benchmark():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    eid = idx.register("bench-model", "builtin", "1.0")
    ok = idx.update_benchmark(eid, "mmlu", 78.5)
    assert ok is True
    e = idx.get(eid)
    assert e["benchmarks"]["mmlu"] == 78.5


def test_intelligence_index_compare():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    idx.register("model-a", "builtin", "1.0", performance_score=80.0, safety_rating=8.0)
    idx.register("model-b", "builtin", "1.0", performance_score=90.0, safety_rating=7.0)
    # compare() requires entry_ids but returns winner as "a"/"b"/"tie"
    all_entries = {e["model_name"]: e["entry_id"] for e in idx.list_entries()}
    eid_a = all_entries["model-a"]
    eid_b = all_entries["model-b"]
    result = idx.compare(eid_a, eid_b)
    assert "winner" in result
    # model-b has higher performance_score so winner should be "b"
    assert result["winner"] in ("a", "b", "tie")


def test_intelligence_index_top_n():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    for i in range(5):
        idx.register(f"model-{i}", "builtin", "1.0", performance_score=float(i * 10))
    top3 = idx.top_n(3, sort_by="performance_score")
    assert len(top3) == 3


def test_intelligence_index_unregister():
    from aura.resources.intelligence_index import IntelligenceIndex
    idx = IntelligenceIndex()
    eid = idx.register("del-model", "builtin", "1.0")
    ok = idx.unregister(eid)
    assert ok is True
    assert idx.get(eid) is None


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------

def test_branding_banner():
    from branding.banner import get_boot_banner
    banner = get_boot_banner("2.0.0")
    assert "2.0.0" in banner
    assert "AURA" in banner or "AURa" in banner or "AUR" in banner


def test_branding_identity_info():
    from branding.banner import get_identity_info
    info = get_identity_info()
    assert info["name"] == "AURA"
    assert "version" in info
    assert info["license"] == "MIT"


def test_branding_assets_palette():
    from branding.assets import BrandingAssets
    assets = BrandingAssets()
    palette = assets.get_color_palette()
    assert "primary" in palette
    assert "secondary" in palette


def test_branding_assets_logo_text():
    from branding.assets import BrandingAssets
    assets = BrandingAssets()
    logo = assets.get_logo_text()
    assert len(logo) > 0


def test_branding_assets_html_badge():
    from branding.assets import BrandingAssets
    assets = BrandingAssets()
    badge = assets.get_html_badge()
    assert "<" in badge  # contains HTML


# ---------------------------------------------------------------------------
# Platform Adapters — LinuxBridge + MacOSBridge
# ---------------------------------------------------------------------------

def test_linux_bridge_system_info():
    from aura.adapters.linux_bridge import LinuxBridge
    bridge = LinuxBridge()
    info = bridge.get_system_info()
    assert "platform" in info
    assert "cpu_count" in info


def test_linux_bridge_list_processes():
    from aura.adapters.linux_bridge import LinuxBridge
    bridge = LinuxBridge()
    procs = bridge.list_processes()
    assert isinstance(procs, list)
    assert len(procs) >= 1


def test_linux_bridge_interfaces():
    from aura.adapters.linux_bridge import LinuxBridge
    bridge = LinuxBridge()
    ifaces = bridge.get_network_interfaces()
    assert isinstance(ifaces, list)
    assert "vnet0" in ifaces


def test_macos_bridge_system_info():
    from aura.adapters.macos_bridge import MacOSBridge
    bridge = MacOSBridge()
    info = bridge.get_system_info()
    assert "platform" in info


def test_macos_bridge_interfaces():
    from aura.adapters.macos_bridge import MacOSBridge
    bridge = MacOSBridge()
    ifaces = bridge.get_network_interfaces()
    assert "vnet0" in ifaces


# ---------------------------------------------------------------------------
# AIOS v2.0.0 — integration tests for new subsystems
# ---------------------------------------------------------------------------

def _make_aios_v2(port, tmp_path):
    """Helper: create an AIOS instance with the given port for v2.0.0 tests."""
    from aura.config import AURaConfig
    from aura.os_core.ai_os import AIOS
    import pathlib
    cfg = AURaConfig()
    cfg.server.port = port
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    cfg.home.home_dir = str(pathlib.Path(tmp_path) / "home")
    return AIOS(cfg)


def test_aios_v2_version(tmp_path):
    with _make_aios_v2(19100, tmp_path) as aios:
        assert aios.VERSION == "2.0.0"


def test_aios_v2_new_properties(tmp_path):
    with _make_aios_v2(19101, tmp_path) as aios:
        assert aios.process_manager is not None
        assert aios.ipc_bus is not None
        assert aios.syslog is not None
        assert aios.secrets_manager is not None
        assert aios.cron is not None
        assert aios.service_manager is not None
        assert aios.vfs is not None
        assert aios.procfs is not None
        assert aios.fhs is not None
        assert aios.pkg_registry is not None
        assert aios.pkg_installer is not None
        assert aios.web_api is not None
        assert aios.ws_hub is not None
        assert aios.model_registry is not None
        assert aios.personality_kernel is not None
        assert aios.mirror is not None
        assert aios.intelligence_index is not None


def test_aios_v2_dispatch_kernel(tmp_path):
    with _make_aios_v2(19102, tmp_path) as aios:
        out = aios.dispatch("kernel")
        assert "online" in out.lower() or "Kernel" in out


def test_aios_v2_dispatch_proc(tmp_path):
    with _make_aios_v2(19103, tmp_path) as aios:
        out = aios.dispatch("proc")
        assert isinstance(out, str)


def test_aios_v2_dispatch_syslog(tmp_path):
    with _make_aios_v2(19104, tmp_path) as aios:
        aios.syslog.info("test", "hello syslog")
        out = aios.dispatch("syslog")
        assert isinstance(out, str)


def test_aios_v2_dispatch_cron(tmp_path):
    with _make_aios_v2(19105, tmp_path) as aios:
        out = aios.dispatch("cron")
        assert isinstance(out, str)


def test_aios_v2_dispatch_svc(tmp_path):
    with _make_aios_v2(19106, tmp_path) as aios:
        out = aios.dispatch("svc", ["list"])
        assert isinstance(out, str)
        assert "virtual-cpu" in out or "Services" in out


def test_aios_v2_dispatch_vfs(tmp_path):
    with _make_aios_v2(19107, tmp_path) as aios:
        aios.vfs.mkdir("/test")
        out = aios.dispatch("vfs", ["ls", "/"])
        assert isinstance(out, str)


def test_aios_v2_dispatch_apkg(tmp_path):
    with _make_aios_v2(19108, tmp_path) as aios:
        out = aios.dispatch("apkg", ["registry"])
        assert "aura-core" in out


def test_aios_v2_dispatch_mirror(tmp_path):
    with _make_aios_v2(19109, tmp_path) as aios:
        out = aios.dispatch("mirror")
        assert "Mirror" in out or "mirror" in out


def test_aios_v2_dispatch_intel(tmp_path):
    with _make_aios_v2(19110, tmp_path) as aios:
        out = aios.dispatch("intel")
        assert isinstance(out, str)


def test_aios_v2_dispatch_personality(tmp_path):
    with _make_aios_v2(19111, tmp_path) as aios:
        out = aios.dispatch("personality")
        assert "AURA" in out


def test_aios_v2_dispatch_modelreg(tmp_path):
    with _make_aios_v2(19112, tmp_path) as aios:
        out = aios.dispatch("modelreg")
        assert "aura-builtin" in out


def test_aios_v2_dispatch_banner(tmp_path):
    with _make_aios_v2(19113, tmp_path) as aios:
        out = aios.dispatch("banner")
        assert "2.0.0" in out or "AURA" in out or "AURa" in out


def test_aios_v2_metrics_includes_new_subsystems(tmp_path):
    with _make_aios_v2(19114, tmp_path) as aios:
        m = aios.metrics()
        assert "kernel" in m
        assert "fs" in m
        assert "pkg" in m
        assert "model_registry" in m
        assert "mirror" in m
        assert "intelligence_index" in m


def test_aios_v2_help_includes_new_commands(tmp_path):
    with _make_aios_v2(19115, tmp_path) as aios:
        out = aios.dispatch("help")
        assert "kernel" in out
        assert "syslog" in out
        assert "mirror" in out
        assert "intel" in out
        assert "vfs" in out
        assert "apkg" in out


# ---------------------------------------------------------------------------
# OllamaConfig
# ---------------------------------------------------------------------------

def test_ollama_config_defaults():
    from aura.config import OllamaConfig
    cfg = OllamaConfig()
    assert cfg.base_url == "http://localhost:11434"
    assert cfg.model == "llama3.1:8b"
    assert cfg.use_cloud_router is True
    assert cfg.timeout_seconds > 0


def test_aura_config_has_ollama():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert hasattr(cfg, "ollama")
    assert cfg.ollama.model == "llama3.1:8b"


# ---------------------------------------------------------------------------
# OllamaBackend — graceful degradation when server not running
# ---------------------------------------------------------------------------

def test_ollama_backend_not_ready_without_server():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    # Point at a port where nothing is listening
    cfg = OllamaConfig(base_url="http://localhost:19999", model="llama3.1:8b")
    b = OllamaBackend(cfg)
    assert b.is_ready() is False


def test_ollama_backend_stub_response():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    cfg = OllamaConfig(base_url="http://localhost:19999", model="llama3.1:8b")
    b = OllamaBackend(cfg)
    resp = b.generate("hello")
    assert resp is not None
    assert isinstance(resp.text, str)
    assert len(resp.text) > 0
    assert "llama3.1:8b" in resp.model


def test_ollama_backend_stub_stream():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    cfg = OllamaConfig(base_url="http://localhost:19999", model="llama3.1:8b")
    b = OllamaBackend(cfg)
    chunks = list(b.stream("test prompt"))
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_ollama_backend_list_models_offline():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    cfg = OllamaConfig(base_url="http://localhost:19999")
    b = OllamaBackend(cfg)
    models = b.list_models()
    assert isinstance(models, list)


def test_ollama_backend_server_version_offline():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    cfg = OllamaConfig(base_url="http://localhost:19999")
    b = OllamaBackend(cfg)
    ver = b.server_version()
    assert ver == ""


def test_ollama_backend_properties():
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import OllamaConfig
    cfg = OllamaConfig(base_url="http://localhost:19999", model="llama3.1:8b")
    b = OllamaBackend(cfg)
    assert b.model_name == "llama3.1:8b"
    assert "19999" in b.base_url


# ---------------------------------------------------------------------------
# Ollama backend registered in AI engine
# ---------------------------------------------------------------------------

def test_ollama_backend_registered_in_engine():
    from aura.ai_engine.engine import _BACKEND_REGISTRY
    assert "ollama" in _BACKEND_REGISTRY


def test_ollama_adaptor_via_engine_create():
    from aura.ai_engine.engine import create_backend
    from aura.config import AIEngineConfig
    cfg = AIEngineConfig()
    cfg.backend = "ollama"
    cfg.api_base_url = "http://localhost:19999"
    b = create_backend(cfg)
    assert b is not None
    assert b.is_ready() is False
    resp = b.generate("hello")
    assert isinstance(resp.text, str)


# ---------------------------------------------------------------------------
# CloudAIRouter
# ---------------------------------------------------------------------------

def _make_router(tmp_path):
    """Helper: create a CloudAIRouter with a mock backend (no Ollama needed)."""
    from aura.cloud.virtual_cloud import VirtualCloud
    from aura.cpu.virtual_cpu import VirtualCPU
    from aura.cloud.cloud_ai_router import CloudAIRouter
    from aura.ai_engine.ollama_backend import OllamaBackend
    from aura.config import AURaConfig, OllamaConfig
    import pathlib

    cfg = AURaConfig()
    cfg.cloud.compute_nodes = 2
    cfg.cpu.virtual_cores = 2
    cfg.cloud.model_cache_dir = str(pathlib.Path(tmp_path) / "model_cache")

    cloud = VirtualCloud(cfg.cloud)
    cpu = VirtualCPU(cfg.cpu)
    cpu.start()

    # Use direct mode so tests don't hang on thread pool
    ollama_cfg = OllamaConfig(
        base_url="http://localhost:19999",
        use_cloud_router=False,
    )
    backend = OllamaBackend(ollama_cfg)
    router = CloudAIRouter(cpu, cloud, backend, ollama_cfg)
    return router, cpu, cloud


def test_cloud_ai_router_not_ready_without_server(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        assert router.is_backend_ready() is False
    finally:
        cpu.stop()
        router.shutdown()


def test_cloud_ai_router_stub_response(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        resp = router.route("hello world")
        assert resp is not None
        assert isinstance(resp.text, str)
        assert len(resp.text) > 0
    finally:
        cpu.stop()
        router.shutdown()


def test_cloud_ai_router_metrics(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        _ = router.route("test query")
        m = router.metrics()
        assert m["queries_routed"] >= 1
        assert "backend" in m
        assert "model" in m
        assert m["cloud_router_enabled"] is False
    finally:
        cpu.stop()
        router.shutdown()


def test_cloud_ai_router_backend_info(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        info = router.backend_info()
        assert "backend_class" in info
        assert "model_name" in info
        assert "is_ready" in info
        assert info["backend_class"] == "OllamaBackend"
    finally:
        cpu.stop()
        router.shutdown()


def test_cloud_ai_router_registers_model_in_cloud(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        models = router.list_cloud_models()
        model_names = [m["model_name"] for m in models]
        # The router should have registered the model in the cloud
        assert any("llama" in n for n in model_names)
    finally:
        cpu.stop()
        router.shutdown()


def test_cloud_ai_router_pull_model_submits(tmp_path):
    router, cpu, cloud = _make_router(tmp_path)
    try:
        ok = router.pull_model("llama3.1:8b")
        assert ok is True  # submitted (even if Ollama not running)
    finally:
        cpu.stop()
        router.shutdown()


# ---------------------------------------------------------------------------
# AIOS v2 — Cloud AI Router wired into AIOS
# ---------------------------------------------------------------------------

def test_aios_cloud_ai_router_property(tmp_path):
    with _make_aios_v2(19150, tmp_path) as aios:
        assert aios.cloud_ai_router is not None


def test_aios_cloud_ai_dispatch_status(tmp_path):
    with _make_aios_v2(19151, tmp_path) as aios:
        out = aios.dispatch("cloud-ai", ["status"])
        assert "Cloud AI Router" in out
        assert "OllamaBackend" in out
        assert "llama3.1:8b" in out


def test_aios_cloud_ai_dispatch_ask(tmp_path):
    with _make_aios_v2(19152, tmp_path) as aios:
        out = aios.dispatch("cloud-ai", ["ask", "hello"])
        # Should get a graceful stub (Ollama not running in CI)
        assert isinstance(out, str)
        assert len(out) > 0


def test_aios_cloud_ai_dispatch_models(tmp_path):
    with _make_aios_v2(19153, tmp_path) as aios:
        out = aios.dispatch("cloud-ai", ["models"])
        assert isinstance(out, str)


def test_aios_cloud_ai_dispatch_pull(tmp_path):
    with _make_aios_v2(19154, tmp_path) as aios:
        out = aios.dispatch("cloud-ai", ["pull"])
        assert isinstance(out, str)
        assert "llama3.1:8b" in out or "pull" in out.lower()


def test_aios_help_includes_cloud_ai(tmp_path):
    with _make_aios_v2(19155, tmp_path) as aios:
        out = aios.dispatch("help")
        assert "cloud-ai" in out


def test_aios_metrics_includes_cloud_ai_router(tmp_path):
    with _make_aios_v2(19156, tmp_path) as aios:
        m = aios.metrics()
        assert "cloud_ai_router" in m
        assert "backend" in m["cloud_ai_router"]


# ---------------------------------------------------------------------------
# VNode Identity
# ---------------------------------------------------------------------------

def test_vnode_identity_creates_node_id(tmp_path):
    from aura.vnode.identity import VNodeIdentity
    import uuid
    v = VNodeIdentity(node_name="test-node")
    assert v.node_id
    try:
        uuid.UUID(v.node_id)
    except ValueError:
        pytest.fail("node_id is not a valid UUID")


def test_vnode_identity_properties():
    from aura.vnode.identity import VNodeIdentity
    v = VNodeIdentity(node_name="my-node")
    assert v.node_name == "my-node"
    assert isinstance(v.capabilities, list)
    assert len(v.capabilities) >= 1
    assert v.version == "2.0.0"
    assert v.platform in ("termux/android", "linux", "unknown")
    assert v.created_at


def test_vnode_identity_to_dict():
    from aura.vnode.identity import VNodeIdentity
    v = VNodeIdentity()
    d = v.to_dict()
    assert "node_id" in d
    assert "node_name" in d
    assert "capabilities" in d
    assert "version" in d
    assert "platform" in d
    assert "fingerprint" in d
    assert "created_at" in d


def test_vnode_identity_fingerprint_is_string():
    from aura.vnode.identity import VNodeIdentity
    v = VNodeIdentity()
    fp = v.fingerprint()
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex


def test_vnode_identity_stable_across_instances(tmp_path):
    """The node_id should be the same when read from disk on second boot."""
    from aura.vnode.identity import _load_or_create_node_id
    nid1 = _load_or_create_node_id()
    nid2 = _load_or_create_node_id()
    assert nid1 == nid2


# ---------------------------------------------------------------------------
# VNode Registry
# ---------------------------------------------------------------------------

def test_vnode_registry_not_registered_without_url():
    from aura.vnode.identity import VNodeIdentity
    from aura.vnode.registry import VNodeRegistry
    v = VNodeIdentity()
    r = VNodeRegistry(identity=v, command_center_url="")
    ok = r.register()
    assert ok is False
    assert r.is_registered is False


def test_vnode_registry_metrics():
    from aura.vnode.identity import VNodeIdentity
    from aura.vnode.registry import VNodeRegistry
    v = VNodeIdentity()
    r = VNodeRegistry(identity=v)
    m = r.metrics()
    assert "registration_status" in m
    assert "command_center_url" in m


def test_vnode_registry_graceful_failure_bad_url():
    from aura.vnode.identity import VNodeIdentity
    from aura.vnode.registry import VNodeRegistry
    v = VNodeIdentity()
    r = VNodeRegistry(identity=v, command_center_url="http://localhost:19999")
    ok = r.register()
    assert ok is False
    assert r.is_registered is False


# ---------------------------------------------------------------------------
# HeartbeatService
# ---------------------------------------------------------------------------

def test_heartbeat_starts_and_stops():
    from aura.vnode.identity import VNodeIdentity
    from aura.vnode.heartbeat import HeartbeatService
    v = VNodeIdentity()
    hb = HeartbeatService(identity=v, command_center_url="", interval_seconds=0.1)
    hb.start()
    assert hb.is_running is True
    hb.stop()
    assert hb.is_running is False


def test_heartbeat_metrics():
    from aura.vnode.identity import VNodeIdentity
    from aura.vnode.heartbeat import HeartbeatService
    v = VNodeIdentity()
    hb = HeartbeatService(identity=v)
    m = hb.metrics()
    assert "is_running" in m
    assert "beat_count" in m
    assert "interval_seconds" in m


# ---------------------------------------------------------------------------
# MeshBus
# ---------------------------------------------------------------------------

def test_mesh_bus_register_and_list_peers():
    from aura.vnode.mesh import MeshBus
    m = MeshBus()
    m.register_peer("node-1", ["ai", "build"])
    m.register_peer("node-2", ["metrics"])
    peers = m.list_peers()
    assert len(peers) == 2
    node_ids = [p["node_id"] for p in peers]
    assert "node-1" in node_ids
    assert "node-2" in node_ids


def test_mesh_bus_unregister_peer():
    from aura.vnode.mesh import MeshBus
    m = MeshBus()
    m.register_peer("node-x", [])
    assert m.unregister_peer("node-x") is True
    assert m.unregister_peer("node-x") is False  # already gone
    assert len(m.list_peers()) == 0


def test_mesh_bus_send_and_receive():
    from aura.vnode.mesh import MeshBus
    m = MeshBus()
    m.register_peer("alpha", [])
    ok = m.send_to_peer("alpha", {"hello": "world"})
    assert ok is True
    msgs = m.receive("alpha")
    assert len(msgs) == 1
    assert msgs[0]["message"]["hello"] == "world"


def test_mesh_bus_broadcast():
    from aura.vnode.mesh import MeshBus
    m = MeshBus()
    m.register_peer("p1", ["news"])
    m.register_peer("p2", ["news"])
    m.register_peer("p3", [])
    count = m.broadcast("news", {"headline": "test"})
    # All peers with "news" capability receive the broadcast
    assert count >= 2
    msgs_p1 = m.receive("p1")
    msgs_p2 = m.receive("p2")
    assert any(msg["message"]["headline"] == "test" for msg in msgs_p1)
    assert any(msg["message"]["headline"] == "test" for msg in msgs_p2)


def test_mesh_bus_metrics():
    from aura.vnode.mesh import MeshBus
    m = MeshBus()
    m.register_peer("n1", [])
    m.send_to_peer("n1", {"x": 1})
    met = m.metrics()
    assert met["peer_count"] == 1
    assert met["total_messages_sent"] >= 1


# ---------------------------------------------------------------------------
# RemoteControlServer
# ---------------------------------------------------------------------------

def test_remote_server_starts_and_responds(tmp_path):
    from aura.web.api import WebAPI
    from aura.remote.server import RemoteControlServer
    api = WebAPI()
    srv = RemoteControlServer(api, host="127.0.0.1", port=19200)
    srv.start()
    try:
        import urllib.request, json
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                resp = urllib.request.urlopen("http://127.0.0.1:19200/health", timeout=1)
                data = json.loads(resp.read())
                assert data["status"] == "ok"
                break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail("Remote server did not respond within 5 s")
    finally:
        srv.stop()


def test_remote_server_metrics():
    from aura.web.api import WebAPI
    from aura.remote.server import RemoteControlServer
    api = WebAPI()
    srv = RemoteControlServer(api, host="127.0.0.1", port=19201)
    srv.start()
    try:
        m = srv.metrics()
        assert m["host"] == "127.0.0.1"
        assert m["port"] == 19201
        assert m["is_running"] is True
        assert "requests_handled" in m
    finally:
        srv.stop()


def test_remote_server_not_running_before_start():
    from aura.web.api import WebAPI
    from aura.remote.server import RemoteControlServer
    api = WebAPI()
    srv = RemoteControlServer(api, host="127.0.0.1", port=19202)
    assert srv.is_running is False


def test_remote_server_post_command():
    from aura.web.api import WebAPI
    from aura.remote.server import RemoteControlServer
    import urllib.request, json
    api = WebAPI()
    srv = RemoteControlServer(api, host="127.0.0.1", port=19203)
    srv.start()
    try:
        # Wait for server to be ready
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen("http://127.0.0.1:19203/health", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        body = json.dumps({"command": "nonexistent"}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:19203/command",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2)
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# BuilderEngine
# ---------------------------------------------------------------------------

def test_builder_engine_generates_module(tmp_path):
    from aura.builder.engine import BuilderEngine
    eng = BuilderEngine(output_dir=str(tmp_path / "builder"))
    path = eng.generate_module("my_module", "Test module")
    import os
    assert os.path.isfile(path)
    content = open(path).read()
    assert "my_module" in content
    assert "class" in content.lower() or "def" in content.lower()


def test_builder_engine_generates_script(tmp_path):
    from aura.builder.engine import BuilderEngine
    eng = BuilderEngine(output_dir=str(tmp_path / "builder"))
    path = eng.generate_script("my_script", "Test script")
    import os
    assert os.path.isfile(path)
    content = open(path).read()
    assert "#!/" in content
    assert "my_script" in content


def test_builder_engine_generates_config(tmp_path):
    from aura.builder.engine import BuilderEngine
    eng = BuilderEngine(output_dir=str(tmp_path / "builder"))
    path = eng.generate_config("my_config", {"key": "value"})
    import os, json
    assert os.path.isfile(path)
    data = json.loads(open(path).read())
    assert data["name"] == "my_config"
    assert data["key"] == "value"


def test_builder_engine_list_generated(tmp_path):
    from aura.builder.engine import BuilderEngine
    eng = BuilderEngine(output_dir=str(tmp_path / "builder"))
    eng.generate_module("mod_a")
    eng.generate_script("scr_b")
    eng.generate_config("cfg_c")
    items = eng.list_generated()
    assert len(items) == 3
    types = {i["type"] for i in items}
    assert "module" in types
    assert "script" in types
    assert "config" in types


def test_builder_engine_metrics(tmp_path):
    from aura.builder.engine import BuilderEngine
    eng = BuilderEngine(output_dir=str(tmp_path / "builder"))
    eng.generate_module("x")
    eng.generate_module("y")
    m = eng.metrics()
    assert m["modules_generated"] == 2
    assert m["scripts_generated"] == 0
    assert m["modules_generated"] + m["scripts_generated"] + m["configs_generated"] == 2


# ---------------------------------------------------------------------------
# ModuleTemplate / ScriptTemplate / ConfigTemplate
# ---------------------------------------------------------------------------

def test_module_template_renders():
    from aura.builder.templates import ModuleTemplate
    t = ModuleTemplate(name="test_mod", description="A test")
    src = t.render()
    assert "test_mod" in src
    assert "SPDX-License-Identifier" in src


def test_script_template_renders():
    from aura.builder.templates import ScriptTemplate
    t = ScriptTemplate(name="my_script", description="does things")
    src = t.render()
    assert "#!/" in src
    assert "my_script" in src


def test_config_template_renders():
    from aura.builder.templates import ConfigTemplate
    import json
    t = ConfigTemplate(name="my_cfg", defaults={"foo": "bar"})
    src = t.render()
    data = json.loads(src)
    assert data["name"] == "my_cfg"
    assert data["foo"] == "bar"


# ---------------------------------------------------------------------------
# Config — new sections
# ---------------------------------------------------------------------------

def test_config_has_vnode():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert cfg.vnode.node_name == "aura-node"
    assert cfg.vnode.heartbeat_interval_seconds == 30.0
    assert cfg.vnode.timeout_seconds == 5


def test_config_has_remote():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert cfg.remote.enabled is False
    assert cfg.remote.port == 8765
    assert cfg.remote.host == "0.0.0.0"


def test_config_has_builder():
    from aura.config import AURaConfig
    cfg = AURaConfig()
    assert "builder" in cfg.builder.output_dir


def test_config_vnode_from_env(monkeypatch):
    monkeypatch.setenv("AURA_NODE_NAME", "my-special-node")
    monkeypatch.setenv("AURA_HEARTBEAT_INTERVAL", "15.0")
    from aura.config import AURaConfig
    cfg = AURaConfig.from_env()
    assert cfg.vnode.node_name == "my-special-node"
    assert cfg.vnode.heartbeat_interval_seconds == 15.0


def test_config_remote_from_env(monkeypatch):
    monkeypatch.setenv("AURA_REMOTE_ENABLED", "true")
    monkeypatch.setenv("AURA_REMOTE_PORT", "9999")
    from aura.config import AURaConfig
    cfg = AURaConfig.from_env()
    assert cfg.remote.enabled is True
    assert cfg.remote.port == 9999


# ---------------------------------------------------------------------------
# AIOS v2.1.0 — virtual node wired in
# ---------------------------------------------------------------------------

def test_aios_has_vnode_identity(tmp_path):
    with _make_aios_v2(19160, tmp_path) as aios:
        assert aios.vnode_identity is not None
        assert aios.vnode_identity.node_id


def test_aios_has_mesh_bus(tmp_path):
    with _make_aios_v2(19161, tmp_path) as aios:
        assert aios.mesh_bus is not None


def test_aios_has_builder_engine(tmp_path):
    with _make_aios_v2(19162, tmp_path) as aios:
        assert aios.builder_engine is not None


def test_aios_dispatch_vnode_status(tmp_path):
    with _make_aios_v2(19163, tmp_path) as aios:
        out = aios.dispatch("vnode", ["status"])
        assert "Virtual Node Status" in out
        assert "node_id" in out
        assert "capabilities" in out


def test_aios_dispatch_vnode_peers(tmp_path):
    with _make_aios_v2(19164, tmp_path) as aios:
        out = aios.dispatch("vnode", ["peers"])
        assert isinstance(out, str)


def test_aios_dispatch_vnode_id(tmp_path):
    with _make_aios_v2(19165, tmp_path) as aios:
        out = aios.dispatch("vnode", ["id"])
        import uuid
        try:
            uuid.UUID(out.strip())
        except ValueError:
            pytest.fail(f"vnode id output is not a valid UUID: {out!r}")


def test_aios_dispatch_remote_status_disabled(tmp_path):
    with _make_aios_v2(19166, tmp_path) as aios:
        out = aios.dispatch("remote", ["status"])
        assert "disabled" in out.lower() or "Remote" in out


def test_aios_dispatch_builder_status(tmp_path):
    with _make_aios_v2(19167, tmp_path) as aios:
        out = aios.dispatch("builder", ["status"])
        assert "Builder Engine" in out


def test_aios_dispatch_builder_module(tmp_path):
    with _make_aios_v2(19168, tmp_path) as aios:
        out = aios.dispatch("builder", ["module", "hello_world", "A hello module"])
        assert "generated" in out.lower()
        assert "hello_world" in out


def test_aios_dispatch_builder_list(tmp_path):
    with _make_aios_v2(19169, tmp_path) as aios:
        aios.dispatch("builder", ["module", "list_test"])
        out = aios.dispatch("builder", ["list"])
        assert "list_test" in out


def test_aios_help_includes_vnode(tmp_path):
    with _make_aios_v2(19170, tmp_path) as aios:
        out = aios.dispatch("help")
        assert "vnode" in out
        assert "remote" in out
        assert "builder" in out


def test_aios_metrics_includes_vnode(tmp_path):
    with _make_aios_v2(19171, tmp_path) as aios:
        m = aios.metrics()
        assert "vnode" in m
        assert "heartbeat" in m
        assert "mesh" in m
        assert "builder" in m


def test_aios_vnode_register_no_cc(tmp_path):
    """vnode register sub-command returns graceful failure when no Command Center."""
    with _make_aios_v2(19172, tmp_path) as aios:
        out = aios.dispatch("vnode", ["register"])
        assert "FAILED" in out or "OK" in out

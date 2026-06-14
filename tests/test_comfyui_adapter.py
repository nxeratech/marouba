from __future__ import annotations

import json
from pathlib import Path

from engine.comfyui_adapter import ComfyUIAdapter, capture_events_from_graphs, captured_workflow
from engine.executor import Executor
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeComfyClient:
    def __init__(self) -> None:
        self.prompts = []
        self.counter = 0

    def post_prompt(self, payload: dict) -> dict:
        self.counter += 1
        prompt_id = f"prompt-{self.counter}"
        self.prompts.append(payload)
        return {"prompt_id": prompt_id}

    def get_history(self, prompt_id: str) -> dict:
        return {prompt_id: {"status": {"completed": True}, "outputs": {}}}


def before_graph() -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old prompt", "clip": ["1", 1]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20, "cfg": 7.0, "positive": ["2", 0]}},
    }


def after_graph() -> dict:
    graph = before_graph()
    graph["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "dark techno bassline", "clip": ["1", 1]}}
    graph["3"] = {"class_type": "KSampler", "inputs": {"seed": 99, "steps": 30, "cfg": 8.5, "positive": ["2", 0]}}
    graph["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 512, "batch_size": 1}}
    graph["5"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0]}}
    graph["6"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "marouba", "images": ["5", 0]}}
    return graph


def test_comfyui_capture_10_edit_session_is_node_level_r1_not_gesture() -> None:
    events = capture_events_from_graphs(
        before_graph(),
        after_graph(),
        [
            {"type": "execution_start", "data": {"prompt_id": "p1"}},
            {"type": "execution_success", "data": {"prompt_id": "p1"}},
            {"type": "execution_start", "data": {"prompt_id": "p1"}},
        ],
    )

    assert len(events) == 10
    assert {event["route_tier"] for event in events} == {"r1"}
    assert "gesture" not in json.dumps(events).casefold()
    assert [event["kind"] for event in events].count("node_added") == 3
    assert [event["kind"] for event in events].count("param_changed") == 4
    assert any(event["kind"] == "queue_requeue" and event["taste_signal"] for event in events)


def test_comfyui_replay_submits_exact_graph_with_param_slots() -> None:
    client = FakeComfyClient()
    adapter = ComfyUIAdapter(client=client)
    graph = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "{prompt}"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": "{seed}", "positive": ["1", 0]}},
    }

    result = adapter.execute(
        {"type": "adapter", "adapter": "comfyui", "graph": graph, "client_id": "marouba-{seed}"},
        {"prompt": "dark techno bassline", "seed": 123},
        {"verification": {"timeout_seconds": 3}},
    )

    assert result["success"] is True
    assert client.prompts == [
        {
            "client_id": "marouba-123",
            "prompt": {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "dark techno bassline"}},
                "2": {"class_type": "KSampler", "inputs": {"seed": "123", "positive": ["1", 0]}},
            },
        }
    ]


def test_executor_comfyui_adapter_route_does_not_require_browser_pixels(monkeypatch, tmp_path: Path) -> None:
    client = FakeComfyClient()
    monkeypatch.setattr("engine.executor.ComfyUIAdapter", lambda: ComfyUIAdapter(client=client))
    executor = Executor(tmp_path)
    route = {"type": "adapter", "adapter": "comfyui", "graph": after_graph()}

    result = executor.execute(route, {}, {"id": "comfy", "app": "ComfyUI", "verification": {"timeout_seconds": 3}})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "snapshot" not in json.dumps(client.prompts).casefold()
    assert "pixel" not in json.dumps(client.prompts).casefold()


def test_comfyui_fake_20_run_soak_meets_threshold() -> None:
    client = FakeComfyClient()
    adapter = ComfyUIAdapter(client=client)
    successes = 0
    for index in range(20):
        result = adapter.execute(
            {"type": "adapter", "adapter": "comfyui", "graph": after_graph(), "wait_for_history": True},
            {"run": index},
            {"verification": {"timeout_seconds": 3}},
        )
        successes += int(result["success"])

    assert successes / 20 >= 0.95
    assert len(client.prompts) == 20


def test_captured_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_graphs(before_graph(), after_graph(), [])
    workflow = captured_workflow("Comfy Demo", after_graph(), events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "comfyui"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_comfyui_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("comfyui-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "comfyui"
        assert "visual" not in workflows[0]["fallback_order"]

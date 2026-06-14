from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.osc_transport import OscUdpClient, decode_osc_message, encode_osc_message
from engine.resolume_adapter import (
    ResolumeAdapter,
    capture_events_from_resolume_osc,
    captured_workflow,
    hash_osc_events,
)
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeOscClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, address: str, args: list | None = None) -> None:
        self.sent.append({"address": address, "args": args or []})


def resolume_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "resolume",
        "events": [
            {
                "route_tier": "r1",
                "app": "Resolume",
                "kind": "osc",
                "semantic": "clip_trigger",
                "address": "/composition/layers/1/clips/1/connect",
                "args": [1],
            },
            {
                "route_tier": "r1",
                "app": "Resolume",
                "kind": "osc",
                "semantic": "effect_param",
                "address": "/composition/layers/1/video/effects/1/params/1",
                "args": ["{effect_amount}"],
            },
            {
                "route_tier": "r1",
                "app": "Resolume",
                "kind": "osc",
                "semantic": "layer_param",
                "address": "/composition/layers/1/opacity",
                "args": [0.85],
            },
            {
                "route_tier": "r1",
                "app": "Resolume",
                "kind": "osc",
                "semantic": "composition_param",
                "address": "/composition/tempocontroller/tempo",
                "args": [128.0],
            },
        ],
    }


def test_shared_osc_transport_round_trips_typed_messages() -> None:
    encoded = encode_osc_message("/composition/layers/1/opacity", [0.85, 7, "mix", True, False])
    decoded = decode_osc_message(encoded)

    assert decoded.address == "/composition/layers/1/opacity"
    assert decoded.args[0] == pytest.approx(0.85)
    assert decoded.args[1:] == [7, "mix", True, False]


def test_resolume_capture_maps_clip_effect_layer_and_composition_events_to_r1() -> None:
    events = capture_events_from_resolume_osc(
        [
            {"address": "/composition/layers/1/clips/1/connect", "args": [1]},
            {"address": "/composition/layers/1/video/effects/1/params/1", "args": [0.5]},
            {"address": "/composition/layers/1/opacity", "args": [0.85]},
            {"address": "/composition/tempocontroller/tempo", "args": [128.0]},
        ]
    )

    assert {event["route_tier"] for event in events} == {"r1"}
    assert [event["semantic"] for event in events] == [
        "clip_trigger",
        "effect_param",
        "layer_param",
        "composition_param",
    ]


def test_resolume_refuses_unreadable_exposed_values() -> None:
    with pytest.raises(RuntimeError, match="value unreadable"):
        ResolumeAdapter(client=FakeOscClient()).execute(
            {
                "type": "adapter",
                "adapter": "resolume",
                "events": [
                    {
                        "route_tier": "r1",
                        "address": "/composition/layers/1/video/effects/1/params/1",
                        "args": [0.5],
                        "value_status": "unreadable",
                    }
                ],
            },
            {},
            {},
        )


def test_resolume_replay_uses_shared_osc_client_and_preserves_exact_values() -> None:
    client = FakeOscClient()
    result = ResolumeAdapter(client=client).execute(resolume_route(), {"effect_amount": 0.72}, {})

    expected = [
        {"address": "/composition/layers/1/clips/1/connect", "args": [1], "semantic": "clip_trigger"},
        {"address": "/composition/layers/1/video/effects/1/params/1", "args": [0.72], "semantic": "effect_param"},
        {"address": "/composition/layers/1/opacity", "args": [0.85], "semantic": "layer_param"},
        {"address": "/composition/tempocontroller/tempo", "args": [128.0], "semantic": "composition_param"},
    ]
    assert isinstance(ResolumeAdapter().client, OscUdpClient)
    assert client.sent == [{"address": item["address"], "args": item["args"]} for item in expected]
    assert result["events_replayed"] == 4
    assert result["osc_hash"] == hash_osc_events(expected)
    assert result["route_used"] == "r1:shared-osc-udp"


def test_executor_resolume_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    client = FakeOscClient()
    monkeypatch.setattr("engine.executor.ResolumeAdapter", lambda: ResolumeAdapter(client=client))

    result = Executor(tmp_path).execute(resolume_route(), {"effect_amount": 0.72}, {"app": "Resolume"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "gesture" not in json.dumps(result).casefold()


def test_resolume_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        result = ResolumeAdapter(client=FakeOscClient()).execute(
            resolume_route(),
            {"effect_amount": round(index / 20, 2)},
            {},
        )
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_resolume_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_resolume_osc(
        [{"address": "/composition/layers/1/clips/1/connect", "args": [1]}]
    )
    workflow = captured_workflow("Resolume Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "resolume"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_resolume_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("resolume-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "resolume"
        assert "visual" not in workflows[0]["fallback_order"]

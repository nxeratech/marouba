from __future__ import annotations

from engine.router import Router


def workflow() -> dict:
    return {
        "routes": [
            {"type": "api", "endpoint": "http://127.0.0.1:8188/prompt"},
            {"type": "cli", "command": "python comfyui_client.py"},
            {"type": "uia", "element": "queue-prompt-button"},
            {"type": "visual", "snapshot": "snapshots/comfyui-queue-button.png"},
        ],
        "fallback_order": ["api", "cli", "uia", "visual", "ask"],
    }


def test_api_available_returns_api_first() -> None:
    router = Router(
        {
            "api": lambda route: True,
            "cli": lambda route: True,
            "uia": lambda route: False,
            "visual": lambda route: False,
        }
    )

    order = router.route_order(workflow())

    assert [route["type"] for route in order] == ["api", "cli", "ask"]


def test_api_unavailable_returns_cli_first() -> None:
    router = Router(
        {
            "api": lambda route: False,
            "cli": lambda route: True,
            "uia": lambda route: False,
            "visual": lambda route: False,
        }
    )

    order = router.route_order(workflow())

    assert [route["type"] for route in order] == ["cli", "ask"]


def test_all_unavailable_returns_ask() -> None:
    router = Router(
        {
            "api": lambda route: False,
            "cli": lambda route: False,
            "uia": lambda route: False,
            "visual": lambda route: False,
        }
    )

    order = router.route_order(workflow())

    assert [route["type"] for route in order] == ["ask"]

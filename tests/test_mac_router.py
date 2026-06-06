from __future__ import annotations

from engine import router as router_module
from engine.router import Router


def workflow() -> dict:
    return {
        "routes": [
            {"type": "uia", "app_window": "Demo", "element": "Run"},
            {"type": "macos_uia", "app_window": "Demo", "element": "Run"},
            {"type": "shortcut", "keys": ["ctrl", "enter"]},
        ],
        "fallback_order": ["uia", "macos_uia", "shortcut", "ask"],
    }


def test_on_darwin_macos_uia_preferred_over_uia(monkeypatch) -> None:
    monkeypatch.setattr(router_module.sys, "platform", "darwin")
    router = Router(
        {
            "uia": lambda route: True,
            "macos_uia": lambda route: True,
            "shortcut": lambda route: True,
        }
    )

    order = router.route_order(workflow())

    assert [route["type"] for route in order] == ["macos_uia", "uia", "shortcut", "ask"]


def test_on_win32_uia_preferred_over_macos_uia(monkeypatch) -> None:
    monkeypatch.setattr(router_module.sys, "platform", "win32")
    router = Router(
        {
            "uia": lambda route: True,
            "macos_uia": lambda route: True,
            "shortcut": lambda route: True,
        }
    )

    order = router.route_order(
        {
            "routes": workflow()["routes"],
            "fallback_order": ["macos_uia", "uia", "shortcut", "ask"],
        }
    )

    assert [route["type"] for route in order] == ["uia", "macos_uia", "shortcut", "ask"]

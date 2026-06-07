from __future__ import annotations

import importlib.util
import sys
from shutil import which
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from engine.companion_client import CompanionClient


AvailabilityChecker = Callable[[dict[str, Any]], bool]


def api_available(route: dict[str, Any], timeout: float = 1.0) -> bool:
    endpoint = route.get("endpoint")
    if not endpoint:
        return False

    base = str(endpoint).split("/prompt", 1)[0]
    request = Request(f"{base}/system_stats", method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (OSError, URLError, ValueError):
        return False


def cli_available(route: dict[str, Any]) -> bool:
    command = str(route.get("command", "")).strip()
    if not command:
        return False
    executable = command.split()[0].strip("\"'")
    return which(executable) is not None


def uia_available(route: dict[str, Any]) -> bool:
    if CompanionClient().health():
        return True

    if importlib.util.find_spec("pywinauto") is None:
        return False

    try:
        from pywinauto import Desktop

        window_title = route.get("app_window") or route.get("window_title")
        element_name = route.get("element") or route.get("name")
        control_type = route.get("role") or route.get("control_type")
        if not window_title or not element_name:
            return False

        desktop = Desktop(backend="uia")
        windows = desktop.windows(title_re=f".*{window_title}.*")
        if not windows:
            return False

        criteria = {"title": element_name}
        if control_type:
            criteria["control_type"] = control_type
        return windows[0].child_window(**criteria).exists(timeout=1)
    except Exception:
        return False


def macos_uia_available(route: dict[str, Any]) -> bool:
    return CompanionClient().health()


def keyboard_available(_: dict[str, Any]) -> bool:
    return importlib.util.find_spec("pyautogui") is not None or importlib.util.find_spec("keyboard") is not None


def manual_repair_available(route: dict[str, Any]) -> bool:
    return bool(route.get("failure_signature"))


def visual_available(route: dict[str, Any]) -> bool:
    return bool(route.get("coordinates")) and importlib.util.find_spec("pyautogui") is not None


def gesture_available(route: dict[str, Any]) -> bool:
    return bool(route.get("events"))


def unavailable(_: dict[str, Any]) -> bool:
    return False


DEFAULT_CHECKERS: dict[str, AvailabilityChecker] = {
    "api": api_available,
    "cli": cli_available,
    "uia": uia_available,
    "macos_uia": macos_uia_available,
    "keyboard": keyboard_available,
    "shortcut": keyboard_available,
    "manual_repair": manual_repair_available,
    "visual": visual_available,
    "gesture": gesture_available,
}


class Router:
    def __init__(self, checkers: dict[str, AvailabilityChecker] | None = None) -> None:
        self.checkers = dict(DEFAULT_CHECKERS)
        if checkers:
            self.checkers.update(checkers)

    def route_order(self, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        routes = workflow.get("routes", [])
        ordered_routes: list[dict[str, Any]] = []

        for route_type in self.platform_fallback_order(workflow):
            if route_type == "ask":
                continue
            for route in routes:
                if route.get("type") != route_type:
                    continue
                checker = self.checkers.get(route_type, unavailable)
                if checker(route):
                    ordered_routes.append(route)

        for route in routes:
            if route.get("type") == "gesture" and route not in ordered_routes:
                checker = self.checkers.get("gesture", unavailable)
                if checker(route):
                    ordered_routes.append(route)

        ordered_routes.append({"type": "ask"})
        return ordered_routes

    def platform_fallback_order(self, workflow: dict[str, Any]) -> list[str]:
        order = list(workflow.get("fallback_order", []))
        if sys.platform == "darwin":
            return self._prefer(order, "macos_uia", "uia")
        if sys.platform == "win32":
            return self._prefer(order, "uia", "macos_uia")
        return order

    def _prefer(self, order: list[str], preferred: str, secondary: str) -> list[str]:
        if preferred not in order or secondary not in order:
            return order
        preferred_index = order.index(preferred)
        secondary_index = order.index(secondary)
        if preferred_index < secondary_index:
            return order
        order.pop(preferred_index)
        secondary_index = order.index(secondary)
        order.insert(secondary_index, preferred)
        return order

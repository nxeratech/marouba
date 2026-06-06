from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    if command == "window":
        print_json(active_window())
        return 0
    if command == "find":
        print_json(find_element(payload))
        return 0
    if command == "click":
        print_json(click_element(payload))
        return 0

    print_json({"ok": False, "error": f"unknown command: {command}"})
    return 1


def active_window() -> dict[str, Any]:
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return {
            "ok": True,
            "title": app.localizedName() if app else "unknown",
            "app_name": app.localizedName() if app else "unknown",
        }
    except Exception as exc:
        return {"ok": False, "title": "unknown", "app_name": "unknown", "error": str(exc)}


def find_element(payload: dict[str, Any]) -> dict[str, Any]:
    element = _find_ax_element(payload)
    if element is None:
        return {"ok": False, "found": False, "error": "element not found"}
    return {
        "ok": True,
        "found": True,
        "name": payload.get("name"),
        "role": payload.get("role"),
        "window_title": payload.get("window_title"),
    }


def click_element(payload: dict[str, Any]) -> dict[str, Any]:
    element = _find_ax_element(payload)
    if element is None:
        return {"ok": False, "clicked": False, "error": "element not found"}

    try:
        import Quartz

        Quartz.AXUIElementPerformAction(element, "AXPress")
        return {"ok": True, "clicked": True}
    except Exception as exc:
        return {"ok": False, "clicked": False, "error": str(exc)}


def _find_ax_element(payload: dict[str, Any]) -> Any:
    try:
        import Quartz
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        ax_app = Quartz.AXUIElementCreateApplication(app.processIdentifier())
        target_name = payload.get("name")
        target_role = payload.get("role")
        return _walk(ax_app, target_name, target_role, Quartz)
    except Exception:
        return None


def _walk(element: Any, target_name: str | None, target_role: str | None, quartz: Any) -> Any:
    name = _copy_attribute(element, "AXTitle", quartz) or _copy_attribute(element, "AXDescription", quartz)
    role = _copy_attribute(element, "AXRole", quartz)
    if target_name and name == target_name and (not target_role or role == target_role):
        return element

    children = _copy_attribute(element, "AXChildren", quartz) or []
    for child in children:
        found = _walk(child, target_name, target_role, quartz)
        if found is not None:
            return found
    return None


def _copy_attribute(element: Any, attr: str, quartz: Any) -> Any:
    try:
        error, value = quartz.AXUIElementCopyAttributeValue(element, attr, None)
        if error == 0:
            return value
    except Exception:
        return None
    return None


def print_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    raise SystemExit(main())

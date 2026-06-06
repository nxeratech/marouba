from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.companion_client import CompanionClient, CompanionUnavailable
from engine.vault import Vault


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "untitled-workflow"


class TeachingSession:
    def __init__(self, name: str, app: str, root: Path = ROOT, vault: Vault | None = None) -> None:
        self.name = name
        self.app = app
        self.root = root
        self.vault = vault or Vault(root)
        self.workflow_id = slugify(name)
        self.actions: list[dict[str, Any]] = []

    def capture_action(self, action: dict[str, Any]) -> None:
        self.actions.append(action)
        print(f"[Marouba] Captured: {self.describe_action(action)}")

    def describe_action(self, action: dict[str, Any]) -> str:
        action_type = action.get("type")
        if action_type == "ui_click":
            return f"UI click {action.get('element')} in {action.get('window_title')}"
        if action_type == "shortcut":
            return f"shortcut {action.get('keys')}"
        if action_type == "mouse_click":
            return f"mouse click ({action.get('x')}, {action.get('y')})"
        if action_type == "http_request":
            return f"HTTP {action.get('method', 'GET')} {action.get('endpoint')}"
        return str(action)

    def save_workflow(self) -> Path:
        workflow = self.build_workflow()
        return self.vault.save_workflow(workflow, filename=f"{self.workflow_id}.md")

    def build_workflow(self) -> dict[str, Any]:
        routes = [route for action in self.actions if (route := self.action_to_route(action))]
        fallback_order = self.fallback_order(routes)
        today = date.today().isoformat()
        return {
            "id": self.workflow_id,
            "name": self.name,
            "app": self.app,
            "app_version": "unknown",
            "author": "nxeratech",
            "category": "taught-workflow",
            "tags": ["taught", slugify(self.app)],
            "last_verified": today,
            "created": today,
            "routes": routes,
            "fallback_order": fallback_order,
            "verification": {"type": "none"},
            "calls": [],
            "depends_on": [],
            "body": f"# {self.name}\n\nCaptured by Marouba Teach mode.\n",
        }

    def action_to_route(self, action: dict[str, Any]) -> dict[str, Any] | None:
        action_type = action.get("type")
        if action_type == "ui_click":
            return {
                "type": "uia",
                "app_window": action.get("window_title") or self.app,
                "element": action.get("element") or action.get("name"),
                "role": action.get("role") or action.get("control_type"),
            }
        if action_type == "shortcut":
            return {"type": "shortcut", "keys": action.get("keys") or action.get("sequence")}
        if action_type == "mouse_click":
            return {
                "type": "visual",
                "coordinates": {"x": int(action.get("x", 0)), "y": int(action.get("y", 0))},
                "button": action.get("button", "left"),
            }
        if action_type == "http_request":
            return {
                "type": "api",
                "endpoint": action.get("endpoint"),
                "method": action.get("method", "GET"),
                "payload_template": action.get("payload_template"),
            }
        return None

    def fallback_order(self, routes: list[dict[str, Any]]) -> list[str]:
        preferred = ["api", "uia", "shortcut", "keyboard", "visual"]
        seen = {route.get("type") for route in routes}
        ordered = [route_type for route_type in preferred if route_type in seen]
        ordered.append("ask")
        return ordered


class Recorder:
    def __init__(self, session: TeachingSession) -> None:
        self.session = session
        self._mouse_listener = None
        self.companion = CompanionClient()

    def start(self) -> None:
        print("[Marouba] Recording started. Type 'done' and press Enter, or press Ctrl+C, to save.")
        self._print_active_window()
        self._start_keyboard_hook()
        self._start_mouse_hook()

    def stop(self) -> None:
        if self._mouse_listener:
            self._mouse_listener.stop()

    def _start_keyboard_hook(self) -> None:
        try:
            import keyboard

            keyboard.on_hotkey("ctrl+s", lambda: self.session.capture_action({"type": "shortcut", "keys": ["ctrl", "s"]}))
            keyboard.on_hotkey(
                "ctrl+enter", lambda: self.session.capture_action({"type": "shortcut", "keys": ["ctrl", "enter"]})
            )
        except Exception as exc:
            print(f"[Marouba] Keyboard capture unavailable: {exc}")

    def _start_mouse_hook(self) -> None:
        try:
            from pynput import mouse

            def on_click(x: int, y: int, button: Any, pressed: bool) -> None:
                if not pressed:
                    return
                ui_action = self._uia_action_at_point(x, y)
                if ui_action:
                    self.session.capture_action(ui_action)
                else:
                    self.session.capture_action(
                        {"type": "mouse_click", "x": x, "y": y, "button": str(button).split(".")[-1]}
                    )

            self._mouse_listener = mouse.Listener(on_click=on_click)
            self._mouse_listener.start()
        except Exception as exc:
            print(f"[Marouba] Mouse capture unavailable: {exc}")

    def _uia_action_at_point(self, x: int, y: int) -> dict[str, Any] | None:
        companion_action = self._companion_uia_action_at_point(x, y)
        if companion_action:
            return companion_action

        try:
            from pywinauto import Desktop

            element = Desktop(backend="uia").from_point(x, y)
            window = element.top_level_parent()
            name = element.window_text()
            if not name:
                return None
            return {
                "type": "ui_click",
                "window_title": window.window_text(),
                "element": name,
                "role": element.friendly_class_name(),
            }
        except Exception:
            return None

    def _companion_uia_action_at_point(self, x: int, y: int) -> dict[str, Any] | None:
        try:
            response = self.companion.find_uia({"x": x, "y": y})
        except CompanionUnavailable:
            return None

        if not response.get("found"):
            return None
        return {
            "type": "ui_click",
            "window_title": response.get("window_title"),
            "element": response.get("name"),
            "role": response.get("role"),
        }

    def _print_active_window(self) -> None:
        try:
            window = self.companion.window()
        except CompanionUnavailable:
            print("[Marouba] Companion window capture unavailable.")
            return

        app_name = window.get("app_name") or "unknown app"
        title = window.get("title") or "unknown window"
        print(f"[Marouba] Active app: {app_name} - {title}")


def run_replay_verification(workflow_id: str) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "replay.py"),
        "--workflow",
        workflow_id,
        "--params",
        "{}",
        "--no-repair",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Teach Marouba a workflow by recording one normal run.")
    parser.add_argument("--name", required=True, help="Workflow name")
    parser.add_argument("--app", required=True, help="Application name")
    args = parser.parse_args()

    session = TeachingSession(args.name, args.app)
    recorder = Recorder(session)
    recorder.start()

    try:
        while True:
            if input().strip().casefold() == "done":
                break
    except KeyboardInterrupt:
        print()
    finally:
        recorder.stop()

    saved_path = session.save_workflow()
    print(f"[Marouba] Workflow saved to {saved_path.relative_to(ROOT)}")
    print("[Marouba] Verifying replay from saved workflow...")
    replay_code = run_replay_verification(session.workflow_id)
    if replay_code == 0:
        print("[Marouba] Replay verified from saved workflow.")
    else:
        print("[Marouba] Replay verification did not complete cleanly; workflow remains saved for repair.")
    return replay_code


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
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
        description = self.describe_action(action).encode("ascii", errors="replace").decode("ascii")
        print(f"[Marouba] Captured: {description}")

    def describe_action(self, action: dict[str, Any]) -> str:
        action_type = action.get("type")
        if action_type == "ui_click":
            return f"UI click {action.get('element')} in {action.get('window_title')}"
        if action_type == "shortcut":
            return f"shortcut {action.get('keys')}"
        if action_type == "text":
            return f"text {action.get('text')!r}"
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
        routes = self.initial_routes() + routes
        fallback_order = self.fallback_order(routes)
        today = date.today().isoformat()
        return {
            "id": self.workflow_id,
            "name": self.name,
            "app": self.app,
            "mode": "sequence",
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

    def initial_routes(self) -> list[dict[str, Any]]:
        if slugify(self.app) == "notepad":
            output_path = self.root / f"{self.workflow_id}.txt"
            return [
                {
                    "type": "cli",
                    "command": f'cmd /c type nul > "{output_path}" && start "" notepad.exe "{output_path}"',
                    "wait_seconds": 2.0,
                    "focus_window": "Notepad",
                },
            ]
        return []

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
            keys = action.get("keys") or action.get("sequence")
            route = {"type": "shortcut", "keys": keys}
            if keys == ["ctrl", "s"]:
                route["wait_seconds"] = 1.5
            if keys == ["ctrl", "n"]:
                route["wait_seconds"] = 1.5
            return route
        if action_type == "text":
            return {"type": "keyboard", "text": action.get("text") or "", "interval": 0.04, "wait_before": 1.0}
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
        preferred = ["api", "cli", "uia", "shortcut", "keyboard", "visual"]
        seen = {route.get("type") for route in routes}
        ordered = [route_type for route_type in preferred if route_type in seen]
        ordered.append("ask")
        return ordered


class Recorder:
    def __init__(self, session: TeachingSession) -> None:
        self.session = session
        self._mouse_listener = None
        self._keyboard_listener = None
        self._keyboard = None
        self._keyboard_hook = None
        self._last_shortcut: tuple[str, float] | None = None
        self._text_buffer: list[str] = []
        self._pressed_modifiers: set[str] = set()
        self.companion = CompanionClient()

    def start(self) -> None:
        print("[Marouba] Recording started. Type 'done' and press Enter, or press Ctrl+C, to save.")
        self._print_active_window()
        self._start_keyboard_hook()
        self._start_mouse_hook()

    def stop(self) -> None:
        self._flush_text_buffer()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._keyboard and self._keyboard_hook:
            try:
                self._keyboard.unhook(self._keyboard_hook)
            except Exception:
                pass

    def _start_keyboard_hook(self) -> None:
        try:
            from pynput import keyboard as pynput_keyboard

            self._keyboard_listener = pynput_keyboard.Listener(
                on_press=self._capture_pynput_key_press,
                on_release=self._capture_pynput_key_release,
            )
            self._keyboard_listener.start()
            return
        except Exception as exc:
            print(f"[Marouba] Pynput keyboard capture unavailable: {exc}")

        try:
            import keyboard

            self._keyboard = keyboard
            for key in ("s", "z", "y", "a", "c", "v", "x", "n", "o", "p", "enter", "tab"):
                keyboard.add_hotkey(f"ctrl+{key}", self._capture_shortcut, args=(["ctrl", key],), suppress=False)
            for key in ("f4", "tab"):
                keyboard.add_hotkey(f"alt+{key}", self._capture_shortcut, args=(["alt", key],), suppress=False)
            self._keyboard_hook = keyboard.hook(self._capture_key_event, suppress=False)
        except Exception as exc:
            print(f"[Marouba] Keyboard capture unavailable: {exc}")

    def _capture_pynput_key_press(self, key: Any) -> None:
        try:
            from pynput import keyboard as pynput_keyboard
        except Exception:
            return

        if key in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
            self._pressed_modifiers.add("ctrl")
            return
        if key in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
            self._pressed_modifiers.add("alt")
            return
        if key in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
            self._pressed_modifiers.add("shift")
            return

        char = getattr(key, "char", None)
        if "ctrl" in self._pressed_modifiers and char:
            self._capture_shortcut(["ctrl", self._normalize_ctrl_char(char)])
            self._pressed_modifiers.discard("ctrl")
            return
        if "alt" in self._pressed_modifiers:
            name = self._normalize_ctrl_char(char) if char else str(key).replace("Key.", "")
            self._capture_shortcut(["alt", name])
            self._pressed_modifiers.discard("alt")
            return

        if key == pynput_keyboard.Key.enter:
            self._text_buffer.append("\n")
            return
        if key == pynput_keyboard.Key.space:
            self._text_buffer.append(" ")
            return
        if key == pynput_keyboard.Key.backspace:
            if self._text_buffer:
                self._text_buffer.pop()
            return
        if key == pynput_keyboard.Key.tab:
            self._text_buffer.append("\t")
            return
        if char:
            self._text_buffer.append(char)

    def _normalize_ctrl_char(self, char: str) -> str:
        if len(char) == 1:
            code = ord(char)
            if 1 <= code <= 26:
                return chr(code + 96)
        return char.casefold()

    def _capture_pynput_key_release(self, key: Any) -> None:
        try:
            from pynput import keyboard as pynput_keyboard
        except Exception:
            return

        if key in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
            self._pressed_modifiers.discard("ctrl")
        elif key in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
            self._pressed_modifiers.discard("alt")
        elif key in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
            self._pressed_modifiers.discard("shift")

    def _capture_shortcut(self, keys: list[str]) -> None:
        joined = "+".join(keys)
        now = time.monotonic()
        if self._last_shortcut and self._last_shortcut[0] == joined and now - self._last_shortcut[1] < 0.4:
            return
        self._last_shortcut = (joined, now)
        self._flush_text_buffer()
        self.session.capture_action({"type": "shortcut", "keys": keys})

    def _capture_key_event(self, event: Any) -> None:
        if getattr(event, "event_type", None) != "down":
            return
        name = str(getattr(event, "name", "") or "")
        if not name:
            return
        if self._is_modifier_down():
            return
        if name == "space":
            self._text_buffer.append(" ")
            return
        if name == "enter":
            self._text_buffer.append("\n")
            return
        if name == "backspace":
            if self._text_buffer:
                self._text_buffer.pop()
            return
        if len(name) == 1:
            self._text_buffer.append(name.upper() if self._is_shift_down() else name)

    def _flush_text_buffer(self) -> None:
        if not self._text_buffer:
            return
        text = "".join(self._text_buffer)
        self._text_buffer.clear()
        if text:
            self.session.capture_action({"type": "text", "text": text})

    def _is_modifier_down(self) -> bool:
        if not self._keyboard:
            return False
        for key in ("ctrl", "alt", "windows"):
            try:
                if self._keyboard.is_pressed(key):
                    return True
            except Exception:
                return False
        return False

    def _is_shift_down(self) -> bool:
        if not self._keyboard:
            return False
        try:
            return bool(self._keyboard.is_pressed("shift"))
        except Exception:
            return False

    def _start_mouse_hook(self) -> None:
        try:
            from pynput import mouse

            def on_click(x: int, y: int, button: Any, pressed: bool) -> None:
                if not pressed:
                    return
                self._flush_text_buffer()
                ui_action = self._uia_action_at_point(x, y)
                if ui_action and ui_action.get("type") == "_ignore":
                    return
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
        window_title = response.get("window_title") or ""
        element = response.get("name")
        if self._is_infrastructure_window(window_title) or self._is_infrastructure_window(str(element or "")):
            return {"type": "_ignore"}
        if self._is_outside_target_app(window_title):
            return {"type": "_ignore"}
        if not element:
            return None
        return {
            "type": "ui_click",
            "window_title": window_title,
            "element": element,
            "role": response.get("role"),
        }

    def _is_infrastructure_window(self, window_title: str) -> bool:
        title = slugify(window_title)
        return "codex" in title or "marouba-companion" in title

    def _is_outside_target_app(self, window_title: str) -> bool:
        app_slug = slugify(self.session.app)
        if app_slug in {"browser", "chrome", "edge"}:
            return False
        title = slugify(window_title)
        if not title:
            return False
        if app_slug == "photoshop":
            return "photoshop" not in title and "adobe" not in title
        return app_slug not in title

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
    parser.add_argument("--verify", action="store_true", help="Immediately replay the saved workflow after recording")
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
    if not args.verify:
        return 0
    print("[Marouba] Verifying replay from saved workflow...")
    replay_code = run_replay_verification(session.workflow_id)
    if replay_code == 0:
        print("[Marouba] Replay verified from saved workflow.")
    else:
        print("[Marouba] Replay verification did not complete cleanly; workflow remains saved for repair.")
    return replay_code


if __name__ == "__main__":
    raise SystemExit(main())

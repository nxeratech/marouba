from __future__ import annotations

import json
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from engine.companion_client import CompanionClient
from engine.blender_adapter import BlenderAdapter
from engine.comfyui_adapter import ComfyUIAdapter
from engine.obs_adapter import ObsAdapter
from engine.reaper_adapter import ReaperAdapter
from engine.resolume_adapter import ResolumeAdapter
from engine.resolve_adapter import ResolveAdapter
from engine.touchdesigner_adapter import TouchDesignerAdapter


class Executor:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).resolve().parents[1]
        self.companion = CompanionClient()

    def execute(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        source = workflow.get("source", "self_taught")
        try:
            route = self._substitute(route, params)
            if source == "marketplace" and route.get("type") in {"shortcut", "visual", "keyboard"}:
                workflow_id = workflow.get("id", "unknown")
                print(
                    "[Marouba] WARNING: executing input-injecting route from marketplace "
                    f"workflow {workflow_id} — ensure you trust this profile"
                )
            if route.get("type") == "adapter":
                output = self._execute_adapter(route, params, workflow)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "api":
                output = self._execute_api(route, params, workflow)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "cli":
                output = self._execute_cli(route, params)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") in {"uia", "macos_uia"}:
                output = self._execute_uia(route, params)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") in {"keyboard", "shortcut"}:
                output = self._execute_keyboard(route, params)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "visual":
                output = self._execute_visual(route, params)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "gesture":
                output = self._execute_gesture(route, params)
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "manual_repair":
                output = params.get("output_path") or route.get("output")
                return self._result(True, output=output, started=start, route=route, source=source)
            if route.get("type") == "ask":
                raise RuntimeError("Ask route reached; repair loop handles this outside the executor")
            raise NotImplementedError(f"Route type not implemented: {route.get('type')}")
        except Exception as exc:
            return self._result(False, error=str(exc), started=start, route=route, source=source)

    def _execute_adapter(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> str | None:
        if str(route.get("adapter") or "").casefold() == "reaper":
            result = ReaperAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() in {"touchdesigner", "touch-designer"}:
            result = TouchDesignerAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() == "resolume":
            result = ResolumeAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() in {"obs-studio", "obs"}:
            result = ObsAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() in {"davinci-resolve", "resolve"}:
            result = ResolveAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() == "blender":
            result = BlenderAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if str(route.get("adapter") or "").casefold() == "comfyui":
            result = ComfyUIAdapter().execute(route, params, workflow)
            return params.get("output_path") or json.dumps(result, sort_keys=True)
        if not self.companion.health():
            raise RuntimeError("Companion is not running; MAP adapter execute requires companion HTTP")
        response = self.companion.adapter_execute({
            "route": route,
            "params": params,
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "app": workflow.get("app"),
            },
        })
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "MAP adapter execute failed"))
        return response.get("output") or params.get("output_path")

    def _execute_api(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> str | None:
        api_name = str(route.get("api", ""))
        if api_name.startswith("ableton"):
            return self._execute_ableton_api(route, params, workflow)

        endpoint = route["endpoint"]
        payload_path = self.root / str(route["payload_template"])
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload = self._substitute(payload, params)

        print(f"[Marouba] POSTing to {endpoint}")
        response = self._json_request(endpoint, method=str(route.get("method", "POST")), payload=payload)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI response did not include prompt_id: {response}")

        print(f"[Marouba] Prompt queued: {prompt_id}")
        print("[Marouba] Polling for completion...")
        history_endpoint = endpoint.rsplit("/prompt", 1)[0] + f"/history/{prompt_id}"
        timeout_seconds = int(workflow.get("verification", {}).get("timeout_seconds", 120))
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            history = self._json_request(history_endpoint, method="GET")
            if str(prompt_id) in history:
                return self._resolve_output(history[str(prompt_id)], params)
            time.sleep(2)

        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def _execute_ableton_api(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> str | None:
        if not self.companion.health():
            raise RuntimeError("Companion is not running; Ableton LOM routes require companion HTTP")
        payload = {
            "route": route,
            "params": params,
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "app": workflow.get("app"),
            },
        }
        response = self.companion.ableton_execute(payload)
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "Ableton LOM execute failed"))
        output = response.get("output")
        if isinstance(output, dict) and output.get("fallback_reason"):
            raise RuntimeError(str(output["fallback_reason"]))
        return params.get("output_path") or (json.dumps(output, sort_keys=True) if output is not None else None)

    def _execute_uia(self, route: dict[str, Any], params: dict[str, Any]) -> str | None:
        payload = {
            "window_title": route.get("app_window") or route.get("window_title"),
            "name": route.get("element") or route.get("name"),
            "role": route.get("role") or route.get("control_type"),
        }
        if self.companion.health():
            response = self.companion.click_uia(payload)
            if not response.get("ok", True):
                raise RuntimeError(response.get("error", "Companion UIA click failed"))
            return params.get("output_path")

        if importlib.util.find_spec("pywinauto") is None:
            raise RuntimeError("Companion is not running and pywinauto is unavailable")

        from pywinauto import Desktop

        window_title = payload["window_title"]
        element_name = payload["name"]
        control_type = payload["role"]
        if not window_title or not element_name:
            raise RuntimeError("UIA route requires app_window/window_title and element/name")

        desktop = Desktop(backend="uia")
        windows = desktop.windows(title_re=f".*{window_title}.*")
        if not windows:
            raise RuntimeError(f"Window not found: {window_title}")

        criteria = {"title": element_name}
        if control_type:
            criteria["control_type"] = control_type
        element = windows[0].child_window(**criteria)
        if not element.exists(timeout=2):
            raise RuntimeError(f"UI element not found: {element_name}")

        element.click_input()
        return params.get("output_path")

    def _execute_keyboard(self, route: dict[str, Any], params: dict[str, Any]) -> str | None:
        text = route.get("text")
        sequence = route.get("keys") or route.get("sequence") or route.get("hotkey")
        if text is None and not sequence:
            raise RuntimeError("Keyboard route requires text, keys, sequence, or hotkey")

        wait_before = float(route.get("wait_before", 0))
        if wait_before > 0:
            time.sleep(wait_before)

        if importlib.util.find_spec("pyautogui") is not None:
            import pyautogui

            if text is not None:
                rendered_text = str(text).format(**params)
                self._write_text_with_pyautogui(pyautogui, rendered_text, float(route.get("interval", 0.01)))
            elif isinstance(sequence, list):
                pyautogui.hotkey(*sequence)
            else:
                pyautogui.hotkey(*str(sequence).replace("+", " ").split())
            wait_seconds = float(route.get("wait_seconds", 0))
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            return params.get("output_path")

        if importlib.util.find_spec("keyboard") is not None:
            import keyboard

            if text is not None:
                keyboard.write(str(text).format(**params))
            else:
                keyboard.send("+".join(sequence) if isinstance(sequence, list) else str(sequence))
            wait_seconds = float(route.get("wait_seconds", 0))
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            return params.get("output_path")

        raise RuntimeError("pyautogui or keyboard is required for keyboard routes")

    def _write_text_with_pyautogui(self, pyautogui: Any, text: str, interval: float) -> None:
        buffer = []
        for char in text:
            if char in {"\n", "\r", "\t"}:
                if buffer:
                    pyautogui.write("".join(buffer), interval=interval)
                    buffer.clear()
                if char in {"\n", "\r"}:
                    pyautogui.press("enter")
                else:
                    pyautogui.press("tab")
            else:
                buffer.append(char)
        if buffer:
            pyautogui.write("".join(buffer), interval=interval)

    def _execute_cli(self, route: dict[str, Any], params: dict[str, Any]) -> str | None:
        command = route.get("command")
        if not command:
            raise RuntimeError("CLI route requires command")
        completed = subprocess.run(str(command), shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip() or f"Command exited with {completed.returncode}"
            raise RuntimeError(error)
        wait_seconds = float(route.get("wait_seconds", 0))
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        focus_window = route.get("focus_window") or route.get("window_title")
        if focus_window:
            self._focus_window(str(focus_window))
        return params.get("output_path") or completed.stdout.strip() or None

    def _focus_window(self, title_fragment: str) -> None:
        if importlib.util.find_spec("pywinauto") is not None:
            try:
                from pywinauto import Desktop

                window = Desktop(backend="uia").window(title_re=f".*{re.escape(title_fragment)}.*")
                if window.exists(timeout=3):
                    window.set_focus()
                    time.sleep(0.3)
                    return
            except Exception:
                pass

        if sys.platform != "win32":
            return

        try:
            import ctypes

            user32 = ctypes.windll.user32
            matches: list[int] = []

            def window_title(hwnd: int) -> str:
                length = user32.GetWindowTextLengthW(hwnd)
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_proc(hwnd: int, _: int) -> bool:
                if user32.IsWindowVisible(hwnd) and title_fragment.casefold() in window_title(hwnd).casefold():
                    matches.append(hwnd)
                return True

            user32.EnumWindows(enum_proc, None)
            if matches:
                hwnd = matches[0]
                user32.ShowWindow(hwnd, 9)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
        except Exception:
            return

    def _execute_visual(self, route: dict[str, Any], params: dict[str, Any]) -> str | None:
        coordinates = route.get("coordinates")
        if not coordinates:
            raise RuntimeError("Visual route requires recorded coordinates")

        if importlib.util.find_spec("pyautogui") is not None:
            import pyautogui

            pyautogui.click(int(coordinates["x"]), int(coordinates["y"]))
            return params.get("output_path")

        raise RuntimeError("pyautogui is required to replay visual coordinate routes")

    def _execute_gesture(self, route: dict[str, Any], params: dict[str, Any]) -> str | None:
        events = route.get("events")
        if not isinstance(events, list) or not events:
            raise RuntimeError("Gesture route requires recorded events")
        if not self.companion.health():
            raise RuntimeError("Companion is not running; gesture replay requires /mouse")

        response = self.companion.mouse(
            {
                "target_window": route.get("target_window") or route.get("window_title"),
                "events": events,
            }
        )
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "Companion mouse replay failed"))

        wait_seconds = float(route.get("wait_seconds", 0))
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return params.get("output_path")

    def _resolve_output(self, history_item: dict[str, Any], params: dict[str, Any]) -> str | None:
        if params.get("output_path"):
            return str(params["output_path"])

        for node in history_item.get("outputs", {}).values():
            for image in node.get("images", []):
                filename = image.get("filename")
                subfolder = image.get("subfolder", "")
                if filename:
                    return str(Path(subfolder) / filename) if subfolder else filename
        return None

    def _json_request(self, url: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method=method.upper(), headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc

    def _substitute(self, value: Any, params: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return value.format(**params)
        if isinstance(value, list):
            return [self._substitute(item, params) for item in value]
        if isinstance(value, dict):
            return {key: self._substitute(item, params) for key, item in value.items()}
        return value

    def _result(
        self,
        success: bool,
        started: float,
        route: dict[str, Any],
        source: str,
        output: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "route_type": route.get("type"),
            "source": source,
            "output": output,
            "error": error,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }

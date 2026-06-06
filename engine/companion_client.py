from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CompanionUnavailable(RuntimeError):
    pass


class CompanionClient:
    def __init__(self, base_url: str = "http://127.0.0.1:7842", timeout: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token_path = Path.home() / ".marouba" / "companion.token"

    def health(self) -> bool:
        try:
            return self.get("/health").get("status") == "ok"
        except CompanionUnavailable:
            return False

    def window(self) -> dict[str, Any]:
        return self.get("/window")

    def find_uia(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/uia/find", payload)

    def click_uia(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/uia/click", payload)

    def screenshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/screenshot", payload)

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        token = self._read_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{self.base_url}{path}", data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CompanionUnavailable(f"Companion HTTP {exc.code}: {detail}") from exc
        except (OSError, URLError, ValueError) as exc:
            raise CompanionUnavailable(f"Companion unavailable: {exc}") from exc

    def _read_token(self) -> str | None:
        try:
            return self.token_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

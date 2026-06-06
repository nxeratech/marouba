from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"


class Registry:
    def __init__(self, path: str | Path = REGISTRY_PATH) -> None:
        self.path = Path(path)

    def list(self) -> list[dict[str, Any]]:
        return self._load().get("workflows", [])

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold()
        return [
            listing
            for listing in self.list()
            if needle in listing.get("id", "").casefold()
            or needle in listing.get("name", "").casefold()
            or needle in listing.get("app", "").casefold()
            or any(needle in tag.casefold() for tag in listing.get("tags", []))
        ]

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        for listing in self.list():
            if listing.get("id") == workflow_id:
                return listing
        return None

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"workflows": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

from __future__ import annotations

from typing import Any

MAP_ROUTE_LADDER: dict[str, tuple[str, ...]] = {
    "r1": ("adapter", "api", "direct_api", "app_script", "script", "cli"),
    "r2": ("uia", "macos_uia", "keyboard", "shortcut"),
    "r3": ("gesture",),
    "r4": ("visual", "vision", "manual_repair"),
}

ROUTE_TYPE_TO_MAP_ROUTE = {
    route_type: map_route
    for map_route, route_types in MAP_ROUTE_LADDER.items()
    for route_type in route_types
}

R4_ROUTE_TYPES = set(MAP_ROUTE_LADDER["r4"])


def map_route_for_type(route_type: str | None) -> str:
    return ROUTE_TYPE_TO_MAP_ROUTE.get(str(route_type or ""), "unknown")


def with_map_route(route: dict[str, Any]) -> dict[str, Any]:
    tagged = dict(route)
    tagged.setdefault("map_route", map_route_for_type(tagged.get("type")))
    return tagged
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from engine.vault import Vault


InputFn = Callable[[str], str]


class Repairer:
    def __init__(self, vault: Vault, input_fn: InputFn = input) -> None:
        self.vault = vault
        self.input_fn = input_fn

    def repair(
        self,
        workflow: dict[str, Any],
        params: dict[str, Any],
        failures: list[dict[str, Any]],
        step_label: str = "workflow",
    ) -> dict[str, Any]:
        signature = self.failure_signature(failures)
        existing = self.find_existing_repair(workflow, signature)
        if existing:
            return {
                "success": True,
                "route_type": "manual_repair",
                "output": params.get("output_path") or existing.get("output"),
                "error": None,
                "duration_ms": 0,
                "repair": "already_recorded",
                "failure_signature": signature,
            }

        self.input_fn(f"Step {step_label} failed. Please perform the action manually, then press Enter.")
        route = self.record_manual_repair(workflow, params, failures, signature)
        saved_path = self.vault.save_workflow(workflow)
        result = {
            "success": True,
            "route_type": "manual_repair",
            "output": params.get("output_path"),
            "error": None,
            "duration_ms": 0,
            "repair": "recorded",
            "failure_signature": signature,
            "saved_workflow": str(saved_path),
        }
        self.vault.log_run(workflow, {"repair_event": True, "route": route, "failures": failures})
        return result

    def find_existing_repair(self, workflow: dict[str, Any], signature: str) -> dict[str, Any] | None:
        for route in workflow.get("routes", []):
            if route.get("type") == "manual_repair" and route.get("failure_signature") == signature:
                return route
        return None

    def record_manual_repair(
        self,
        workflow: dict[str, Any],
        params: dict[str, Any],
        failures: list[dict[str, Any]],
        signature: str,
    ) -> dict[str, Any]:
        route = {
            "type": "manual_repair",
            "failure_signature": signature,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "description": "User manually completed the failed step during repair.",
            "output": params.get("output_path"),
            "failures": [
                {"route_type": failure.get("route_type"), "error": failure.get("error")} for failure in failures
            ],
        }
        workflow.setdefault("routes", []).insert(0, route)
        fallback_order = workflow.setdefault("fallback_order", [])
        workflow["fallback_order"] = ["manual_repair"] + [item for item in fallback_order if item != "manual_repair"]
        return route

    def failure_signature(self, failures: list[dict[str, Any]]) -> str:
        parts = []
        for failure in failures:
            route_type = failure.get("route_type", "unknown")
            error = str(failure.get("error", "")).strip()
            parts.append(f"{route_type}:{error}")
        return "|".join(parts) or "unknown"

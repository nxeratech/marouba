from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.distillation import distill_after_session
from engine.executor import Executor
from engine.repairer import Repairer
from engine.router import Router
from engine.vault import Vault
from engine.map_ladder import map_route_for_type


def replay_workflow(
    workflow_id: str,
    params: dict,
    root: Path = ROOT,
    no_repair: bool = False,
    router: Router | None = None,
    executor: Executor | None = None,
    repair_mode: bool = False,
) -> int:
    vault = Vault(root)

    print(f"[Marouba] Loading workflow: {workflow_id}")
    workflow = vault.find_workflow(workflow_id)
    if not workflow:
        print(f"[Marouba] Workflow not found: {workflow_id}", file=sys.stderr)
        return 1

    router = router or Router()
    executor = executor or Executor(root)
    if workflow.get("mode") == "sequence":
        return replay_sequence(workflow, params, root, vault, executor)

    routes = router.route_order(workflow, allow_repair_routes=repair_mode)
    print(f"[Marouba] Route order: {', '.join(route['type'] for route in routes)}")
    failures = []
    repair_events = []
    consecutive_repairs = 0
    for index, route in enumerate(routes):
        route_type = route["type"]
        if route_type == "ask":
            break
        print(f"[Marouba] Trying route: {route_type} ({route.get('map_route', map_route_for_type(route_type))})")
        result = execute_with_watchdog(executor, route, params, workflow)
        result.setdefault("map_route", route.get("map_route", map_route_for_type(route_type)))
        if result["success"]:
            output = result.get("output")
            verification = workflow.get("verification", {})
            if verification.get("type") == "file_exists" and output and not Path(output).exists():
                result["success"] = False
                result["error"] = f"Verification failed: file does not exist: {output}"
                failures.append(result)
                print(f"[Marouba] Route failed: {route_type}: {result['error']}")
            else:
                if repair_events:
                    result["repair_events"] = repair_events
                print(f"[Marouba] Complete. Output: {output}")
                log_path = vault.log_run(workflow, result)
                print(f"[Marouba] Run logged to {log_path.relative_to(root)}")
                maybe_distill_after_session(vault, workflow)
                print("[Marouba] Replay complete.")
                return 0
        else:
            failures.append(result)
            print(f"[Marouba] Route failed: {route_type}: {result['error']}")

        next_route = next_executable_route(routes, index + 1)
        if next_route:
            repair_event = fallback_repair_event(route, next_route, result)
            repair_events.append(repair_event)
            consecutive_repairs += 1
            print(
                "[Marouba] Fallback repair event: "
                f"{repair_event['from_route']} -> {repair_event['to_route']}: {repair_event['reason']}"
            )
            if consecutive_repairs >= 3:
                pause_result = {
                    "success": False,
                    "paused": True,
                    "route_type": route_type,
                    "map_route": result.get("map_route"),
                    "error": "Replay paused after 3 consecutive repair fallbacks.",
                    "repair_events": repair_events,
                }
                log_path = vault.log_run(workflow, pause_result)
                print(f"[Marouba] Replay paused after 3 consecutive repairs. Run logged to {log_path.relative_to(root)}")
                maybe_distill_after_session(vault, workflow)
                return 1

    print("[Marouba] All routes failed.")
    for failure in failures:
        print(f"[Marouba] - {failure['route_type']}: {failure['error']}")
    if no_repair:
        return 1

    repairer = Repairer(vault)
    repair_result = repairer.repair(workflow, params, failures, step_label=workflow_id)
    if repair_result["success"]:
        log_path = vault.log_run(workflow, repair_result)
        print(f"[Marouba] Repair recorded. Run logged to {log_path.relative_to(root)}")
        maybe_distill_after_session(vault, workflow)
        print("[Marouba] Phase 1b repair complete.")
        return 0
    return 1

def route_timeout_seconds(route: dict, workflow: dict) -> float:
    timeout = route.get("timeout_seconds") or workflow.get("step_timeout_seconds") or workflow.get("route_timeout_seconds")
    return float(timeout or 30)


def execute_with_watchdog(executor: Executor, route: dict, params: dict, workflow: dict) -> dict:
    timeout = route_timeout_seconds(route, workflow)
    results: queue.Queue[dict] = queue.Queue(maxsize=1)

    def run() -> None:
        results.put(executor.execute(route, params, workflow))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        return results.get(timeout=timeout)
    except queue.Empty:
        return {
            "success": False,
            "route_type": route.get("type"),
            "map_route": route.get("map_route", map_route_for_type(route.get("type"))),
            "output": None,
            "error": f"Route timed out after {timeout:g}s",
            "duration_ms": round(timeout * 1000),
        }


def next_executable_route(routes: list[dict], start_index: int) -> dict | None:
    for candidate in routes[start_index:]:
        if candidate.get("type") != "ask":
            return candidate
    return None


def fallback_repair_event(route: dict, next_route: dict, result: dict) -> dict:
    return {
        "repair_event": True,
        "event_type": "fallback",
        "from_route": route.get("type"),
        "from_map_route": route.get("map_route", map_route_for_type(route.get("type"))),
        "to_route": next_route.get("type"),
        "to_map_route": next_route.get("map_route", map_route_for_type(next_route.get("type"))),
        "reason": str(result.get("error") or "route failed"),
    }

def replay_sequence(workflow: dict, params: dict, root: Path, vault: Vault, executor: Executor) -> int:
    routes = [route for route in workflow.get("routes", []) if route.get("type") != "ask"]
    print(f"[Marouba] Sequence steps: {', '.join(route['type'] for route in routes)}")
    if not routes:
        print("[Marouba] Sequence workflow has no executable routes.", file=sys.stderr)
        return 1

    results = []
    for index, route in enumerate(routes, start=1):
        route_type = route["type"]
        print(f"[Marouba] Step {index}/{len(routes)}: {route_type}")
        result = executor.execute(route, params, workflow)
        results.append(result)
        if not result["success"]:
            print(f"[Marouba] Step failed: {route_type}: {result['error']}", file=sys.stderr)
            vault.log_run(workflow, {"success": False, "route_type": "sequence", "steps": results})
            maybe_distill_after_session(vault, workflow)
            return 1

    final_result = {"success": True, "route_type": "sequence", "steps": results}
    log_path = vault.log_run(workflow, final_result)
    print(f"[Marouba] Run logged to {log_path.relative_to(root)}")
    maybe_distill_after_session(vault, workflow)
    print("[Marouba] Replay complete.")
    return 0


def maybe_distill_after_session(vault: Vault, workflow: dict) -> dict:
    try:
        result = distill_after_session(vault, workflow)
    except Exception as exc:
        print(f"[Marouba] AI distillation skipped: {exc}", file=sys.stderr)
        return {"status": "error", "error": str(exc)}
    if result.get("status") == "annotated":
        print(f"[Marouba] AI distillation annotations written to {result['path']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a Marouba workflow from the vault.")
    parser.add_argument("--workflow", required=True, help="Workflow id or name")
    parser.add_argument("--params", default="{}", help="JSON params for workflow placeholders")
    parser.add_argument("--no-repair", action="store_true", help="Do not prompt for repair when all routes fail")
    parser.add_argument("--repair-mode", action="store_true", help="Allow explicit r4 visual/vision/manual repair routes during replay")
    args = parser.parse_args()

    params = json.loads(args.params)
    return replay_workflow(args.workflow, params, no_repair=args.no_repair, repair_mode=args.repair_mode)


if __name__ == "__main__":
    raise SystemExit(main())

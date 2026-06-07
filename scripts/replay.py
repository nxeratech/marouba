from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.executor import Executor
from engine.repairer import Repairer
from engine.router import Router
from engine.vault import Vault


def replay_workflow(
    workflow_id: str,
    params: dict,
    root: Path = ROOT,
    no_repair: bool = False,
    router: Router | None = None,
    executor: Executor | None = None,
) -> int:
    vault = Vault(root)

    print(f"[Marouba] Loading workflow: {workflow_id}")
    workflow = vault.find_workflow(workflow_id)
    if not workflow:
        print(f"[Marouba] Workflow not found: {workflow_id}", file=sys.stderr)
        return 1

    router = router or Router()
    routes = router.route_order(workflow)
    print(f"[Marouba] Route order: {', '.join(route['type'] for route in routes)}")

    executor = executor or Executor(root)
    failures = []
    for route in routes:
        route_type = route["type"]
        print(f"[Marouba] Trying route: {route_type}")
        result = executor.execute(route, params, workflow)
        if result["success"]:
            output = result.get("output")
            verification = workflow.get("verification", {})
            if verification.get("type") == "file_exists" and output and not Path(output).exists():
                result["success"] = False
                result["error"] = f"Verification failed: file does not exist: {output}"
                failures.append(result)
                print(f"[Marouba] Route failed: {route_type}: {result['error']}")
                continue

            print(f"[Marouba] Complete. Output: {output}")
            log_path = vault.log_run(workflow, result)
            print(f"[Marouba] Run logged to {log_path.relative_to(root)}")
            print("[Marouba] Replay complete.")
            return 0

        failures.append(result)
        print(f"[Marouba] Route failed: {route_type}: {result['error']}")

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
        print("[Marouba] Phase 1b repair complete.")
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a Marouba workflow from the vault.")
    parser.add_argument("--workflow", required=True, help="Workflow id or name")
    parser.add_argument("--params", default="{}", help="JSON params for workflow placeholders")
    parser.add_argument("--no-repair", action="store_true", help="Do not prompt for repair when all routes fail")
    args = parser.parse_args()

    params = json.loads(args.params)
    return replay_workflow(args.workflow, params, no_repair=args.no_repair)


if __name__ == "__main__":
    raise SystemExit(main())

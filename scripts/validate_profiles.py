from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.vault import Vault


def validate_profiles(root: Path = ROOT) -> int:
    vault = Vault(root)
    profiles_dir = root / "profiles"
    failures: list[str] = []

    for profile_dir in sorted(path for path in profiles_dir.iterdir() if path.is_dir()):
        workflow_paths = sorted((profile_dir / "workflows").glob("*.md"))
        if not workflow_paths:
            message = f"[Marouba] FAIL {profile_dir.name}: no workflows found"
            print(message)
            failures.append(message)
            continue

        profile_failures = []
        for workflow_path in workflow_paths:
            try:
                workflow = vault.load_workflow(workflow_path)
                fallback_order = [route for route in workflow.get("fallback_order", []) if route != "ask"]
                if len(fallback_order) < 2:
                    profile_failures.append(f"{workflow_path.name}: fallback_order has fewer than 2 routes")
            except Exception as exc:
                profile_failures.append(f"{workflow_path.name}: {exc}")

        if profile_failures:
            print(f"[Marouba] FAIL {profile_dir.name}")
            for failure in profile_failures:
                print(f"[Marouba]   - {failure}")
            failures.extend(profile_failures)
        else:
            print(f"[Marouba] PASS {profile_dir.name}: {len(workflow_paths)} workflows")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(validate_profiles())

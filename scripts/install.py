from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.installer import install_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a signed Marouba workflow bundle.")
    parser.add_argument("--bundle", required=True, help="Path or URL to .mwf bundle")
    args = parser.parse_args()

    installed_path = install_bundle(args.bundle, ROOT)
    print(f"[Marouba] Installed workflow: {installed_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

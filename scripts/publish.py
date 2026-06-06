from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.publisher import publish_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Package and sign a workflow for the Marouba marketplace.")
    parser.add_argument("--workflow", required=True, help="Path to workflow .md")
    parser.add_argument("--author", required=True, help="Creator name")
    parser.add_argument("--price", required=True, help="Price in USD")
    parser.add_argument("--output-dir", default=None, help="Directory for .mwf output")
    args = parser.parse_args()

    bundle_path = publish_workflow(args.workflow, args.author, args.price, args.output_dir)
    print(f"[Marouba] Published bundle: {bundle_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

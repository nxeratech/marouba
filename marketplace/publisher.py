from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from engine.vault import Vault
from marketplace.signing import sign_workflow


def publish_workflow(
    workflow_path: str | Path,
    author: str,
    price_usd: str | float,
    output_dir: str | Path | None = None,
    version: str = "0.1.0",
    vault_spec_version: str = "0.1",
) -> Path:
    workflow_path = Path(workflow_path)
    root = workflow_path.resolve().parents[2] if "vault" in workflow_path.parts else Path.cwd()
    workflow = Vault(root).load_workflow(workflow_path)
    output_dir = Path(output_dir) if output_dir else workflow_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": workflow["id"],
        "name": workflow["name"],
        "author": author,
        "version": version,
        "price_usd": f"{float(price_usd):.2f}",
        "category": workflow.get("category", "workflow"),
        "tags": workflow.get("tags", []),
        "created": date.today().isoformat(),
        "vault_spec_version": vault_spec_version,
    }

    bundle_path = output_dir / f"{workflow['id']}.mwf"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        bundled_workflow = temp_dir / "workflow.md"
        shutil.copyfile(workflow_path, bundled_workflow)
        sig_path = sign_workflow(bundled_workflow)
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(bundled_workflow, "workflow.md")
            bundle.write(sig_path, "workflow.sig")
            bundle.write(manifest_path, "manifest.json")

    return bundle_path

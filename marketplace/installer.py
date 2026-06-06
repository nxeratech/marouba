from __future__ import annotations

import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from engine.vault import Vault
from engine.vault import sanitize_workflow_id
from marketplace.signing import verify_workflow


class InstallError(RuntimeError):
    pass


def install_bundle(bundle_path_or_url: str | Path, root: str | Path | None = None) -> Path:
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    bundle_path = fetch_bundle(bundle_path_or_url)
    vault = Vault(root)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        with zipfile.ZipFile(bundle_path) as bundle:
            names = set(bundle.namelist())
            required = {"workflow.md", "workflow.sig", "manifest.json"}
            if not required.issubset(names):
                raise InstallError("Bundle is missing workflow.md, workflow.sig, or manifest.json")
            for member in bundle.infolist():
                validate_zip_member(member.filename)
            for name in required:
                (temp_dir / name).write_bytes(bundle.read(name))

        workflow_path = temp_dir / "workflow.md"
        sig_path = temp_dir / "workflow.sig"
        manifest_path = temp_dir / "manifest.json"
        if not verify_workflow(workflow_path, sig_path):
            raise InstallError("Workflow signature verification failed")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        workflow = vault.load_workflow(workflow_path)
        destination = vault.workflows_dir / f"{sanitize_workflow_id(str(workflow['id']))}.md"
        shutil.copyfile(workflow_path, destination)
        log_install(root, manifest, destination)
        return destination


def fetch_bundle(bundle_path_or_url: str | Path) -> Path:
    value = str(bundle_path_or_url)
    if value.startswith(("http://", "https://")):
        temp_path, _ = urllib.request.urlretrieve(value)
        return Path(temp_path)
    return Path(bundle_path_or_url)


def validate_zip_member(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise InstallError(f"Unsafe bundle path: {name}")


def log_install(root: Path, manifest: dict, destination: Path) -> Path:
    runs_dir = root / "vault" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_path = runs_dir / "installs.json"
    installs = []
    if log_path.exists():
        installs = json.loads(log_path.read_text(encoding="utf-8"))
    installs.append(
        {
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "id": manifest.get("id"),
            "name": manifest.get("name"),
            "author": manifest.get("author"),
            "version": manifest.get("version"),
            "price_usd": manifest.get("price_usd"),
            "path": str(destination),
        }
    )
    log_path.write_text(json.dumps(installs, indent=2, sort_keys=True), encoding="utf-8")
    return log_path

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from engine.vault import Vault
from marketplace.installer import InstallError, install_bundle
from marketplace.publisher import publish_workflow
from marketplace.registry import Registry
from marketplace.signing import generate_keypair, sign_workflow, verify_workflow


def workflow() -> dict:
    return {
        "id": "marketplace-test-workflow",
        "name": "Marketplace Test Workflow",
        "app": "ComfyUI",
        "app_version": "latest",
        "author": "nxeratech",
        "category": "test",
        "tags": ["marketplace", "test"],
        "last_verified": "2026-06-06",
        "created": "2026-06-06",
        "routes": [
            {"type": "cli", "command": "echo {output_path}"},
            {"type": "shortcut", "keys": ["ctrl", "enter"]},
        ],
        "fallback_order": ["cli", "shortcut", "ask"],
        "verification": {"type": "file_exists", "path": "{output_path}"},
        "calls": [],
        "depends_on": [],
        "body": "# Marketplace Test Workflow\n",
    }


def save_workflow(root: Path) -> Path:
    return Vault(root).save_workflow(workflow())


def test_sign_workflow_verify_passes(monkeypatch, tmp_path: Path) -> None:
    workflow_path = save_workflow(tmp_path)
    private_key, _ = generate_keypair(tmp_path / "keys")
    monkeypatch.setenv("MAROUBA_SIGNING_KEY", str(private_key))

    sig_path = sign_workflow(workflow_path, private_key)

    assert verify_workflow(workflow_path, sig_path) is True


def test_tamper_with_workflow_verify_fails(monkeypatch, tmp_path: Path) -> None:
    workflow_path = save_workflow(tmp_path)
    private_key, _ = generate_keypair(tmp_path / "keys")
    monkeypatch.setenv("MAROUBA_SIGNING_KEY", str(private_key))
    sig_path = sign_workflow(workflow_path, private_key)

    workflow_path.write_text(workflow_path.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")

    assert verify_workflow(workflow_path, sig_path) is False


def test_publish_workflow_produces_valid_mwf(tmp_path: Path) -> None:
    workflow_path = save_workflow(tmp_path)

    bundle_path = publish_workflow(workflow_path, author="nxeratech", price_usd="0.00", output_dir=tmp_path)

    assert bundle_path.suffix == ".mwf"
    with zipfile.ZipFile(bundle_path) as bundle:
        assert set(bundle.namelist()) == {"workflow.md", "workflow.sig", "manifest.json"}
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    assert manifest["id"] == "marketplace-test-workflow"
    assert manifest["price_usd"] == "0.00"


def test_install_mwf_workflow_appears_in_vault(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    install_root = tmp_path / "install"
    workflow_path = save_workflow(source_root)
    bundle_path = publish_workflow(workflow_path, author="nxeratech", price_usd="0.00", output_dir=tmp_path)

    installed_path = install_bundle(bundle_path, install_root)

    assert installed_path.exists()
    assert installed_path == install_root / "vault" / "workflows" / "marketplace-test-workflow.md"
    assert Vault(install_root).find_workflow("marketplace-test-workflow") is not None
    assert (install_root / "vault" / "runs" / "installs.json").exists()


def test_install_tampered_mwf_rejected(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    install_root = tmp_path / "install"
    workflow_path = save_workflow(source_root)
    bundle_path = publish_workflow(workflow_path, author="nxeratech", price_usd="0.00", output_dir=tmp_path)
    tampered_path = tmp_path / "tampered.mwf"

    with zipfile.ZipFile(bundle_path) as original, zipfile.ZipFile(tampered_path, "w") as tampered:
        for name in original.namelist():
            data = original.read(name)
            if name == "workflow.md":
                data += b"\nTampered.\n"
            tampered.writestr(name, data)

    with pytest.raises(InstallError, match="signature verification failed"):
        install_bundle(tampered_path, install_root)


def test_forged_signature_rejected(monkeypatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    install_root = tmp_path / "install"
    workflow_path = save_workflow(source_root)
    trusted_private, _ = generate_keypair(tmp_path / "trusted")
    attacker_private, _ = generate_keypair(tmp_path / "attacker")
    monkeypatch.setenv("MAROUBA_SIGNING_KEY", str(trusted_private))

    sig_path = sign_workflow(workflow_path, attacker_private)
    bundle_path = tmp_path / "forged.mwf"
    manifest = {
        "id": "marketplace-test-workflow",
        "name": "Marketplace Test Workflow",
        "author": "attacker",
        "version": "0.1.0",
        "price_usd": "0.00",
        "category": "test",
        "tags": [],
        "created": "2026-06-06",
        "vault_spec_version": "0.1",
    }
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.write(workflow_path, "workflow.md")
        bundle.write(sig_path, "workflow.sig")
        bundle.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(InstallError):
        install_bundle(bundle_path, install_root)


def test_registry_lists_searches_and_gets_seed_listings() -> None:
    registry = Registry()

    listings = registry.list()

    assert len(listings) >= 3
    assert registry.get("comfyui-generate-image-001")["price_usd"] == "0.00"
    assert registry.search("photoshop")[0]["id"] == "photoshop-export-for-web"

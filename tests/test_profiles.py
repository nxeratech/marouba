from __future__ import annotations

from pathlib import Path

import frontmatter

from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]
PROFILE_APPS = ["comfyui", "photoshop", "ableton", "blender", "browser"]


def test_all_five_profiles_load_without_error() -> None:
    for app in PROFILE_APPS:
        profile_path = ROOT / "profiles" / app / f"{app}-profile.md"
        profile = frontmatter.load(profile_path)

        assert profile.metadata["app"]
        assert "uia_window_title" in profile.metadata
        assert "shortcuts" in profile.metadata
        assert "cli_commands" in profile.metadata
        assert "output_folder" in profile.metadata


def test_all_profile_workflows_are_valid_vault_format() -> None:
    vault = Vault(ROOT)

    for app in PROFILE_APPS:
        workflow_paths = sorted((ROOT / "profiles" / app / "workflows").glob("*.md"))
        assert len(workflow_paths) >= 2

        for workflow_path in workflow_paths:
            workflow = vault.load_workflow(workflow_path)

            assert workflow["id"]
            assert workflow["name"]
            assert workflow["app"]
            assert workflow["routes"]
            assert workflow["fallback_order"]
            assert workflow["verification"]
            assert "calls" in workflow
            assert "depends_on" in workflow


def test_profile_workflows_have_at_least_two_fallback_routes() -> None:
    vault = Vault(ROOT)

    for workflow_path in (ROOT / "profiles").glob("*/workflows/*.md"):
        workflow = vault.load_workflow(workflow_path)
        real_routes = [route for route in workflow["fallback_order"] if route != "ask"]

        assert len(real_routes) >= 2, workflow_path

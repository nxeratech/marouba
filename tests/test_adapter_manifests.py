from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = sorted(ROOT.glob("profiles/*/manifest.yaml"))


def test_profile_manifests_are_valid_map_yaml() -> None:
    assert MANIFESTS, "expected MAP manifests under profiles/<app>/manifest.yaml"
    for path in MANIFESTS:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path
        assert data.get("adapter"), path
        assert data.get("mechanism"), path
        assert data.get("tier") in {"T0", "T1", "T2", "T3"}, path
        assert isinstance(data.get("versions"), list) and data["versions"], path
        assert isinstance(data.get("capabilities"), dict), path
        assert isinstance(data.get("known_blockers"), list), path
        assert data.get("setup"), path


def test_ableton_manifest_expresses_master_plan_capabilities() -> None:
    data = yaml.safe_load((ROOT / "profiles" / "ableton" / "manifest.yaml").read_text(encoding="utf-8"))

    assert data["adapter"] == "ableton-live"
    assert data["mechanism"] == "remote-script + osc"
    assert data["tier"] == "T1"
    assert data["versions"] == ["11.x", "12.x"]
    assert data["capabilities"]["parameter_values"] == "full"
    assert data["capabilities"]["midi_notes"] == "full"
    assert data["capabilities"]["transport_state"] == "full"
    assert data["capabilities"]["file_drag_payload"] == "partial"
    assert data["capabilities"]["custom_renderer_widgets"] == "via_api"

def test_ableton_manifest_matches_rust_parser_field_for_field() -> None:
    manifest_path = ROOT / "profiles" / "ableton" / "manifest.yaml"
    python_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(ROOT / "companion" / "src-tauri" / "crates" / "marouba-adapter" / "Cargo.toml"),
            "--example",
            "dump_manifest",
            "--",
            str(manifest_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rust_manifest = yaml.safe_load(result.stdout)

    assert rust_manifest == python_manifest

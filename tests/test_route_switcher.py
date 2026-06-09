from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"


def load_profile(name):
    text = (PROFILES / name).read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    return yaml.safe_load(frontmatter)


def select_route(event_type, profile=None, element_name=None, action=None):
    if profile is None:
        return "coordinates"
    routes = profile.get("supported_routes", {}).get(event_type, [])
    if "api" in routes:
        return "api"
    if element_name and "uia" in routes:
        return "uia"
    if action and action in profile.get("known_shortcuts", {}):
        return f"shortcut:{profile['known_shortcuts'][action]}"
    return "coordinates"


def test_route_switcher_uia_preferred_when_element_named():
    profile = load_profile("ms-paint.md")
    route = select_route("toolbar_click", profile, element_name="Brushes")
    assert route == "uia"


def test_route_switcher_coordinates_fallback_when_no_profile():
    route = select_route("toolbar_click", None, element_name="Brushes")
    assert route == "coordinates"


def test_route_switcher_keyboard_shortcut_used_when_declared():
    profile = load_profile("ableton-live.md")
    route = select_route("keyboard_shortcut", profile, action="save_live_set")
    assert route == "shortcut:Ctrl+S"


def test_route_switcher_api_route_wins_before_uia():
    profile = load_profile("ableton-live.md")
    profile["supported_routes"]["toolbar_click"] = ["api", "uia", "gesture"]
    route = select_route("toolbar_click", profile, element_name="Play")
    assert route == "api"


def test_profile_loader_matches_title_fragment_case_insensitive():
    title = "Untitled* - Ableton Live 12 Suite"
    matches = [
        load_profile(path.name)
        for path in PROFILES.glob("*.md")
        if path.is_file()
        and load_profile(path.name)["title_fragment"].lower() in title.lower()
    ]
    assert [profile["app_name"] for profile in matches] == ["Ableton Live"]


def test_profiles_declare_coordinate_safe_fallback_routes():
    for path in ("ms-paint.md", "notepad-plus-plus.md", "ableton-live.md"):
        profile = load_profile(path)
        routes = profile["supported_routes"]
        assert "canvas_stroke" in routes
        assert "mouse_move_idle" in routes
        assert routes["mouse_move_idle"] == ["gesture"]

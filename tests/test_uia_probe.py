from scripts.uia_probe import ProbeElement, ProbeReport, WindowInventoryItem, render_markdown, slugify


def test_uia_probe_report_renders_coverage_percentages() -> None:
    report = ProbeReport(
        app="Paint",
        title_query="Paint",
        generated_at="2026-06-10T12:00:00",
        target_title="Untitled - Paint",
        target_rect="(L0, T0, R100, B100)",
        windows=[
            WindowInventoryItem(
                title="Untitled - Paint",
                control_type="Window",
                class_name="MSPaintApp",
                rectangle="(L0, T0, R100, B100)",
            )
        ],
        elements=[
            ProbeElement(
                name="Untitled - Paint",
                control_type="Window",
                class_name="MSPaintApp",
                automation_id="",
                rectangle="(L0, T0, R100, B100)",
                patterns=["Window"],
            ),
            ProbeElement(
                name="Pencil",
                control_type="Button",
                class_name="",
                automation_id="Pencil",
                rectangle="(L10, T10, R20, B20)",
                patterns=["Invoke"],
            ),
            ProbeElement(
                name="",
                control_type="Custom",
                class_name="",
                automation_id="",
                rectangle="(L20, T20, R30, B30)",
                patterns=[],
                value="0.5",
            ),
        ],
        errors=["sample warning"],
    )

    markdown = render_markdown(report)

    assert "| Elements with names | 2 | 66.7% |" in markdown
    assert "| Child elements discovered | 2 | 66.7% |" in markdown
    assert "| Actionable named controls | 1 | 33.3% |" in markdown
    assert "| Elements with supported patterns | 2 | 66.7% |" in markdown
    assert "| Elements with readable values | 1 | 33.3% |" in markdown
    assert "Assessment: **LOW - few actionable controls are exposed**" in markdown
    assert "Pencil" in markdown
    assert "sample warning" in markdown


def test_uia_probe_slugifies_report_names() -> None:
    assert slugify("Ableton Live 12 Suite") == "ableton-live-12-suite"

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Any, Iterable


PATTERN_IDS: dict[str, int] = {
    "Invoke": 10000,
    "Selection": 10001,
    "Value": 10002,
    "RangeValue": 10003,
    "Scroll": 10004,
    "ExpandCollapse": 10005,
    "Grid": 10006,
    "GridItem": 10007,
    "MultipleView": 10008,
    "Window": 10009,
    "SelectionItem": 10010,
    "Dock": 10011,
    "Table": 10012,
    "TableItem": 10013,
    "Text": 10014,
    "Toggle": 10015,
    "Transform": 10016,
    "ScrollItem": 10017,
    "LegacyIAccessible": 10018,
    "ItemContainer": 10019,
    "VirtualizedItem": 10020,
    "SynchronizedInput": 10021,
    "ObjectModel": 10022,
    "Annotation": 10023,
    "Text2": 10024,
    "Styles": 10025,
    "Spreadsheet": 10026,
    "SpreadsheetItem": 10027,
    "Transform2": 10028,
    "TextChild": 10029,
    "Drag": 10030,
    "DropTarget": 10031,
    "TextEdit": 10032,
    "CustomNavigation": 10033,
    "Selection2": 10034,
}

VALUE_PATTERN_ID = PATTERN_IDS["Value"]
RANGE_VALUE_PATTERN_ID = PATTERN_IDS["RangeValue"]
LEGACY_PATTERN_ID = PATTERN_IDS["LegacyIAccessible"]


@dataclasses.dataclass
class ProbeElement:
    name: str
    control_type: str
    class_name: str
    automation_id: str
    rectangle: str
    patterns: list[str]
    value: str | None = None

    @property
    def has_name(self) -> bool:
        return bool(self.name.strip())

    @property
    def has_patterns(self) -> bool:
        return bool(self.patterns)

    @property
    def has_value(self) -> bool:
        return self.value is not None and self.value != ""


@dataclasses.dataclass
class WindowInventoryItem:
    title: str
    control_type: str
    class_name: str
    rectangle: str


@dataclasses.dataclass
class ProbeReport:
    app: str
    title_query: str
    generated_at: str
    target_title: str
    target_rect: str
    elements: list[ProbeElement]
    windows: list[WindowInventoryItem]
    errors: list[str]

    @property
    def total_elements(self) -> int:
        return len(self.elements)

    @property
    def named_elements(self) -> int:
        return sum(1 for element in self.elements if element.has_name)

    @property
    def patterned_elements(self) -> int:
        return sum(1 for element in self.elements if element.has_patterns)

    @property
    def valued_elements(self) -> int:
        return sum(1 for element in self.elements if element.has_value)

    @property
    def child_elements(self) -> int:
        return max(0, len(self.elements) - 1)

    @property
    def actionable_named_elements(self) -> int:
        ignored = {"", "Window", "Pane", "Custom", "Group"}
        return sum(
            1
            for element in self.elements[1:]
            if element.has_name and element.control_type not in ignored
        )

    def percent(self, count: int) -> float:
        if self.total_elements == 0:
            return 0.0
        return round((count / self.total_elements) * 100.0, 1)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "uia-probe"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def detect_patterns(element: Any) -> list[str]:
    native = getattr(getattr(element, "element_info", None), "element", None)
    if native is None:
        return []

    patterns: list[str] = []
    for name, pattern_id in PATTERN_IDS.items():
        try:
            pattern = native.GetCurrentPattern(pattern_id)
        except Exception:
            continue
        if pattern:
            patterns.append(name)
    return patterns


def read_value(element: Any, patterns: Iterable[str]) -> str | None:
    native = getattr(getattr(element, "element_info", None), "element", None)
    if native is None:
        return None

    pattern_set = set(patterns)
    if "Value" in pattern_set:
        try:
            value_pattern = native.GetCurrentPattern(VALUE_PATTERN_ID)
            value = getattr(value_pattern, "CurrentValue", None)
            if value is not None:
                return safe_text(value)
        except Exception:
            pass

    if "RangeValue" in pattern_set:
        try:
            range_pattern = native.GetCurrentPattern(RANGE_VALUE_PATTERN_ID)
            value = getattr(range_pattern, "CurrentValue", None)
            if value is not None:
                return safe_text(value)
        except Exception:
            pass

    if "LegacyIAccessible" in pattern_set:
        try:
            legacy_pattern = native.GetCurrentPattern(LEGACY_PATTERN_ID)
            value = getattr(legacy_pattern, "CurrentValue", None)
            if value is not None:
                return safe_text(value)
        except Exception:
            pass

    return None


def element_to_probe(element: Any) -> ProbeElement:
    info = element.element_info
    patterns = detect_patterns(element)
    return ProbeElement(
        name=safe_text(getattr(info, "name", "")),
        control_type=safe_text(getattr(info, "control_type", "")),
        class_name=safe_text(getattr(info, "class_name", "")),
        automation_id=safe_text(getattr(info, "automation_id", "")),
        rectangle=safe_text(getattr(info, "rectangle", "")),
        patterns=patterns,
        value=read_value(element, patterns),
    )


def find_target_window(desktop: Any, title_query: str) -> Any:
    query = title_query.lower()
    candidates = []
    for window in desktop.windows():
        title = safe_text(getattr(window.element_info, "name", ""))
        if query in title.lower():
            candidates.append(window)
    if not candidates:
        available = [safe_text(getattr(w.element_info, "name", "")) for w in desktop.windows()]
        visible = ", ".join(title for title in available if title)[:600]
        raise RuntimeError(f"No running top-level window matched '{title_query}'. Visible windows: {visible}")
    return candidates[0]


def probe_app(app: str, title: str, max_elements: int = 5000) -> ProbeReport:
    if sys.platform != "win32":
        raise RuntimeError("UIA probe requires Windows")

    try:
        from pywinauto import Desktop
    except ImportError as error:
        raise RuntimeError("pywinauto is required for UIA probing on Windows") from error

    desktop = Desktop(backend="uia")
    target = find_target_window(desktop, title)
    errors: list[str] = []

    try:
        descendants = target.descendants()
    except Exception as error:
        descendants = []
        errors.append(f"Failed to walk descendants: {error}")

    elements: list[ProbeElement] = [element_to_probe(target)]
    for child in descendants[: max(0, max_elements - 1)]:
        try:
            elements.append(element_to_probe(child))
        except Exception as error:
            errors.append(f"Failed to read element: {error}")

    windows: list[WindowInventoryItem] = []
    for window in desktop.windows():
        try:
            info = window.element_info
            title_text = safe_text(getattr(info, "name", ""))
            if title.lower() in title_text.lower() or app.lower() in title_text.lower():
                windows.append(
                    WindowInventoryItem(
                        title=title_text,
                        control_type=safe_text(getattr(info, "control_type", "")),
                        class_name=safe_text(getattr(info, "class_name", "")),
                        rectangle=safe_text(getattr(info, "rectangle", "")),
                    )
                )
        except Exception as error:
            errors.append(f"Failed to inventory window: {error}")

    target_info = target.element_info
    return ProbeReport(
        app=app,
        title_query=title,
        generated_at=dt.datetime.now().isoformat(timespec="seconds"),
        target_title=safe_text(getattr(target_info, "name", "")),
        target_rect=safe_text(getattr(target_info, "rectangle", "")),
        elements=elements,
        windows=windows,
        errors=errors,
    )


def render_markdown(report: ProbeReport) -> str:
    assessment = coverage_assessment(report)
    lines = [
        f"# UIA Probe Audit - {report.app}",
        "",
        f"- Generated: {report.generated_at}",
        f"- Title query: `{report.title_query}`",
        f"- Target window: `{report.target_title}`",
        f"- Target rect: `{report.target_rect}`",
        f"- Assessment: **{assessment}**",
        "",
        "## Coverage",
        "",
        "| Metric | Count | Percent |",
        "|---|---:|---:|",
        f"| Elements walked | {report.total_elements} | 100.0% |",
        f"| Child elements discovered | {report.child_elements} | {report.percent(report.child_elements)}% |",
        f"| Actionable named controls | {report.actionable_named_elements} | {report.percent(report.actionable_named_elements)}% |",
        f"| Elements with names | {report.named_elements} | {report.percent(report.named_elements)}% |",
        f"| Elements with supported patterns | {report.patterned_elements} | {report.percent(report.patterned_elements)}% |",
        f"| Elements with readable values | {report.valued_elements} | {report.percent(report.valued_elements)}% |",
        "",
        "## Window / Dialog Inventory",
        "",
        "| Title | Control | Class | Rect |",
        "|---|---|---|---|",
    ]
    if report.windows:
        for item in report.windows:
            lines.append(
                f"| {markdown_cell(item.title)} | {markdown_cell(item.control_type)} | {markdown_cell(item.class_name)} | {markdown_cell(item.rectangle)} |"
            )
    else:
        lines.append("| _None_ |  |  |  |")

    lines.extend(
        [
            "",
            "## Elements",
            "",
            "| # | Name | Control | Class | AutomationId | Patterns | Value | Rect |",
            "|---:|---|---|---|---|---|---|---|",
        ]
    )
    for index, element in enumerate(report.elements, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    markdown_cell(element.name),
                    markdown_cell(element.control_type),
                    markdown_cell(element.class_name),
                    markdown_cell(element.automation_id),
                    markdown_cell(", ".join(element.patterns)),
                    markdown_cell(element.value or ""),
                    markdown_cell(element.rectangle),
                ]
            )
            + " |"
        )

    if report.errors:
        lines.extend(["", "## Probe Warnings", ""])
        for error in report.errors:
            lines.append(f"- {error}")

    lines.append("")
    return "\n".join(lines)


def coverage_assessment(report: ProbeReport) -> str:
    if report.child_elements == 0:
        return "LOW - only the top-level window is exposed through UIA"
    if report.actionable_named_elements >= 20 and report.percent(report.named_elements) >= 60:
        return "HIGH - many named actionable controls are exposed"
    if report.actionable_named_elements >= 5:
        return "PARTIAL - some actionable controls are exposed"
    return "LOW - few actionable controls are exposed"


def markdown_cell(value: str) -> str:
    return safe_text(value).replace("|", "\\|")


def write_report(report: ProbeReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date = dt.date.today().isoformat()
    path = output_dir / f"{slugify(report.app)}-uia-audit-{date}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only UIA coverage probe for Marouba adapters.")
    parser.add_argument("--app", required=True, help="Human app name for the report, e.g. Paint")
    parser.add_argument("--title", required=True, help="Substring of a running top-level window title")
    parser.add_argument("--out", default="audits", help="Directory for Markdown reports")
    parser.add_argument("--max-elements", type=int, default=5000, help="Maximum UIA elements to walk")
    args = parser.parse_args(argv)

    try:
        report = probe_app(args.app, args.title, args.max_elements)
        path = write_report(report, Path(args.out))
    except Exception as error:
        print(f"[Marouba] UIA probe failed: {error}", file=sys.stderr)
        return 2

    print(f"[Marouba] UIA audit written: {path}")
    print(
        "[Marouba] Coverage: "
        f"names={report.percent(report.named_elements)}% "
        f"patterns={report.percent(report.patterned_elements)}% "
        f"values={report.percent(report.valued_elements)}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

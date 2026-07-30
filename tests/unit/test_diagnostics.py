"""R1.5, R3.5, R7.1, D11 — Diagnostic, Severity, DiagnosticCollector."""

import json

from clens.core.diagnostics import Diagnostic, DiagnosticCollector, Position, Severity
from clens.core.source import SourceFile


def make_diagnostic(
    message: str,
    file: str = "a.c",
    severity: Severity = Severity.ERROR,
    start: Position | None = None,
    end: Position | None = None,
) -> Diagnostic:
    start = start or Position(1, 6, 5)
    return Diagnostic(
        severity=severity,
        message=message,
        file=file,
        start=start,
        end=end or Position(start.line, start.column + 1, start.offset + 1),
    )


def test_length_derived_from_offsets():
    d = make_diagnostic("x", start=Position(1, 6, 5), end=Position(1, 9, 8))
    assert d.length == 3


def test_collector_has_errors_and_filters_by_severity():
    collector = DiagnosticCollector()
    collector.add(make_diagnostic("bad char", severity=Severity.ERROR))
    collector.add(make_diagnostic("style nit", severity=Severity.WARNING))

    assert collector.has_errors is True
    assert len(collector.errors) == 1
    assert len(collector.warnings) == 1
    assert len(collector.diagnostics) == 2


def test_collector_empty_has_no_errors():
    assert DiagnosticCollector().has_errors is False


def test_sorted_by_file_then_start_offset():
    collector = DiagnosticCollector()
    d_late = make_diagnostic("second", file="a.c", start=Position(2, 1, 10))
    d_early = make_diagnostic("first", file="a.c", start=Position(1, 1, 0))
    d_other_file = make_diagnostic("other", file="b.c", start=Position(1, 1, 0))
    collector.add(d_late)
    collector.add(d_other_file)
    collector.add(d_early)

    ordered = collector.sorted()
    assert [d.message for d in ordered] == ["first", "second", "other"]


def test_to_json_round_trips():
    collector = DiagnosticCollector()
    collector.add(make_diagnostic("unrecognized character '@'"))
    payload = json.loads(collector.to_json())

    assert payload == [
        {
            "severity": "error",
            "message": "unrecognized character '@'",
            "file": "a.c",
            "start": {"line": 1, "column": 6},
            "end": {"line": 1, "column": 7},
            "code": None,
            "source": "clens",
        }
    ]


def test_format_pretty_renders_caret_under_offending_column():
    """Golden shape from skills/diagnostics/SKILL.md."""
    source = SourceFile("int x@ = 5;\n", "main.c")
    collector = DiagnosticCollector()
    collector.add(
        Diagnostic(
            severity=Severity.ERROR,
            message="unrecognized character '@'",
            file="main.c",
            start=Position(1, 6, 5),
            end=Position(1, 7, 6),
        )
    )

    output = collector.format_pretty(source)

    assert output == (
        "main.c:1:6: error: unrecognized character '@'\n  1 | int x@ = 5;\n    |      ^"
    )


def test_format_pretty_ignores_diagnostics_for_other_files():
    source = SourceFile("int x;\n", "main.c")
    collector = DiagnosticCollector()
    collector.add(make_diagnostic("elsewhere", file="other.c"))
    assert collector.format_pretty(source) == ""

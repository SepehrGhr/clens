"""R1.5, R3.5, R7.1, D11 — Diagnostic, Severity, DiagnosticCollector."""

import json

from clens.core.diagnostics import (
    Diagnostic,
    DiagnosticCollector,
    Position,
    SemanticCode,
    Severity,
    diagnostic_from_span,
)
from clens.core.source import SourceFile
from clens.core.token import Span


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


def test_diagnostic_from_span_derives_end_position():
    """Span carries a start line/column but not an end one; the helper must
    derive the end position from the SourceFile rather than leaving it at the
    start."""
    source = SourceFile("int coutn;\n", "main.c")
    span = Span(start_offset=4, end_offset=9, line=1, column=5)

    d = diagnostic_from_span(
        Severity.ERROR,
        "undefined symbol 'coutn'",
        "main.c",
        span,
        source,
        code=SemanticCode.UNDEFINED_SYMBOL,
    )

    assert d.start == Position(1, 5, 4)
    assert d.end == Position(1, 10, 9)
    assert d.code == "S001"
    assert d.severity is Severity.ERROR


def test_semantic_code_registry_has_no_duplicate_values():
    codes = [
        v for k, v in vars(SemanticCode).items() if not k.startswith("_") and isinstance(v, str)
    ]
    assert len(codes) == len(set(codes))
    assert codes  # the required-rows block must not be empty

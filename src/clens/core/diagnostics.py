"""The one LSP-shaped Diagnostic type shared by the lexer, parser, and (in
Phase 2) the semantic analyzer. Positions carry both 1-based line/column and
the raw 0-based offset, since the highlighter and the pretty-printer both need
offsets while human-facing output needs line/column. See D11.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from clens.core.source import SourceFile


class Severity(Enum):
    """Diagnostic severity, matching the LSP severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass(slots=True, frozen=True)
class Position:
    """A single point in a source file: 1-based line/column plus 0-based offset."""

    line: int
    column: int
    offset: int


@dataclass(slots=True)
class Diagnostic:
    """A single diagnostic message with an exact source range."""

    severity: Severity
    message: str
    file: str
    start: Position
    end: Position
    code: str | None = None
    source: str = "clens"

    @property
    def length(self) -> int:
        """Span length in characters, derived from the start/end offsets."""
        return self.end.offset - self.start.offset

    def to_dict(self) -> dict[str, Any]:
        """This diagnostic as a JSON-serializable dict."""
        return {
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "start": {"line": self.start.line, "column": self.start.column},
            "end": {"line": self.end.line, "column": self.end.column},
            "code": self.code,
            "source": self.source,
        }


@dataclass(slots=True)
class DiagnosticCollector:
    """Accumulates diagnostics for one run. Passed explicitly, never global."""

    _diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(self, diagnostic: Diagnostic) -> None:
        """Record a diagnostic."""
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """All recorded diagnostics, in insertion order."""
        return list(self._diagnostics)

    @property
    def errors(self) -> list[Diagnostic]:
        """Diagnostics at ERROR severity."""
        return [d for d in self._diagnostics if d.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        """Diagnostics at WARNING severity."""
        return [d for d in self._diagnostics if d.severity is Severity.WARNING]

    @property
    def has_errors(self) -> bool:
        """Whether any recorded diagnostic is at ERROR severity (R7.1 exit codes)."""
        return any(d.severity is Severity.ERROR for d in self._diagnostics)

    def sorted(self) -> list[Diagnostic]:
        """Diagnostics ordered by file, then by start offset."""
        return sorted(self._diagnostics, key=lambda d: (d.file, d.start.offset))

    def to_json(self) -> str:
        """All diagnostics, sorted, as a JSON array."""
        return json.dumps([d.to_dict() for d in self.sorted()], indent=2)

    def format_pretty(self, source: SourceFile) -> str:
        """Render diagnostics for ``source`` as caret-annotated text blocks."""
        blocks = [_format_one(d, source) for d in self.sorted() if d.file == source.filename]
        return "\n".join(blocks)


def _format_one(diagnostic: Diagnostic, source: SourceFile) -> str:
    line_text = source.line_text(diagnostic.start.line)
    gutter = str(diagnostic.start.line)
    same_line = diagnostic.start.line == diagnostic.end.line
    caret_count = max(1, diagnostic.length) if same_line else 1
    prefix = "  " + " " * len(gutter) + " | "
    caret_row = prefix + " " * (diagnostic.start.column - 1) + "^" * caret_count
    header = (
        f"{diagnostic.file}:{diagnostic.start.line}:{diagnostic.start.column}: "
        f"{diagnostic.severity.value}: {diagnostic.message}"
    )
    body = f"  {gutter} | {line_text}"
    return "\n".join([header, body, caret_row])

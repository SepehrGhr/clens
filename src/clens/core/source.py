"""SourceFile: text plus a precomputed line-start index for offset<->line/column
conversion. Every later position (tokens, AST spans, diagnostics) is derived from
this one implementation rather than tracked incrementally, so there is exactly one
place where off-by-one and CRLF bugs can hide. See R1.1.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field


def _compute_line_starts(text: str) -> list[int]:
    """Return the 0-based offset of the first character of each line.

    A line starts at offset 0 and after every ``\\n``. ``\\r\\n`` is handled the
    same way: the ``\\r`` stays as the last character of the preceding line, and
    the following ``\\n`` starts the next one.
    """
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _strip_line_terminator(raw: str) -> str:
    """Strip a single trailing line terminator (``\\r\\n``, ``\\n``, or ``\\r``)."""
    if raw.endswith("\r\n"):
        return raw[:-2]
    if raw.endswith("\n") or raw.endswith("\r"):
        return raw[:-1]
    return raw


@dataclass(slots=True)
class SourceFile:
    """A source file's text, addressable by 0-based offset or 1-based line/column.

    Satisfies R1.1's position requirements. Handles ``\\n``, ``\\r\\n``, files with
    no trailing newline, and empty files.
    """

    text: str
    filename: str = "<unknown>"
    _line_starts: list[int] = field(init=False, repr=False, default_factory=list)

    def __post_init__(self) -> None:
        self._line_starts = _compute_line_starts(self.text)

    @property
    def line_count(self) -> int:
        """Number of lines in the file (at least 1, even for an empty file)."""
        return len(self._line_starts)

    def offset_to_line_col(self, offset: int) -> tuple[int, int]:
        """Convert a 0-based offset to a 1-based ``(line, column)`` pair.

        ``offset`` may equal ``len(text)`` to address the end-of-file position.
        """
        if not (0 <= offset <= len(self.text)):
            raise ValueError(
                f"offset {offset} out of range for a source of length {len(self.text)}"
            )
        line_index = bisect_right(self._line_starts, offset) - 1
        line = line_index + 1
        column = offset - self._line_starts[line_index] + 1
        return line, column

    def line_col_to_offset(self, line: int, column: int) -> int:
        """Convert a 1-based ``(line, column)`` pair to a 0-based offset."""
        if not (1 <= line <= self.line_count):
            raise ValueError(f"line {line} out of range (file has {self.line_count} lines)")
        offset = self._line_starts[line - 1] + (column - 1)
        if not (0 <= offset <= len(self.text)):
            raise ValueError(f"column {column} out of range on line {line}")
        return offset

    def line_text(self, line: int) -> str:
        """Return line ``line``'s text, excluding its trailing line terminator."""
        if not (1 <= line <= self.line_count):
            raise ValueError(f"line {line} out of range (file has {self.line_count} lines)")
        start = self._line_starts[line - 1]
        end = self._line_starts[line] if line < self.line_count else len(self.text)
        return _strip_line_terminator(self.text[start:end])

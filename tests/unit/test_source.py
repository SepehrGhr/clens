"""R1.1 — SourceFile position handling, including CRLF and empty-file edges."""

import pytest

from clens.core.source import SourceFile


def test_empty_file_has_one_line():
    src = SourceFile("", "empty.c")
    assert src.line_count == 1
    assert src.line_text(1) == ""
    assert src.offset_to_line_col(0) == (1, 1)


def test_single_line_no_trailing_newline():
    src = SourceFile("int x;", "a.c")
    assert src.line_count == 1
    assert src.line_text(1) == "int x;"
    assert src.offset_to_line_col(0) == (1, 1)
    assert src.offset_to_line_col(6) == (1, 7)  # EOF position, one past last char


def test_multi_line_lf():
    src = SourceFile("int x;\nint y;\n", "a.c")
    assert src.line_count == 3  # trailing newline opens an empty final line
    assert src.line_text(1) == "int x;"
    assert src.line_text(2) == "int y;"
    assert src.line_text(3) == ""
    assert src.offset_to_line_col(7) == (2, 1)  # first char of line 2
    assert src.offset_to_line_col(13) == (2, 7)  # ';' on line 2


def test_crlf_positions_match_lf_equivalent():
    lf = SourceFile("int x;\nint y;\n", "a.c")
    crlf = SourceFile("int x;\r\nint y;\r\n", "a.c")
    assert crlf.line_text(1) == lf.line_text(1) == "int x;"
    assert crlf.line_text(2) == lf.line_text(2) == "int y;"
    # 'y' is at the same column on both variants: \r stays on the previous line.
    lf_offset = lf.text.index("y")
    crlf_offset = crlf.text.index("y")
    assert lf.offset_to_line_col(lf_offset) == crlf.offset_to_line_col(crlf_offset) == (2, 5)


def test_golden_invalid_char_position():
    """R1.1 — 'int x@ = 5;' reports '@' at exactly 1:6."""
    src = SourceFile("int x@ = 5;\nint y = 10;\n", "a.c")
    at_offset = src.text.index("@")
    assert src.offset_to_line_col(at_offset) == (1, 6)


def test_line_col_to_offset_round_trips():
    src = SourceFile("int x;\nint y;\n", "a.c")
    for offset in range(len(src.text) + 1):
        line, col = src.offset_to_line_col(offset)
        assert src.line_col_to_offset(line, col) == offset


def test_offset_to_line_col_out_of_range_raises():
    src = SourceFile("int x;", "a.c")
    with pytest.raises(ValueError):
        src.offset_to_line_col(-1)
    with pytest.raises(ValueError):
        src.offset_to_line_col(len(src.text) + 1)


def test_line_text_out_of_range_raises():
    src = SourceFile("int x;", "a.c")
    with pytest.raises(ValueError):
        src.line_text(0)
    with pytest.raises(ValueError):
        src.line_text(2)


def test_line_col_to_offset_invalid_line_raises():
    src = SourceFile("int x;\nint y;\n", "a.c")
    with pytest.raises(ValueError, match="line 0"):
        src.line_col_to_offset(0, 1)
    with pytest.raises(ValueError, match="line 99"):
        src.line_col_to_offset(99, 1)


def test_line_col_to_offset_invalid_column_raises():
    src = SourceFile("int x;\nint y;\n", "a.c")
    with pytest.raises(ValueError, match="column"):
        src.line_col_to_offset(1, 0)
    with pytest.raises(ValueError, match="column"):
        src.line_col_to_offset(1, 999)

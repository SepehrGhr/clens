"""R3.5, R9.5 — truncation fuzz: every valid fixture, truncated at every
token position, must parse without raising.
"""

from pathlib import Path

import pytest

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import TokenType, iter_significant
from clens.languages.c import ast_nodes as ast
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser

VALID_FIXTURES = sorted((Path(__file__).parent.parent / "fixtures" / "valid").glob("*.c"))


def _truncated_with_eof(tokens: list, cut: int) -> list:
    """The first `cut` significant tokens, always ending in an EOF token
    (ParserBase requires it) so a truncated stream is still legal input.
    """
    truncated = tokens[:cut]
    if not truncated or truncated[-1].type is not TokenType.EOF:
        truncated = [*truncated, tokens[-1]]
    return truncated


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=lambda p: p.name)
def test_truncated_prefixes_never_raise(path: Path):
    source = SourceFile(path.read_text(), path.name)
    lex_diagnostics = DiagnosticCollector()
    tokens = list(iter_significant(tokenize(source, lex_diagnostics)))

    for cut in range(len(tokens) + 1):
        truncated = _truncated_with_eof(tokens, cut)
        diagnostics = DiagnosticCollector()
        parser = Parser(truncated, diagnostics)
        program = parser.parse_program()  # must not raise, for any prefix
        assert isinstance(program, ast.Program)


def test_full_valid_fixtures_parse_without_errors():
    """The untruncated files themselves should be error-free — a sanity
    check that the fuzz loop above is exercising real, valid C.
    """
    for path in VALID_FIXTURES:
        source = SourceFile(path.read_text(), path.name)
        diagnostics = DiagnosticCollector()
        tokens = list(iter_significant(tokenize(source, diagnostics)))
        parser = Parser(tokens, diagnostics)
        parser.parse_program()
        assert not diagnostics.errors, f"{path.name}: {[d.message for d in diagnostics.errors]}"

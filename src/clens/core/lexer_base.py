"""Generic master-regex scanner engine (R1.3, R1.5). Knows nothing about any
particular language: it is driven entirely by an ordered list of TokenRule
objects supplied by the caller. Adding a new language is a new rule table, not
a new engine.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from clens.core.diagnostics import Diagnostic, DiagnosticCollector, Position, Severity
from clens.core.source import SourceFile
from clens.core.token import Token, TokenType

#: Identity retype callback: never reclassifies a token.
_NO_RETYPE: Callable[[str, TokenType], TokenType] = lambda lexeme, token_type: token_type  # noqa: E731


@dataclass(frozen=True, slots=True)
class TokenRule:
    """One alternative in the master regex.

    ``name`` doubles as the regex group name and must be unique and a valid
    Python identifier. ``pattern`` is a raw, unanchored regex tried at the
    current scan position; ordering across the rule list matters (R1.3 —
    earlier rules win when more than one could match at the same position).

    ``diagnostic``, if set, marks this rule as an error-recovery rule: a
    match still produces a token (so scanning can continue treating it as
    the type it clearly meant to be), but also records a diagnostic. Used
    for unterminated strings/comments (R1.6, R1.7). ``diagnostic_span``
    controls how many characters starting at the match are underlined —
    typically just the opening delimiter, not the whole broken literal.
    """

    name: str
    type: TokenType
    pattern: str
    diagnostic: str | None = None
    diagnostic_code: str | None = None
    diagnostic_span: int = 1


def compile_master_regex(rules: Sequence[TokenRule]) -> re.Pattern[str]:
    """Compile an ordered rule list into one named-group alternation.

    ``re.DOTALL`` is enabled so that rules spanning multiple lines (block
    comments) can use ``.`` to mean "any character including newline";
    every other rule in this codebase uses explicit character classes, so
    the flag does not change their meaning.
    """
    pattern = "|".join(f"(?P<{rule.name}>{rule.pattern})" for rule in rules)
    return re.compile(pattern, re.DOTALL)


class LexerEngine:
    """Drives a compiled master regex over a SourceFile, applying keyword
    retyping and single-character recovery on unrecognized input.
    """

    def __init__(
        self,
        rules: Sequence[TokenRule],
        *,
        retype: Callable[[str, TokenType], TokenType] | None = None,
    ) -> None:
        self._rules_by_name = {rule.name: rule for rule in rules}
        self._master = compile_master_regex(rules)
        self._retype = retype or _NO_RETYPE

    def tokenize(self, source: SourceFile, diagnostics: DiagnosticCollector) -> list[Token]:
        """Scan ``source`` end to end into a flat token list, terminated by
        an EOF token. Never raises: unrecognized characters become
        single-character INVALID tokens with a diagnostic (R1.5).
        """
        text = source.text
        pos = 0
        length = len(text)
        tokens: list[Token] = []

        while pos < length:
            match = self._master.match(text, pos)
            if match is None:
                tokens.append(self._invalid_token(source, diagnostics, pos))
                pos += 1
                continue

            name = match.lastgroup
            assert name is not None, "every alternative in the master regex is named"
            lexeme = match.group(name)
            if not lexeme:
                # No rule should match empty; guard anyway so a bad pattern
                # can never hang the scanner (rule 1: never crash).
                tokens.append(self._invalid_token(source, diagnostics, pos))
                pos += 1
                continue

            rule = self._rules_by_name[name]
            token_type = self._retype(lexeme, rule.type)
            line, column = source.offset_to_line_col(pos)
            end = pos + len(lexeme)
            tokens.append(
                Token(
                    type=token_type,
                    lexeme=lexeme,
                    file=source.filename,
                    line=line,
                    column=column,
                    start_offset=pos,
                    end_offset=end,
                )
            )
            if rule.diagnostic is not None:
                self._add_rule_diagnostic(source, diagnostics, rule, pos, line, column)
            pos = end

        tokens.append(self._eof_token(source))
        return tokens

    def _add_rule_diagnostic(
        self,
        source: SourceFile,
        diagnostics: DiagnosticCollector,
        rule: TokenRule,
        pos: int,
        line: int,
        column: int,
    ) -> None:
        end_offset = min(pos + rule.diagnostic_span, len(source.text))
        end_line, end_column = source.offset_to_line_col(end_offset)
        diagnostics.add(
            Diagnostic(
                severity=Severity.ERROR,
                message=rule.diagnostic,
                file=source.filename,
                start=Position(line, column, pos),
                end=Position(end_line, end_column, end_offset),
                code=rule.diagnostic_code,
            )
        )

    def _invalid_token(
        self, source: SourceFile, diagnostics: DiagnosticCollector, pos: int
    ) -> Token:
        char = source.text[pos]
        line, column = source.offset_to_line_col(pos)
        diagnostics.add(
            Diagnostic(
                severity=Severity.ERROR,
                message=f"unrecognized character {char!r}",
                file=source.filename,
                start=Position(line, column, pos),
                end=Position(line, column + 1, pos + 1),
                code="E001-unrecognized-character",
            )
        )
        return Token(
            type=TokenType.INVALID,
            lexeme=char,
            file=source.filename,
            line=line,
            column=column,
            start_offset=pos,
            end_offset=pos + 1,
        )

    def _eof_token(self, source: SourceFile) -> Token:
        offset = len(source.text)
        line, column = source.offset_to_line_col(offset)
        return Token(
            type=TokenType.EOF,
            lexeme="",
            file=source.filename,
            line=line,
            column=column,
            start_offset=offset,
            end_offset=offset,
        )

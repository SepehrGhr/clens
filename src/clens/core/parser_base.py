"""Generic recursive-descent parser cursor (R3.1, R3.3).

Language-agnostic: knows token types but nothing about which lexemes mean
what in any particular language (D12 — no C keyword names here). The C
grammar's production functions and its synchronization lexeme set live in
`languages/c/parser.py`.
"""

from __future__ import annotations

from clens.core.diagnostics import Diagnostic, DiagnosticCollector, Position, Severity
from clens.core.token import Token, TokenType

__all__ = ["ParseError", "ParserBase"]


class ParseError(Exception):
    """Internal control-flow signal raised by `expect()`/`fail()` on a
    mismatch. Caught at the statement/declaration boundary, where
    `synchronize()` is called; never escapes `parse()`.
    """


class ParserBase:
    """A cursor over a flat, trivia-filtered token list (see
    `core.token.iter_significant`), plus the primitives every recursive-
    descent parser needs: lookahead, conditional consumption, diagnostic-
    raising expectation, and panic-mode synchronization.
    """

    def __init__(self, tokens: list[Token], diagnostics: DiagnosticCollector) -> None:
        if not tokens or tokens[-1].type is not TokenType.EOF:
            raise ValueError("token stream must be non-empty and end with an EOF token")
        self._tokens = tokens
        self._pos = 0
        self.diagnostics = diagnostics

    @property
    def pos(self) -> int:
        """Current cursor position, for callers that need a stuck-progress
        guard around their own recovery loops.
        """
        return self._pos

    def peek(self, offset: int = 0) -> Token:
        """The token `offset` positions ahead of the cursor, clamped to the
        trailing EOF token so lookahead never runs off the end.
        """
        index = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[index]

    def previous(self) -> Token:
        """The most recently consumed token."""
        return self._tokens[max(self._pos - 1, 0)]

    def at_end(self) -> bool:
        return self.peek().type is TokenType.EOF

    def advance(self) -> Token:
        """Consume and return the current token, unless already at EOF."""
        token = self.peek()
        if not self.at_end():
            self._pos += 1
        return token

    def check(self, *types: TokenType) -> bool:
        """Whether the current token's type is one of `types`."""
        return self.peek().type in types

    def check_lexeme(self, *lexemes: str) -> bool:
        """Whether the current token's exact lexeme is one of `lexemes`
        (for keywords/operators, which all share one TokenType).
        """
        return self.peek().lexeme in lexemes

    def match(self, *types: TokenType) -> Token | None:
        """Consume and return the current token if its type matches, else
        return None without consuming.
        """
        if self.check(*types):
            return self.advance()
        return None

    def match_lexeme(self, *lexemes: str) -> Token | None:
        """Consume and return the current token if its lexeme matches, else
        return None without consuming.
        """
        if self.check_lexeme(*lexemes):
            return self.advance()
        return None

    def expect(self, type_: TokenType, lexeme: str, context: str = "") -> Token:
        """Consume a token of `type_` with exactly `lexeme`, or emit a
        diagnostic and raise ParseError (R3.5): "expected 'x' <context>,
        got 'y'".
        """
        if self.check(type_) and self.peek().lexeme == lexeme:
            return self.advance()
        suffix = f" {context}" if context else ""
        self.fail(f"expected '{lexeme}'{suffix}, got {self._describe_current()}")

    def expect_type(self, type_: TokenType, description: str, context: str = "") -> Token:
        """Consume a token of `type_` regardless of lexeme (e.g. any
        IDENT), or emit a diagnostic and raise ParseError.
        """
        if self.check(type_):
            return self.advance()
        suffix = f" {context}" if context else ""
        self.fail(f"expected {description}{suffix}, got {self._describe_current()}")

    def fail(self, message: str) -> None:
        """Emit a diagnostic at the current token and raise ParseError.
        Never returns (return type is None only because Python has no
        bottom type without extra ceremony; callers should treat this as
        unreachable after the call).
        """
        self.error(message)
        raise ParseError(message)

    def error(self, message: str, token: Token | None = None) -> None:
        """Record a diagnostic without raising — for recoverable notices
        (e.g. "unsupported construct") that don't need panic-mode.
        """
        token = token or self.peek()
        end_column = token.column + max(1, len(token.lexeme))
        self.diagnostics.add(
            Diagnostic(
                severity=Severity.ERROR,
                message=message,
                file=token.file,
                start=Position(token.line, token.column, token.start_offset),
                end=Position(token.line, end_column, token.end_offset),
            )
        )

    def _describe_current(self) -> str:
        token = self.peek()
        if token.type is TokenType.EOF:
            return "end of file"
        return f"'{token.lexeme}'"

    def synchronize(self, sync_lexemes: frozenset[str]) -> None:
        """Panic-mode recovery (R3.3): skip tokens until a semicolon
        (consumed — the statement is over), a '}' (not consumed — the
        enclosing block needs it to close), a lexeme in `sync_lexemes`
        (not consumed — resume parsing from there), or EOF.
        """
        while not self.at_end():
            if self.peek().lexeme == ";":
                self.advance()
                return
            if self.peek().lexeme == "}":
                return
            if self.peek().lexeme in sync_lexemes:
                return
            self.advance()

    def guard_progress(self, pos_before: int) -> None:
        """Force one `advance()` if a parse-and-recover cycle left the
        cursor exactly where it started. Belt-and-suspenders against an
        infinite loop in a caller's recovery loop (rule 1: never hang).
        """
        if self._pos == pos_before and not self.at_end():
            self.advance()

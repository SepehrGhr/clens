"""clens command-line entry point (R7.1): `tokens`, `ast`, `highlight`,
`check`, `symbols`, each with `--json` and `-o/--output`; `highlight`
additionally takes `--format ansi|html`.

Exit codes: `0` clean, `1` diagnostics with ERROR severity present,
`2` internal failure. Rule 1 (never crash) means `2` should be unreachable
in practice — `main()`'s top-level guard exists so that if something we
did not anticipate goes wrong, the user sees one line on stderr, never a
traceback.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from clens.core.ast_nodes import Node
from clens.core.ast_printer import format_ast
from clens.core.diagnostics import Diagnostic, DiagnosticCollector, Position, Severity
from clens.core.scopes import Scope
from clens.core.source import SourceFile
from clens.core.symbols import Symbol
from clens.core.token import Span, Token, iter_significant
from clens.languages.c.highlighter import highlight as highlight_program
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.languages.c.semantic import analyze
from clens.render.ansi import render_ansi
from clens.render.html import render_html


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="clens",
        description="A code-aware IDE feature set for a subset of C.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    tokens_parser = subparsers.add_parser("tokens", help="dump the token stream")
    _add_common_arguments(tokens_parser)

    ast_parser = subparsers.add_parser("ast", help="pretty-print the AST")
    _add_common_arguments(ast_parser)

    highlight_parser = subparsers.add_parser("highlight", help="syntax-highlight a file")
    _add_common_arguments(highlight_parser)
    highlight_parser.add_argument(
        "--format", choices=["ansi", "html"], default="ansi", help="output format (default: ansi)"
    )

    check_parser = subparsers.add_parser("check", help="report diagnostics only")
    _add_common_arguments(check_parser)

    symbols_parser = subparsers.add_parser("symbols", help="dump the symbol table")
    _add_common_arguments(symbols_parser)

    return parser


def _add_common_arguments(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("file", help="C source file")
    subparser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    subparser.add_argument(
        "-o", "--output", metavar="OUT", help="write output to this file instead of stdout"
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point registered as the ``clens`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001 - rule 1: never let a traceback reach the user
        print(f"clens: internal error: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    diagnostics = DiagnosticCollector()
    source = _load_source(args.file, diagnostics)
    if source is None:
        _report_load_failure(diagnostics, args)
        return 1

    output, cmd_diagnostics = _COMMANDS[args.command](source, args)
    _write_output(output, args)
    return 1 if cmd_diagnostics.has_errors else 0


def _load_source(path_str: str, diagnostics: DiagnosticCollector) -> SourceFile | None:
    """Read `path_str` into a SourceFile. Never raises: a missing path, a
    directory, or unreadable bytes all become one ERROR diagnostic instead
    (R9.5) -- there is no encoding under which reading a file can crash
    this function.
    """
    path = Path(path_str)
    if not path.exists():
        diagnostics.add(_file_error(path_str, "no such file or directory"))
        return None
    if path.is_dir():
        diagnostics.add(_file_error(path_str, "is a directory, not a file"))
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        diagnostics.add(_file_error(path_str, str(exc)))
        return None
    text = raw.decode("utf-8", errors="replace")
    return SourceFile(text, path_str)


def _file_error(path_str: str, message: str) -> Diagnostic:
    zero = Position(line=1, column=1, offset=0)
    return Diagnostic(
        severity=Severity.ERROR,
        message=f"{message}: {path_str}",
        file=path_str,
        start=zero,
        end=zero,
        code="E000-file-error",
    )


def _report_load_failure(diagnostics: DiagnosticCollector, args: argparse.Namespace) -> None:
    if getattr(args, "json", False):
        _write_output(diagnostics.to_json(), args)
    else:
        print(f"clens: {diagnostics.diagnostics[0].message}", file=sys.stderr)


def _write_output(text: str, args: argparse.Namespace) -> None:
    output_path = getattr(args, "output", None)
    if output_path:
        Path(output_path).write_text(text)
    else:
        print(text)


def _tokenize_and_parse(source: SourceFile, diagnostics: DiagnosticCollector):
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    return tokens, program


# --- Subcommands -------------------------------------------------------------


def _cmd_tokens(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    if args.json:
        payload = [_token_to_dict(t) for t in tokens]
        return json.dumps(payload, indent=2), diagnostics
    lines = [f"{t.line}:{t.column} {t.type.name} {t.lexeme!r}" for t in tokens]
    return "\n".join(lines), diagnostics


def _token_to_dict(token: Token) -> dict:
    return {
        "type": token.type.name,
        "lexeme": token.lexeme,
        "line": token.line,
        "column": token.column,
        "start_offset": token.start_offset,
        "end_offset": token.end_offset,
    }


def _cmd_ast(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    _, program = _tokenize_and_parse(source, diagnostics)
    if args.json:
        return json.dumps(_to_jsonable(program), indent=2), diagnostics
    return format_ast(program), diagnostics


def _to_jsonable(value: object) -> object:
    if isinstance(value, Node):
        result: dict[str, object] = {"node": type(value).__name__}
        for f in dataclasses.fields(value):
            if f.name == "span":
                continue
            result[f.name] = _to_jsonable(getattr(value, f.name))
        result["span"] = _to_jsonable(value.span)
        return result
    if isinstance(value, Span):
        return {
            "line": value.line,
            "column": value.column,
            "start_offset": value.start_offset,
            "end_offset": value.end_offset,
        }
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    return value  # str, int, float, bool, None


def _cmd_highlight(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens, program = _tokenize_and_parse(source, diagnostics)
    highlight_map = highlight_program(tokens, program)
    if args.json:
        payload = [
            {"token_index": index, "category": category.value}
            for index, category in sorted(highlight_map.items())
        ]
        return json.dumps(payload, indent=2), diagnostics
    if args.format == "html":
        return render_html(source, tokens, highlight_map), diagnostics
    return render_ansi(source, tokens, highlight_map), diagnostics


def _cmd_check(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    _tokenize_and_parse(source, diagnostics)
    if args.json:
        return diagnostics.to_json(), diagnostics
    if not diagnostics.diagnostics:
        return "no diagnostics", diagnostics
    return diagnostics.format_pretty(source), diagnostics


def _cmd_symbols(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    _, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    if args.json:
        return json.dumps(_scope_to_dict(model.global_scope), indent=2), diagnostics
    return "\n".join(_render_scope(model.global_scope, 0)), diagnostics


def _scope_to_dict(scope: Scope) -> dict:
    return {
        "kind": scope.kind.value,
        "symbols": [_symbol_to_dict(s) for s in scope.symbols.values()],
        "children": [_scope_to_dict(c) for c in scope.children],
    }


def _symbol_to_dict(symbol: Symbol) -> dict:
    return {
        "name": symbol.name,
        "kind": symbol.kind.value,
        "type": str(symbol.type),
        "line": symbol.definition_loc.line,
        "column": symbol.definition_loc.column,
        "is_used": symbol.is_used,
        "is_initialized": symbol.is_initialized,
    }


def _render_scope(scope: Scope, depth: int) -> list[str]:
    indent = "  " * depth
    lines = [f"{indent}{scope.kind.value.upper()}"]
    for symbol in scope.symbols.values():
        lines.append(f"{indent}  {symbol.name}: {symbol.kind.value} {symbol.type}")
    for child in scope.children:
        lines.extend(_render_scope(child, depth + 1))
    return lines


_COMMANDS = {
    "tokens": _cmd_tokens,
    "ast": _cmd_ast,
    "highlight": _cmd_highlight,
    "check": _cmd_check,
    "symbols": _cmd_symbols,
}


if __name__ == "__main__":
    sys.exit(main())

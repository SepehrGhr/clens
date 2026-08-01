"""clens command-line entry point (R7.1): `tokens`, `ast`, `highlight`,
`check`, `symbols`, `complete`, `hover`, each with `--json` and
`-o/--output`; `highlight` additionally takes `--format ansi|html`;
`complete`/`hover` additionally take a 1-based `line` and `col`.

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
from clens.core.cfg import BlockKind, ControlFlowGraph
from clens.core.diagnostics import Diagnostic, DiagnosticCollector, Position, Severity
from clens.core.graph_layout import layered_layout
from clens.core.scopes import Scope
from clens.core.source import SourceFile
from clens.core.token import Span, Token, iter_significant
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.call_graph import (
    CallGraph,
    build_call_graph,
    dead_functions,
    recursive_functions,
)
from clens.languages.c.cfg_builder import build_cfg, describe_node, render_cfg_text
from clens.languages.c.dead_code import DeadCodeReport, find_dead_code
from clens.languages.c.highlighter import highlight as highlight_program
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.languages.c.program_analysis import analyze_program
from clens.languages.c.queries import (
    CompletionItem,
    HoverInfo,
    completions_at,
    definition_info_to_dict,
    find_references_by_name,
    find_references_to_dict,
    goto_definition_at,
    hover_at,
    scope_to_dict,
)
from clens.languages.c.rename import rename_symbol_at
from clens.languages.c.semantic import analyze
from clens.render.ansi import render_ansi
from clens.render.html import render_html
from clens.render.svg import render_svg
from clens.web.server import serve


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

    complete_parser = subparsers.add_parser("complete", help="completion list at a cursor")
    _add_common_arguments(complete_parser)
    _add_position_arguments(complete_parser)

    hover_parser = subparsers.add_parser("hover", help="hover info at a cursor")
    _add_common_arguments(hover_parser)
    _add_position_arguments(hover_parser)

    goto_def_parser = subparsers.add_parser("goto-def", help="go to a symbol's definition")
    _add_common_arguments(goto_def_parser)
    _add_position_arguments(goto_def_parser)

    find_refs_parser = subparsers.add_parser("find-refs", help="find every reference to a symbol")
    _add_common_arguments(find_refs_parser)
    find_refs_parser.add_argument("symbol", help="name of the symbol to find references to")

    rename_parser = subparsers.add_parser("rename", help="scope-aware rename by symbol identity")
    _add_common_arguments(rename_parser)
    _add_position_arguments(rename_parser)
    rename_parser.add_argument("new_name", help="the new name")
    rename_parser.add_argument(
        "--apply",
        action="store_true",
        help="write the change to disk (default: show the diff only)",
    )

    show_cfg_parser = subparsers.add_parser("show-cfg", help="show a function's control flow graph")
    _add_common_arguments(show_cfg_parser)
    show_cfg_parser.add_argument("function", help="name of the function to graph")
    show_cfg_parser.add_argument(
        "--format", choices=["text", "svg"], default="text", help="output format (default: text)"
    )

    callgraph_parser = subparsers.add_parser("callgraph", help="show the program's call graph")
    _add_common_arguments(callgraph_parser)
    callgraph_parser.add_argument(
        "--format", choices=["text", "svg"], default="text", help="output format (default: text)"
    )

    dead_code_parser = subparsers.add_parser(
        "dead-code", help="report all five A6 dead-code categories"
    )
    _add_common_arguments(dead_code_parser)

    serve_parser = subparsers.add_parser("serve", help="start the interactive web UI")
    serve_parser.add_argument("--port", type=int, default=8000, help="port to listen on")
    serve_parser.add_argument("--host", default="127.0.0.1", help="host to bind (default: local)")

    return parser


def _add_common_arguments(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("file", help="C source file")
    subparser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    subparser.add_argument(
        "-o", "--output", metavar="OUT", help="write output to this file instead of stdout"
    )


def _add_position_arguments(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("line", type=int, help="1-based line number")
    subparser.add_argument("col", type=int, help="1-based column number")


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
    if args.command == "serve":
        return _cmd_serve(args)

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
    tokens, program = _tokenize_and_parse(source, diagnostics)
    analyze(program, source, diagnostics, tokens=tokens)
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
        return json.dumps(scope_to_dict(model.global_scope), indent=2), diagnostics
    return "\n".join(_render_scope(model.global_scope, 0)), diagnostics


def _render_scope(scope: Scope, depth: int) -> list[str]:
    indent = "  " * depth
    lines = [f"{indent}{scope.kind.value.upper()}"]
    for symbol in scope.symbols.values():
        lines.append(f"{indent}  {symbol.name}: {symbol.kind.value} {symbol.type}")
    for child in scope.children:
        lines.extend(_render_scope(child, depth + 1))
    return lines


def _cmd_complete(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    offset = _offset_for(source, args, diagnostics)
    if offset is None:
        return _position_error_output(diagnostics, args), diagnostics
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    items = completions_at(model, offset)
    return _position_output(items, args), diagnostics


def _cmd_hover(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    offset = _offset_for(source, args, diagnostics)
    if offset is None:
        return _position_error_output(diagnostics, args), diagnostics
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    info = hover_at(model, offset)
    return _position_output(info, args), diagnostics


def _offset_for(
    source: SourceFile, args: argparse.Namespace, diagnostics: DiagnosticCollector
) -> int | None:
    """`args.line`/`args.col` to a 0-based offset, or `None` (with an
    ERROR diagnostic added) if the position is out of range for `source`.
    A typo'd line/column is a plausible, ordinary mistake — it gets a
    normal diagnostic and exit code 1, not the top-level internal-error
    fallback.
    """
    try:
        return source.line_col_to_offset(args.line, args.col)
    except ValueError as exc:
        diagnostics.add(_file_error(args.file, str(exc)))
        return None


def _position_error_output(diagnostics: DiagnosticCollector, args: argparse.Namespace) -> str:
    """Render the *most recently added* diagnostic as the command's error
    output. Always the last one, not the first: for a plain out-of-range
    line/col this is the only diagnostic there is, but `find-refs`,
    `rename`, and `show-cfg` add their own "not found" error *after*
    already running the full pipeline, so earlier semantic diagnostics
    (a warning on an unrelated line) must not bury it.
    """
    message = diagnostics.diagnostics[-1].message
    if args.json:
        return json.dumps({"error": message}, indent=2)
    return f"clens: {message}"


def _position_output(
    result: list[CompletionItem] | HoverInfo | None, args: argparse.Namespace
) -> str:
    if args.json:
        return json.dumps(_position_result_to_jsonable(result), indent=2)
    if result is None:
        return "no hover information"
    if isinstance(result, list):
        if not result:
            return "no completions"
        return "\n".join(f"{i.label}  {i.kind}  {i.detail}" for i in result)
    lines = [result.signature, result.scope_description]
    if result.doc_comment:
        lines.append(result.doc_comment)
    return "\n".join(lines)


def _position_result_to_jsonable(result: list[CompletionItem] | HoverInfo | None) -> object:
    if result is None:
        return None
    if isinstance(result, list):
        return [
            {"label": i.label, "kind": i.kind, "detail": i.detail, "sortOrder": i.sort_order}
            for i in result
        ]
    return {
        "signature": result.signature,
        "scopeDescription": result.scope_description,
        "docComment": result.doc_comment,
    }


def _cmd_goto_def(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    offset = _offset_for(source, args, diagnostics)
    if offset is None:
        return _position_error_output(diagnostics, args), diagnostics
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    info = goto_definition_at(model, offset)
    if info is None:
        if args.json:
            return json.dumps({"result": None}, indent=2), diagnostics
        return "no definition found", diagnostics
    payload = definition_info_to_dict(model, info)
    if args.json:
        return json.dumps(payload, indent=2), diagnostics
    return _render_definition_text(payload), diagnostics


def _render_definition_text(payload: dict) -> str:
    d = payload["defined_at"]
    return (
        f"{payload['symbol']} ({payload['kind']} {payload['type']}) "
        f"defined at {d['file']}:{d['line']}:{d['col']}"
    )


def _cmd_find_refs(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    matches = find_references_by_name(model, args.symbol)
    if not matches:
        diagnostics.add(_file_error(args.file, f"no such symbol: {args.symbol}"))
        return _position_error_output(diagnostics, args), diagnostics
    payloads = [find_references_to_dict(model, symbol, refs) for symbol, refs in matches]
    if args.json:
        result = payloads[0] if len(payloads) == 1 else payloads
        return json.dumps(result, indent=2), diagnostics
    return "\n\n".join(_render_find_refs_text(p) for p in payloads), diagnostics


def _render_find_refs_text(payload: dict) -> str:
    lines = [_render_definition_text(payload)]
    lines.extend(f"  {r['file']}:{r['line']}:{r['col']}" for r in payload["references"])
    return "\n".join(lines)


def _cmd_rename(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    offset = _offset_for(source, args, diagnostics)
    if offset is None:
        return _position_error_output(diagnostics, args), diagnostics
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    result = rename_symbol_at(model, source, offset, args.new_name)
    if not result.ok:
        diagnostics.add(_file_error(args.file, result.error or "rename refused"))
        return _position_error_output(diagnostics, args), diagnostics
    if args.apply:
        Path(args.file).write_text(result.new_text)
    if args.json:
        payload = {"diff": result.diff, "applied": args.apply}
        return json.dumps(payload, indent=2), diagnostics
    output = result.diff
    if args.apply:
        output += "\napplied.\n"
    return output, diagnostics


def _cmd_show_cfg(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    _, program = _tokenize_and_parse(source, diagnostics)
    func = next(
        (d for d in program.declarations if isinstance(d, FuncDecl) and d.name == args.function),
        None,
    )
    if func is None:
        diagnostics.add(_file_error(args.file, f"no such function: {args.function}"))
        return _position_error_output(diagnostics, args), diagnostics
    cfg = build_cfg(func)
    if cfg is None:
        diagnostics.add(_file_error(args.file, f"{args.function} has no body (a prototype)"))
        return _position_error_output(diagnostics, args), diagnostics
    if args.json:
        return json.dumps(_cfg_to_dict(cfg), indent=2), diagnostics
    if args.format == "svg":
        svg = render_svg(_cfg_layout(cfg), highlighted_ids=frozenset({"ENTRY", "EXIT"}))
        return svg, diagnostics
    return render_cfg_text(cfg), diagnostics


def _cfg_layout(cfg: ControlFlowGraph):
    normals = sorted((b for b in cfg.blocks if b.kind is BlockKind.NORMAL), key=lambda b: b.id)
    ordered = [cfg.entry, *normals, cfg.exit]
    node_ids = [b.label() for b in ordered]
    labels = {
        b.label(): "\n".join([b.label(), *(describe_node(s) for s in b.statements)])
        for b in ordered
    }
    edges = [
        (block.label(), target.label(), label.value)
        for block in ordered
        for target, label in block.successors
    ]
    return layered_layout(node_ids, labels, edges, root=cfg.entry.label())


def _cfg_to_dict(cfg: ControlFlowGraph) -> dict:
    normals = sorted((b for b in cfg.blocks if b.kind is BlockKind.NORMAL), key=lambda b: b.id)
    ordered = [cfg.entry, *normals, cfg.exit]
    return {
        "function": cfg.function_name,
        "blocks": [
            {
                "id": block.label(),
                "statements": [describe_node(s) for s in block.statements],
                "successors": [
                    {"target": target.label(), "label": label.value}
                    for target, label in block.successors
                ],
            }
            for block in ordered
        ],
    }


def _cmd_callgraph(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    call_graph = build_call_graph(model)
    if args.json:
        return json.dumps(_call_graph_to_dict(call_graph), indent=2), diagnostics
    if args.format == "svg":
        return render_svg(_call_graph_layout(call_graph)), diagnostics
    return _render_call_graph_text(call_graph), diagnostics


def _call_graph_layout(call_graph: CallGraph):
    node_ids = sorted(call_graph.graph.nodes)
    labels = {name: name for name in node_ids}
    edges = [(e.caller, e.callee, "") for e in call_graph.edges]
    root = "main" if call_graph.has_main else (node_ids[0] if node_ids else "")
    return layered_layout(node_ids, labels, edges, root=root)


def _call_graph_to_dict(call_graph: CallGraph) -> dict:
    return {
        "nodes": sorted(call_graph.graph.nodes),
        "edges": [
            {"caller": e.caller, "callee": e.callee, "line": e.site.line, "col": e.site.column}
            for e in sorted(call_graph.edges, key=lambda e: (e.caller, e.callee))
        ],
        "unresolved": [
            {"caller": u.caller, "callee": u.callee_name, "line": u.site.line, "col": u.site.column}
            for u in sorted(call_graph.unresolved, key=lambda u: (u.caller, u.callee_name))
        ],
        "hasMain": call_graph.has_main,
        "deadFunctions": sorted(dead_functions(call_graph)),
        "recursiveFunctions": sorted(recursive_functions(call_graph)),
        "stronglyConnectedComponents": [
            sorted(component)
            for component in sorted(
                call_graph.graph.strongly_connected_components(), key=lambda c: sorted(c)
            )
        ],
    }


def _render_call_graph_text(call_graph: CallGraph) -> str:
    lines = []
    for name in sorted(call_graph.graph.nodes):
        callees = sorted(call_graph.graph.successors(name))
        lines.append(f"{name} -> {', '.join(callees)}" if callees else name)
    dead = sorted(dead_functions(call_graph))
    if dead:
        lines.append(f"dead: {', '.join(dead)}")
    recursive = sorted(recursive_functions(call_graph))
    if recursive:
        lines.append(f"recursive: {', '.join(recursive)}")
    return "\n".join(lines)


def _cmd_dead_code(source: SourceFile, args: argparse.Namespace) -> tuple[str, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens, program = _tokenize_and_parse(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    analysis = analyze_program(model)
    report = find_dead_code(analysis)
    if args.json:
        return json.dumps(_dead_code_to_dict(report), indent=2), diagnostics
    return _render_dead_code_text(report), diagnostics


def _dead_code_to_dict(report: DeadCodeReport) -> dict:
    return {
        "unreachableFunctions": report.unreachable_functions,
        "unreachableBlocks": [
            {"function": b.function, "block": b.block_label} for b in report.unreachable_blocks
        ],
        "postJumpStatements": [
            {"function": p.function, "text": p.text, "line": p.span.line, "col": p.span.column}
            for p in report.post_jump_statements
        ],
        "unusedVariables": [
            {"function": u.function, "name": u.symbol.name, "line": u.symbol.definition_loc.line}
            for u in report.unused_variables
        ],
        "deadAssignments": [
            {
                "function": d.function,
                "name": d.symbol.name,
                "line": d.span.line,
                "col": d.span.column,
            }
            for d in report.dead_assignments
        ],
    }


def _render_dead_code_text(report: DeadCodeReport) -> str:
    lines = []
    for name in report.unreachable_functions:
        lines.append(f"[warning] unreachable function: {name}")
    for b in report.unreachable_blocks:
        lines.append(f"[warning] unreachable block {b.block_label} in {b.function}")
    for p in report.post_jump_statements:
        lines.append(f"[warning] {p.function}:{p.span.line}:{p.span.column}: unreachable: {p.text}")
    for u in report.unused_variables:
        lines.append(f"[info] {u.function}: unused variable '{u.symbol.name}'")
    for d in report.dead_assignments:
        lines.append(
            f"[warning] {d.function}:{d.span.line}:{d.span.column}: "
            f"dead assignment to '{d.symbol.name}'"
        )
    return "\n".join(lines) if lines else "no dead code found"


def _cmd_serve(args: argparse.Namespace) -> int:
    """`serve` has no `file` argument, so it bypasses `_COMMANDS` and
    `_load_source` entirely (handled in `_run`) — it starts the web UI
    (D22) and blocks until interrupted.
    """
    serve(host=args.host, port=args.port)
    return 0


_COMMANDS = {
    "tokens": _cmd_tokens,
    "ast": _cmd_ast,
    "highlight": _cmd_highlight,
    "check": _cmd_check,
    "symbols": _cmd_symbols,
    "complete": _cmd_complete,
    "hover": _cmd_hover,
    "goto-def": _cmd_goto_def,
    "find-refs": _cmd_find_refs,
    "rename": _cmd_rename,
    "show-cfg": _cmd_show_cfg,
    "callgraph": _cmd_callgraph,
    "dead-code": _cmd_dead_code,
}


if __name__ == "__main__":
    sys.exit(main())

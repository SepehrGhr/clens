"""The web UI backend (D22): stdlib `http.server` only, no third-party
dependency. Each `/api/*` endpoint is a thin adapter over
`languages/c/queries.py` — the actual analysis, completion, and hover
logic lives there, not here (D23).

The per-endpoint logic is three plain functions (`handle_analyze`,
`handle_complete`, `handle_hover`) taking and returning plain dicts, kept
separate from `ClensRequestHandler`'s HTTP plumbing specifically so tests
can call them directly without a socket.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.call_graph import (
    build_call_graph,
    call_graph_layout,
    dead_functions,
    recursive_functions,
)
from clens.languages.c.cfg_builder import ENTRY_EXIT_LABELS, build_cfg, cfg_layout
from clens.languages.c.dead_code import find_dead_code
from clens.languages.c.highlighter import highlight as highlight_program
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.languages.c.program_analysis import analyze_program
from clens.languages.c.queries import completions_at, hover_at, scope_to_dict
from clens.languages.c.semantic import analyze
from clens.render.svg import render_svg
from clens.web.renderer import generate_theme_css, render_interactive

__all__ = [
    "ClensRequestHandler",
    "dispatch_post",
    "handle_analyze",
    "handle_callgraph",
    "handle_cfg",
    "handle_complete",
    "handle_dead_code",
    "handle_hover",
    "serve",
]

STATIC_DIR = Path(__file__).parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def _build_model(text: str):
    """Tokenize, parse, and analyze `text` from scratch (D21: a full
    re-run per request — files are small, correctness beats latency).
    Shared by all three endpoints.
    """
    source = SourceFile(text, "<web>")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    model = analyze(program, source, diagnostics, tokens=tokens)
    return source, diagnostics, tokens, program, model


def handle_analyze(body: dict[str, Any]) -> dict[str, Any]:
    """`{source}` -> `{html, diagnostics, symbols}`."""
    text = body.get("source", "")
    source, diagnostics, tokens, program, model = _build_model(text)
    highlight_map = highlight_program(tokens, program)
    return {
        "html": render_interactive(source, tokens, highlight_map),
        "diagnostics": [d.to_dict() for d in diagnostics.sorted()],
        "symbols": scope_to_dict(model.global_scope),
    }


def handle_complete(body: dict[str, Any]) -> dict[str, Any]:
    """`{source, line, column}` -> `{items}`."""
    offset, model = _offset_and_model(body)
    if offset is None:
        return {"items": []}
    items = completions_at(model, offset)
    return {
        "items": [
            {"label": i.label, "kind": i.kind, "detail": i.detail, "sortOrder": i.sort_order}
            for i in items
        ]
    }


def handle_hover(body: dict[str, Any]) -> dict[str, Any]:
    """`{source, line, column}` -> `{info}`."""
    offset, model = _offset_and_model(body)
    if offset is None:
        return {"info": None}
    info = hover_at(model, offset)
    if info is None:
        return {"info": None}
    return {
        "info": {
            "signature": info.signature,
            "scopeDescription": info.scope_description,
            "docComment": info.doc_comment,
        }
    }


def handle_cfg(body: dict[str, Any]) -> dict[str, Any]:
    """`{source, function}` -> `{svg}`, or `{svg: None, error}` if there is
    no such function or it is a prototype with no body -- never a 500;
    both are ordinary, expected states while a user is editing.
    """
    text = body.get("source", "")
    function_name = body.get("function", "")
    _source, _diagnostics, _tokens, program, _model = _build_model(text)
    func = next(
        (d for d in program.declarations if isinstance(d, FuncDecl) and d.name == function_name),
        None,
    )
    if func is None:
        return {"svg": None, "error": f"no such function: {function_name}"}
    cfg = build_cfg(func)
    if cfg is None:
        return {"svg": None, "error": f"{function_name} has no body (a prototype)"}
    svg = render_svg(cfg_layout(cfg), highlighted_ids=ENTRY_EXIT_LABELS)
    return {"svg": svg}


def handle_callgraph(body: dict[str, Any]) -> dict[str, Any]:
    """`{source}` -> `{svg, deadFunctions, recursiveFunctions}`."""
    text = body.get("source", "")
    _source, _diagnostics, _tokens, _program, model = _build_model(text)
    call_graph = build_call_graph(model)
    svg = render_svg(call_graph_layout(call_graph))
    return {
        "svg": svg,
        "deadFunctions": sorted(dead_functions(call_graph)),
        "recursiveFunctions": sorted(recursive_functions(call_graph)),
    }


def handle_dead_code(body: dict[str, Any]) -> dict[str, Any]:
    """`{source}` -> `{unreachableFunctions, unreachableBlocks,
    postJumpStatements, unusedVariables, deadAssignments}` (A6)."""
    text = body.get("source", "")
    _source, _diagnostics, _tokens, _program, model = _build_model(text)
    analysis = analyze_program(model)
    report = find_dead_code(analysis)
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


def _offset_and_model(body: dict[str, Any]):
    """Shared by complete/hover: build a model from `body["source"]` and
    convert `body["line"]`/`body["column"]` to an offset. Never raises —
    a missing field, a wrong type, or an out-of-range position all yield
    `(None, model)` so the caller returns an empty result instead of a
    500.
    """
    text = body.get("source", "")
    _source, _diagnostics, _tokens, _program, model = _build_model(text)
    try:
        line = int(body["line"])
        column = int(body["column"])
        offset = model.source.line_col_to_offset(line, column)
    except (KeyError, TypeError, ValueError):
        return None, model
    return offset, model


_POST_ROUTES = {
    "/api/analyze": handle_analyze,
    "/api/complete": handle_complete,
    "/api/hover": handle_hover,
    "/api/cfg": handle_cfg,
    "/api/callgraph": handle_callgraph,
    "/api/dead-code": handle_dead_code,
}


def dispatch_post(path: str, raw_body: bytes) -> tuple[dict[str, Any], int]:
    """The whole `POST /api/*` routing decision as a pure function of a
    path and raw request bytes: `(response_payload, status_code)`. Kept
    separate from `ClensRequestHandler` so every case (unknown route,
    malformed JSON, a non-object body, a handler that somehow raises) is
    testable without a socket or a real request object.
    """
    handler = _POST_ROUTES.get(path)
    if handler is None:
        return {"error": "not found"}, 404
    try:
        body = json.loads(raw_body) if raw_body else {}
        if not isinstance(body, dict):
            raise ValueError("request body must be a JSON object")
    except (json.JSONDecodeError, ValueError):
        return {"error": "malformed request body"}, 400
    try:
        return handler(body), 200
    except Exception as exc:  # noqa: BLE001 - rule 1: never let this reach the client
        return {"error": f"internal error: {exc}"}, 500


class ClensRequestHandler(BaseHTTPRequestHandler):
    """Routes `GET /`, `GET /static/*`, and the three `POST /api/*`
    endpoints. All feature logic lives in `dispatch_post`, the
    module-level `handle_*` functions, and `languages/c/queries.py`; this
    class only does I/O.
    """

    server_version = "clens/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        if self.path == "/":
            self._serve_static("index.html")
        elif self.path.startswith("/static/"):
            self._serve_static(self.path[len("/static/") :])
        else:
            self.send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        payload, status = dispatch_post(self.path, raw)
        self._send_json(payload, status=status)

    def _serve_static(self, relative: str) -> None:
        if relative == "theme.css":
            self._send_bytes(generate_theme_css().encode("utf-8"), "text/css; charset=utf-8")
            return
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents or not path.is_file():
            self.send_error(404, "not found")
            return
        content_type = _CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        self._send_bytes(path.read_bytes(), content_type)

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # keep `clens serve` and test output quiet; nothing here is an error


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the web UI, blocking until interrupted. Binds to localhost by
    default (D22): this is a local dev tool, not a public service.
    """
    server = HTTPServer((host, port), ClensRequestHandler)
    print(f"clens serving on http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

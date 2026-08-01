"""S8.2, D22, D23 — the web UI backend, tested via the handler functions
directly (no socket, no live server) per the web-ui skill's own guidance:
one test per endpoint, plus malformed JSON, a missing field, and a source
that fails to parse. A handful of live-socket tests cover the HTTP
plumbing itself (`ClensRequestHandler`), which the handler-level tests
above never touch.
"""

import http.client
import json
import threading
from http.server import HTTPServer

import pytest

from clens.core.highlight import Category
from clens.core.theme import THEME
from clens.web.renderer import generate_theme_css
from clens.web.server import (
    ClensRequestHandler,
    dispatch_post,
    handle_analyze,
    handle_callgraph,
    handle_cfg,
    handle_complete,
    handle_dead_code,
    handle_hover,
)

# --- /api/analyze ----------------------------------------------------------


def test_handle_analyze_returns_html_diagnostics_and_symbols():
    result = handle_analyze({"source": "int g = 1;\n"})
    assert "data-start" in result["html"]
    assert result["html"].startswith("<pre>")
    assert result["diagnostics"] == []
    assert result["symbols"]["kind"] == "global"
    names = {s["name"] for s in result["symbols"]["symbols"]}
    assert names == {"g"}


def test_handle_analyze_reports_semantic_diagnostics():
    result = handle_analyze({"source": "int x = 3.14;\n"})
    assert len(result["diagnostics"]) == 1
    assert result["diagnostics"][0]["severity"] == "warning"
    assert result["diagnostics"][0]["code"] == "S010"


def test_handle_analyze_missing_source_field_is_empty_file_not_a_crash():
    result = handle_analyze({})
    assert result["diagnostics"] == []
    assert result["symbols"]["kind"] == "global"


def test_handle_analyze_source_that_fails_to_parse_still_returns_a_result():
    """A syntax error must not crash the endpoint - Phase 1's recovery
    guarantees a partial AST either way."""
    result = handle_analyze({"source": "int x = ;\n"})
    assert any(d["severity"] == "error" for d in result["diagnostics"])
    assert result["html"].startswith("<pre>")


# --- /api/complete -----------------------------------------------------


def test_handle_complete_returns_matching_items():
    text = "int factorial(int n) { return n; }\nvoid f(void) {\n    factorial;\n}\n"
    result = handle_complete({"source": text, "line": 3, "column": 8})
    labels = [i["label"] for i in result["items"]]
    assert "factorial" in labels
    item = next(i for i in result["items"] if i["label"] == "factorial")
    assert item["kind"] == "function"
    assert item["detail"] == "(int) -> int"
    assert "sortOrder" in item


def test_handle_complete_missing_line_field_returns_empty_items():
    result = handle_complete({"source": "int g;\n", "column": 1})
    assert result == {"items": []}


def test_handle_complete_out_of_range_position_returns_empty_items():
    result = handle_complete({"source": "int g;\n", "line": 999, "column": 1})
    assert result == {"items": []}


# --- /api/hover ----------------------------------------------------------


def test_handle_hover_returns_signature_and_scope():
    result = handle_hover({"source": "int g = 1;\n", "line": 1, "column": 5})
    assert result["info"]["signature"] == "int"
    assert result["info"]["scopeDescription"] == "global scope"
    assert result["info"]["docComment"] is None


def test_handle_hover_missing_column_field_returns_none_info():
    result = handle_hover({"source": "int g;\n", "line": 1})
    assert result == {"info": None}


def test_handle_hover_no_symbol_at_position_returns_none_info():
    result = handle_hover({"source": "int g;\n\n", "line": 2, "column": 1})
    assert result == {"info": None}


# --- /api/cfg ----------------------------------------------------------


def test_handle_cfg_returns_svg_for_a_known_function():
    text = (
        "int factorial(int n) {\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}\n"
    )
    result = handle_cfg({"source": text, "function": "factorial"})
    assert result["svg"].startswith("<svg")
    assert result["svg"].rstrip().endswith("</svg>")


def test_handle_cfg_unknown_function_reports_error_not_a_500():
    result = handle_cfg({"source": "int f(void) { return 1; }\n", "function": "nope"})
    assert result["svg"] is None
    assert "nope" in result["error"]


def test_handle_cfg_prototype_reports_error_not_a_500():
    result = handle_cfg({"source": "int f(int n);\n", "function": "f"})
    assert result["svg"] is None
    assert "no body" in result["error"]


def test_handle_cfg_missing_function_field_reports_error():
    result = handle_cfg({"source": "int f(void) { return 1; }\n"})
    assert result["svg"] is None


# --- /api/callgraph ------------------------------------------------------


def test_handle_callgraph_returns_svg_and_dead_and_recursive_functions():
    text = "void helper(void) { }\nint f(void) { return f(); }\nint main(void) { return f(); }\n"
    result = handle_callgraph({"source": text})
    assert result["svg"].startswith("<svg")
    assert result["deadFunctions"] == ["helper"]
    assert result["recursiveFunctions"] == ["f"]
    assert {"caller": "main", "callee": "f"} in result["edges"]


def test_handle_callgraph_empty_source_does_not_crash():
    result = handle_callgraph({})
    assert result["svg"].startswith("<svg")
    assert result["deadFunctions"] == []


# --- /api/dead-code ------------------------------------------------------


def test_handle_dead_code_reports_all_categories():
    text = (
        "void helper(void) { }\n"
        "int foo(void) {\n"
        "    return 42;\n"
        "    return 0;\n"
        "}\n"
        "int main(void) { return foo(); }\n"
    )
    result = handle_dead_code({"source": text})
    assert result["unreachableFunctions"] == ["helper"]
    assert len(result["unreachableBlocks"]) == 1
    assert len(result["postJumpStatements"]) == 1


def test_handle_dead_code_clean_source_reports_nothing():
    result = handle_dead_code({"source": "int f(int n) { return n; }\n"})
    assert result["unreachableFunctions"] == []
    assert result["unreachableBlocks"] == []
    assert result["postJumpStatements"] == []
    assert result["unusedVariables"] == []
    assert result["deadAssignments"] == []


# --- dispatch_post routing, malformed input, errors ------------------------


def test_dispatch_post_unknown_route_is_404():
    payload, status = dispatch_post("/api/nonexistent", b"{}")
    assert status == 404


def test_dispatch_post_malformed_json_is_400():
    payload, status = dispatch_post("/api/analyze", b"{not valid json")
    assert status == 400
    assert "error" in payload


def test_dispatch_post_non_object_json_is_400():
    payload, status = dispatch_post("/api/analyze", b"[1, 2, 3]")
    assert status == 400


def test_dispatch_post_empty_body_uses_defaults():
    payload, status = dispatch_post("/api/analyze", b"")
    assert status == 200
    assert payload["symbols"]["kind"] == "global"


def test_dispatch_post_analyze_route_end_to_end():
    payload, status = dispatch_post("/api/analyze", b'{"source": "int g;\\n"}')
    assert status == 200
    assert payload["symbols"]["symbols"][0]["name"] == "g"


def test_dispatch_post_cfg_route_end_to_end():
    body = b'{"source": "int f(void) { return 1; }\\n", "function": "f"}'
    payload, status = dispatch_post("/api/cfg", body)
    assert status == 200
    assert payload["svg"].startswith("<svg")


def test_dispatch_post_callgraph_route_end_to_end():
    body = b'{"source": "int f(void) { return 1; }\\n"}'
    payload, status = dispatch_post("/api/callgraph", body)
    assert status == 200
    assert payload["svg"].startswith("<svg")


def test_dispatch_post_dead_code_route_end_to_end():
    body = b'{"source": "int f(int n) { return n; }\\n"}'
    payload, status = dispatch_post("/api/dead-code", body)
    assert status == 200
    assert payload["unreachableFunctions"] == []


def test_dispatch_post_handler_raising_is_a_500_not_a_crash(monkeypatch):
    """Rule 1 at the web layer: a handler that somehow raises must become
    a 500 JSON response, never an unhandled exception."""
    import clens.web.server as server_module

    def _broken(body):
        raise RuntimeError("boom")

    monkeypatch.setitem(server_module._POST_ROUTES, "/api/analyze", _broken)
    payload, status = dispatch_post("/api/analyze", b"{}")
    assert status == 500
    assert "boom" in payload["error"]


# --- live-socket tests: the actual ClensRequestHandler, not just the pure
# handler functions above ----------------------------------------------


@pytest.fixture
def running_server():
    server = HTTPServer(("127.0.0.1", 0), ClensRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_smoke_test_get_root(running_server):
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("GET", "/")
    response = conn.getresponse()
    body = response.read()
    assert response.status == 200
    assert b"<html" in body.lower()
    conn.close()


def test_theme_css_served_dynamically_matches_generate_theme_css(running_server):
    """/static/theme.css must be provably shared with core/theme.py (skill's
    own requirement), served live via generate_theme_css() rather than a
    committed file that could drift out of sync.
    """
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("GET", "/static/theme.css")
    response = conn.getresponse()
    body = response.read().decode("utf-8")
    assert response.status == 200
    assert body == generate_theme_css()
    for category in Category:
        assert THEME[category].hex_color in body
    conn.close()


def test_get_unknown_path_is_404(running_server):
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("GET", "/nonexistent")
    response = conn.getresponse()
    response.read()
    assert response.status == 404
    conn.close()


def test_get_static_missing_file_is_404(running_server):
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("GET", "/static/does-not-exist.js")
    response = conn.getresponse()
    response.read()
    assert response.status == 404
    conn.close()


def test_get_static_path_traversal_is_404(running_server):
    """`_serve_static` must not let '/static/../server.py' escape STATIC_DIR."""
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("GET", "/static/../server.py")
    response = conn.getresponse()
    response.read()
    assert response.status == 404
    conn.close()


def test_post_api_analyze_over_a_real_socket(running_server):
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    body = json.dumps({"source": "int g;\n"}).encode("utf-8")
    conn.request("POST", "/api/analyze", body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    payload = json.loads(response.read())
    assert response.status == 200
    assert payload["symbols"]["symbols"][0]["name"] == "g"
    conn.close()


def test_post_unknown_route_over_a_real_socket_is_404(running_server):
    conn = http.client.HTTPConnection("127.0.0.1", running_server, timeout=5)
    conn.request("POST", "/api/nonexistent", body=b"{}")
    response = conn.getresponse()
    response.read()
    assert response.status == 404
    conn.close()

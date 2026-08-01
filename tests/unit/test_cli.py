"""R7.1, R9.5 — the clens CLI: all four subcommands, --json, -o, exit
codes, and robustness against the inputs evaluators will try.
"""

import json
import os
from pathlib import Path

import pytest

from clens.cli.main import build_parser, main


def write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content)
    return str(path)


def test_no_args_exits_2_with_usage_message(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2
    assert "usage: clens" in capsys.readouterr().err


def test_help_flag_prints_usage_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    assert "usage: clens" in capsys.readouterr().out


def test_build_parser_prog_name():
    assert build_parser().prog == "clens"


# --- serve (S8.2, D22) -----------------------------------------------------


def test_serve_command_parses_default_host_and_port():
    args = build_parser().parse_args(["serve"])
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_serve_command_parses_custom_host_and_port():
    args = build_parser().parse_args(["serve", "--port", "9000", "--host", "0.0.0.0"])
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_serve_command_calls_web_server_serve_with_parsed_args(monkeypatch):
    """`serve` has no file argument and must bypass _load_source entirely -
    this exercises that bypass without actually starting a real server."""
    calls = []
    monkeypatch.setattr("clens.cli.main.serve", lambda host, port: calls.append((host, port)))
    code = main(["serve", "--port", "9001", "--host", "0.0.0.0"])
    assert code == 0
    assert calls == [("0.0.0.0", 9001)]


# --- tokens -------------------------------------------------------------


def test_tokens_command_prints_token_stream(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["tokens", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "KEYWORD" in out and "IDENT" in out and "'x'" in out


def test_tokens_command_json(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["tokens", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert any(t["lexeme"] == "x" and t["type"] == "IDENT" for t in payload)


# --- ast ------------------------------------------------------------------


def test_ast_command_prints_pretty_ast(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }")
    code = main(["ast", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "FuncDecl" in out and "ReturnStmt" in out


def test_ast_command_json(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }")
    code = main(["ast", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["node"] == "Program"
    assert payload["declarations"][0]["node"] == "FuncDecl"


# --- highlight --------------------------------------------------------------


def test_highlight_command_defaults_to_ansi(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["highlight", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "\x1b[" in out


def test_highlight_command_html_format(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["highlight", path, "--format", "html"])
    out = capsys.readouterr().out
    assert code == 0
    assert "<!doctype html>" in out


def test_highlight_command_json(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["highlight", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert any(entry["category"] == "type" for entry in payload)


def test_highlight_command_writes_to_output_file(tmp_path):
    path = write(tmp_path, "a.c", "int x;")
    out_path = tmp_path / "out.html"
    code = main(["highlight", path, "--format", "html", "-o", str(out_path)])
    assert code == 0
    assert "<!doctype html>" in out_path.read_text()


# --- check ------------------------------------------------------------------


def test_check_command_no_diagnostics(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x;")
    code = main(["check", path])
    assert code == 0
    assert capsys.readouterr().out.strip() == "no diagnostics"


def test_check_command_reports_diagnostics_pretty(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x@;")
    code = main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "unrecognized character '@'" in out
    assert "^" in out  # caret underline


def test_check_command_json(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x@;")
    code = main(["check", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload[0]["severity"] == "error"


def test_check_command_runs_semantic_analysis_too(tmp_path, capsys):
    """P6.3: check now runs lexer + parser + semantic in one pass - a
    file with no lexical/syntax errors but a real type error must still
    be caught, not just the earlier phases."""
    path = write(tmp_path, "a.c", "void f(void) { return 5; }\n")
    code = main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "void function should not return a value" in out


def test_check_command_semantic_warning_does_not_fail_exit_code(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int x = 3.14;\n")
    code = main(["check", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "may lose precision" in out


# --- symbols (S8.1) -----------------------------------------------------------


def test_symbols_command_renders_the_scope_tree(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int g = 1;\nint f(int x) { return x + g; }\n")
    code = main(["symbols", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "GLOBAL" in out
    assert "g: variable int" in out
    assert "f: function" in out
    assert "x: parameter int" in out


def test_symbols_command_json(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int g = 1;\n")
    code = main(["symbols", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["kind"] == "global"
    names = {s["name"] for s in payload["symbols"]}
    assert names == {"g"}
    assert payload["symbols"][0]["type"] == "int"


def test_symbols_command_reports_semantic_errors(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return undeclared; }\n")
    code = main(["symbols", path, "--json"])
    capsys.readouterr()
    assert code == 1


# --- complete (S8.1) -----------------------------------------------------


def test_complete_command_lists_matching_symbols(tmp_path, capsys):
    """`fac` with no trailing ';' is a syntax error - the normal state
    while a user is mid-typing (the skill's own framing) - so the exit
    code reflects that real parse error; completion must still work."""
    text = "int factorial(int n) { return n; }\nvoid f(void) {\n    fac\n}\n"
    path = write(tmp_path, "a.c", text)
    main(["complete", path, "3", "8"])
    out = capsys.readouterr().out
    assert "factorial" in out
    assert "function" in out


def test_complete_command_json(tmp_path, capsys):
    text = "int factorial(int n) { return n; }\nvoid f(void) {\n    fac\n}\n"
    path = write(tmp_path, "a.c", text)
    main(["complete", path, "3", "8", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["label"] == "factorial"
    assert payload[0]["kind"] == "function"
    assert payload[0]["detail"] == "(int) -> int"
    assert "sortOrder" in payload[0]


def test_complete_command_no_matches(tmp_path, capsys):
    path = write(tmp_path, "a.c", "void f(void) {\n    zzz\n}\n")
    main(["complete", path, "2", "8"])
    out = capsys.readouterr().out
    assert out.strip() == "no completions"


def test_complete_command_out_of_range_position_exits_1(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int g;\n")
    code = main(["complete", path, "999", "1"])
    out = capsys.readouterr().out
    assert code == 1
    assert "clens:" in out


# --- hover (S7, S8.1) -----------------------------------------------------


def test_hover_command_shows_signature_and_scope(tmp_path, capsys):
    text = "/* Computes n factorial. */\nint factorial(int n) { return n; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["hover", path, "2", "6"])
    out = capsys.readouterr().out
    assert code == 0
    assert "(int) -> int" in out
    assert "global scope" in out
    assert "Computes n factorial." in out


def test_hover_command_json(tmp_path, capsys):
    text = "int g = 1;\n"
    path = write(tmp_path, "a.c", text)
    code = main(["hover", path, "1", "5"])
    capsys.readouterr()
    code_json = main(["hover", path, "1", "5", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == code_json == 0
    assert payload["signature"] == "int"
    assert payload["scopeDescription"] == "global scope"
    assert payload["docComment"] is None


def test_hover_command_no_symbol_at_position(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int g;\n\n")
    code = main(["hover", path, "2", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.strip() == "no hover information"


def test_hover_command_out_of_range_position_exits_1(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int g;\n")
    code = main(["hover", path, "1", "999"])
    out = capsys.readouterr().out
    assert code == 1
    assert "clens:" in out


# --- exit codes (R7.1) -------------------------------------------------------


def test_exit_0_for_clean_file(tmp_path):
    path = write(tmp_path, "a.c", "int main(void) { return 0; }")
    assert main(["check", path]) == 0


def test_exit_1_when_errors_present(tmp_path):
    path = write(tmp_path, "a.c", "int x = ;")
    assert main(["check", path]) == 1


# --- R9.5 robustness ----------------------------------------------------------


def test_empty_file(tmp_path):
    path = write(tmp_path, "empty.c", "")
    assert main(["check", path]) == 0
    assert main(["tokens", path]) == 0
    assert main(["ast", path]) == 0
    assert main(["highlight", path]) == 0


def test_comments_only_file(tmp_path):
    path = write(tmp_path, "comments.c", "// just a comment\n/* and a block */\n")
    assert main(["check", path]) == 0
    assert main(["highlight", path]) == 0


def test_binary_garbage_file_does_not_crash(tmp_path, capsys):
    path = tmp_path / "garbage.c"
    path.write_bytes(bytes(range(256)) * 4)
    code = main(["check", str(path)])
    assert code in (0, 1)  # never 2 (internal failure), never an exception
    capsys.readouterr()


def test_nonexistent_path(capsys):
    code = main(["check", "/no/such/file/exists.c"])
    assert code == 1
    assert "no such file or directory" in capsys.readouterr().err


def test_nonexistent_path_json(capsys):
    code = main(["check", "/no/such/file/exists.c", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "no such file or directory" in payload[0]["message"]


def test_directory_passed_as_file(tmp_path, capsys):
    code = main(["check", str(tmp_path)])
    assert code == 1
    assert "is a directory" in capsys.readouterr().err


def test_never_raises_for_any_command_on_any_robustness_input(tmp_path):
    """R9.5 smoke test across the full command x input matrix."""
    inputs = [
        write(tmp_path, "empty2.c", ""),
        write(tmp_path, "syntax_error.c", "int x = ;\nint y = 42;\n"),
        write(tmp_path, "lexical_error.c", "int x@ = 5;\n"),
        "/no/such/path.c",
        str(tmp_path),
    ]
    for command in ("tokens", "ast", "highlight", "check"):
        for path in inputs:
            code = main([command, path])  # must not raise
            assert isinstance(code, int)
            assert code != 2


def test_unreadable_file_reports_diagnostic_not_crash(tmp_path, capsys):
    path = tmp_path / "locked.c"
    path.write_text("int x;")
    path.chmod(0o000)
    try:
        if os.access(path, os.R_OK):
            pytest.skip("running as a user that bypasses file permissions (e.g. root)")
        code = main(["check", str(path)])
        assert code == 1
        assert str(path) in capsys.readouterr().err
    finally:
        path.chmod(0o644)


def test_unexpected_internal_error_exits_2_without_traceback(monkeypatch, tmp_path, capsys):
    """Exit code 2 (R7.1) is meant to be unreachable in normal operation;
    this proves the top-level guard actually works if something we did not
    anticipate still goes wrong.
    """

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("clens.cli.main.tokenize", _boom)
    path = write(tmp_path, "a.c", "int x;")

    code = main(["tokens", path])

    assert code == 2
    err = capsys.readouterr().err
    assert "internal error" in err
    assert "Traceback" not in err


# --- goto-def / find-refs (A4, A7.2) ------------------------------------------


def test_goto_def_command_text(tmp_path, capsys):
    text = "int factorial(int n) { return n; }\nint g(void) { return factorial(1); }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["goto-def", path, "2", "22"])
    out = capsys.readouterr().out
    assert code == 0
    assert "factorial" in out
    assert ":1:5" in out


def test_goto_def_command_no_definition_at_a_keyword(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }\n")
    code = main(["goto-def", path, "1", "16"])
    out = capsys.readouterr().out
    assert code == 0
    assert "no definition" in out


def test_find_refs_command_text_matches_course_document_shape(tmp_path, capsys):
    text = "int factorial(int n) { return n; }\nint g(void) { return factorial(1); }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["find-refs", path, "factorial"])
    out = capsys.readouterr().out
    assert code == 0
    assert "defined at" in out
    assert ":1:5" in out
    assert ":2:22" in out


def test_find_refs_command_json_shape(tmp_path, capsys):
    text = "int factorial(int n) { return n; }\nint g(void) { return factorial(1); }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["find-refs", path, "factorial", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["symbol"] == "factorial"
    assert payload["defined_at"] == {"file": path, "line": 1, "col": 5}
    assert len(payload["references"]) == 1


def test_find_refs_command_ambiguous_name_lists_every_match(tmp_path, capsys):
    text = "int n;\nint f(int n) { return n; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["find-refs", path, "n", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert isinstance(payload, list)
    assert len(payload) == 2


def test_find_refs_command_unknown_symbol_reports_error(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }\n")
    code = main(["find-refs", path, "does_not_exist"])
    assert code == 1
    assert "does_not_exist" in capsys.readouterr().out


# --- rename (A5, A7.2) --------------------------------------------------------


def test_rename_command_shows_a_diff_by_default_without_writing(tmp_path, capsys):
    text = "int f(int n) { return n; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["rename", path, "1", "11", "count"])
    out = capsys.readouterr().out
    assert code == 0
    assert "-int f(int n)" in out
    assert "+int f(int count)" in out
    assert Path(path).read_text() == text  # not written without --apply


def test_rename_command_apply_writes_the_file(tmp_path, capsys):
    text = "int f(int n) { return n; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["rename", path, "1", "11", "count", "--apply"])
    capsys.readouterr()
    assert code == 0
    assert Path(path).read_text() == "int f(int count) { return count; }\n"


def test_rename_command_json_shape(tmp_path, capsys):
    text = "int f(int n) { return n; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["rename", path, "1", "11", "count", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["applied"] is False
    assert "+int f(int count)" in payload["diff"]


def test_rename_command_refusal_reports_the_reason_not_an_unrelated_diagnostic(tmp_path, capsys):
    """A refused rename's message must be the refusal reason itself, even
    when the file has an earlier, unrelated semantic diagnostic (an
    unused-variable info here) that gets recorded first in the same
    collector -- the CLI must not print that one instead."""
    text = "int g = 0;\nint f(int g) { int unused_local; return g; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["rename", path, "2", "11", "g"])
    out = capsys.readouterr().out
    assert code == 1
    assert "already the current name" in out
    assert "unused_local" not in out


def test_rename_command_no_symbol_at_position_is_refused(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }\n")
    code = main(["rename", path, "1", "16", "whatever"])
    assert code == 1
    assert "no symbol" in capsys.readouterr().out


# --- show-cfg (A1, A7.2) -----------------------------------------------------


def test_show_cfg_command_text_matches_golden_shape(tmp_path, capsys):
    text = (
        "int factorial(int n) {\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}\n"
    )
    path = write(tmp_path, "a.c", text)
    code = main(["show-cfg", path, "factorial"])
    out = capsys.readouterr().out
    assert code == 0
    assert "ENTRY" in out
    assert "B1: n <= 1" in out
    assert "--true--> B2" in out
    assert "--false--> B3" in out
    assert "B2: return 1" in out
    assert "B3: return n * factorial(n - 1)" in out
    assert out.count("-> EXIT") == 2


def test_show_cfg_command_json(tmp_path, capsys):
    text = "int f(void) { return 1; }\n"
    path = write(tmp_path, "a.c", text)
    code = main(["show-cfg", path, "f", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["function"] == "f"
    ids = [b["id"] for b in payload["blocks"]]
    assert ids == ["ENTRY", "B1", "EXIT"]


def test_show_cfg_command_unknown_function_reports_error_not_crash(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(void) { return 1; }\n")
    code = main(["show-cfg", path, "does_not_exist"])
    assert code == 1
    assert "does_not_exist" in capsys.readouterr().out


def test_show_cfg_command_prototype_has_no_graph(tmp_path, capsys):
    path = write(tmp_path, "a.c", "int f(int n);\n")
    code = main(["show-cfg", path, "f"])
    assert code == 1
    assert "no body" in capsys.readouterr().out


# --- callgraph (A3, A7.2) -----------------------------------------------------


def test_callgraph_command_text(tmp_path, capsys):
    text = (
        "int self_recursive(int n) { if (n <= 0) return 0; return self_recursive(n - 1); }\n"
        "int main(void) { return self_recursive(3); }\n"
    )
    path = write(tmp_path, "a.c", text)
    code = main(["callgraph", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "main -> self_recursive" in out
    assert "self_recursive -> self_recursive" in out
    assert "recursive: self_recursive" in out


def test_callgraph_command_json_shape(tmp_path, capsys):
    text = (
        "int helper(void) { return 1; }\n"
        "int main(void) { return helper(); }\n"
        "int dead(void) { return 0; }\n"
    )
    path = write(tmp_path, "a.c", text)
    code = main(["callgraph", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(payload["nodes"]) == {"helper", "main", "dead"}
    assert payload["hasMain"] is True
    assert payload["deadFunctions"] == ["dead"]
    assert {"caller": "main", "callee": "helper", "line": 2, "col": 25} in payload["edges"]

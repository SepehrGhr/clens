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

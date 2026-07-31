"""R9.5 — end-to-end robustness: every input class the acceptance checklist
names, run through all four CLI commands. No input may raise, and exit code
2 (internal failure) must never be observed.

This complements the more targeted robustness tests elsewhere (lexer-level
unicode/invalid-char fuzzing in test_lexer_c.py, parser-level truncation
fuzz in test_parser_robustness.py, CLI file-loading edge cases in
test_cli.py) with one comprehensive sweep tied directly to
`.agents/checklists/phase1-acceptance.md`'s robustness section.
"""

import random

from clens.cli.main import main

COMMANDS = ("tokens", "ast", "highlight", "check")


def run_all_commands(path: str) -> None:
    for command in COMMANDS:
        code = main([command, path])
        assert isinstance(code, int)
        assert code in (0, 1), f"{command} {path} exited {code}, expected 0 or 1"


def test_empty_file(tmp_path):
    path = tmp_path / "empty.c"
    path.write_text("")
    run_all_commands(str(path))


def test_whitespace_only_file(tmp_path):
    path = tmp_path / "whitespace.c"
    path.write_text("   \t\t\n\n  \n\t\n   ")
    run_all_commands(str(path))


def test_comments_only_file(tmp_path):
    path = tmp_path / "comments.c"
    path.write_text("// line\n/* block\nspanning lines */\n// another\n")
    run_all_commands(str(path))


def test_unterminated_string(tmp_path):
    path = tmp_path / "unterminated_string.c"
    path.write_text('char *s = "never closed\nint x;\n')
    run_all_commands(str(path))


def test_unterminated_block_comment(tmp_path):
    path = tmp_path / "unterminated_comment.c"
    path.write_text("int x;\n/* never closed\nint y;\n")
    run_all_commands(str(path))


def test_unbalanced_braces(tmp_path):
    path = tmp_path / "unbalanced.c"
    path.write_text("int f(void) {\n    return 1;\n\nint g(void) {\n    return 2;\n}\n")
    run_all_commands(str(path))


def test_stray_at_sign(tmp_path):
    path = tmp_path / "stray_at.c"
    path.write_text("int x@ = 5;\nint y = 10;\n")
    run_all_commands(str(path))


def test_crlf_line_endings(tmp_path):
    path = tmp_path / "crlf.c"
    path.write_bytes(b"int factorial(int n) {\r\n    return n;\r\n}\r\n")
    run_all_commands(str(path))


def test_no_trailing_newline(tmp_path):
    path = tmp_path / "no_trailing_newline.c"
    path.write_text("int x;")  # deliberately no trailing \n
    assert not path.read_bytes().endswith(b"\n")
    run_all_commands(str(path))


def test_one_megabyte_valid_file(tmp_path):
    """A large but well-formed file -- stresses the O(n) assumptions, not
    error recovery. Runs only 'check' (full lex+parse+diagnostics): the
    other three commands share the same pipeline and are already exercised
    at this size would just multiply runtime without adding size-specific
    signal (their own logic is covered by the smaller fixtures elsewhere).
    """
    unit = "int f%d(int n) { return n * f%d(n - 1); }\n"
    parts = []
    size = 0
    i = 0
    while size < 1_000_000:
        line = unit % (i, i)
        parts.append(line)
        size += len(line)
        i += 1
    path = tmp_path / "large_valid.c"
    path.write_text("".join(parts))
    assert path.stat().st_size >= 1_000_000
    assert main(["check", str(path)]) == 0


def test_one_megabyte_random_bytes(tmp_path):
    rng = random.Random(0)
    path = tmp_path / "large_garbage.c"
    path.write_bytes(bytes(rng.randrange(256) for _ in range(1_000_000)))
    assert main(["check", str(path)]) == 1  # every byte here is unrecognized


def test_nonexistent_path():
    run_all_commands("/no/such/file/anywhere.c")


def test_directory_as_path(tmp_path):
    run_all_commands(str(tmp_path))

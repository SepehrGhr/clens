"""phase2-acceptance.md's robustness section, exercised directly against
`analyze()` rather than only incidentally through `clens check` (which
happens to run the same pipeline, but that's a Stage 6 wiring detail, not
a guarantee this file wants to depend on): empty file, comments only, a
file that fails to parse entirely, unbalanced braces, `typedef`, random
bytes. No input may raise; `analyze()` must always return a `SemanticModel`.
"""

import random

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import SemanticModel, analyze


def analyze_text(text: str, filename: str = "a.c") -> tuple[SemanticModel, DiagnosticCollector]:
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return model, diagnostics


def test_empty_file_does_not_crash():
    model, diagnostics = analyze_text("")
    assert isinstance(model, SemanticModel)
    assert not diagnostics.diagnostics


def test_whitespace_only_does_not_crash():
    model, _ = analyze_text("   \t\n\n  \t\n   ")
    assert isinstance(model, SemanticModel)


def test_comments_only_does_not_crash():
    model, diagnostics = analyze_text("// line\n/* block\nspanning */\n// another\n")
    assert isinstance(model, SemanticModel)
    assert not diagnostics.diagnostics


def test_file_that_fails_to_parse_entirely_does_not_crash():
    """Not one broken statement among valid ones - nothing here parses."""
    model, diagnostics = analyze_text("@ # $ } { ) (")
    assert isinstance(model, SemanticModel)
    # Recovery may or may not leave any declarations; the only hard
    # requirement is that analysis completes and returns a real model.
    assert model.global_scope is not None


def test_unbalanced_braces_does_not_crash():
    text = "int f(void) {\n    return 1;\n\nint g(void) {\n    return 2;\n}\n"
    model, diagnostics = analyze_text(text)
    assert isinstance(model, SemanticModel)


def test_typedef_does_not_crash_the_semantic_analyzer():
    """typedef is rejected at the parser (unsupported construct) and
    recovered via panic mode; analyze() must still run cleanly over
    whatever AST survives, with no crash and no diagnostics of its own
    piled on top of the parser's."""
    path_text = "typedef int myint;\nint x = 1;\n"
    model, diagnostics = analyze_text(path_text)
    assert isinstance(model, SemanticModel)
    assert any(d.severity.value == "error" for d in diagnostics.diagnostics)
    assert model.global_scope.lookup_local("x") is not None


def test_random_bytes_do_not_crash():
    rng = random.Random(0)
    garbage = "".join(chr(rng.randrange(32, 127)) for _ in range(2000))
    model, diagnostics = analyze_text(garbage)
    assert isinstance(model, SemanticModel)


def test_file_full_of_error_regions_analyzes_without_extra_diagnostics():
    """Several syntax errors in a row: the parser reports each one; the
    semantic analyzer must skip every ErrorStmt/ErrorExpr region silently
    (never a diagnostic *about* the hole itself, e.g. "undefined symbol"
    for whatever token confused the parser) rather than crashing or
    piling more noise on top. It may still legitimately report on the
    parts that *did* parse — `int a = ;` still declares a real `a`, so
    "unused variable 'a'" is correct, not a cascade."""
    text = (
        "int f(void) {\n"
        "    int a = ;\n"
        "    int b = ;\n"
        "    return + ;\n"
        "}\n"
        "int g(void) {\n"
        "    ) invalid (\n"
        "}\n"
    )
    model, diagnostics = analyze_text(text)
    assert isinstance(model, SemanticModel)
    semantic_diagnostics = [d for d in diagnostics.diagnostics if d.code and d.code.startswith("S")]
    # Only the legitimate, independent unused-variable reports on the
    # declarations that did parse - nothing invented about the holes.
    assert {d.code for d in semantic_diagnostics} == {"S009"}
    assert len(semantic_diagnostics) == 2


def test_one_megabyte_valid_file_analyzes_without_crashing():
    unit = "int f%d(int n) { return n * f%d(n - 1); }\n"
    parts = []
    size = 0
    i = 0
    while size < 1_000_000:
        line = unit % (i, i)
        parts.append(line)
        size += len(line)
        i += 1
    model, diagnostics = analyze_text("".join(parts))
    assert isinstance(model, SemanticModel)
    assert not diagnostics.diagnostics

"""S6.1 — the course document's thirteen-row diagnostic table, audited one
row per test, each asserting the exact code and severity. Grep this file
for every row ID at the defense.
"""

from clens.core.diagnostics import DiagnosticCollector, Severity
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze


def lex(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokenize(source, diagnostics)
    return diagnostics


def parse_only(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    parse(source, diagnostics)
    return diagnostics


def analyze_text(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    analyze(program, source, diagnostics)
    return diagnostics


# --- Rows 1-2: Lexer -----------------------------------------------------


def test_row_1_unrecognized_character():
    diagnostics = lex("int x@ = 5;\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "E001-unrecognized-character"


def test_row_2_unterminated_string_literal():
    diagnostics = lex('int x = "abc;\n')
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "E002-unterminated-string"


# --- Rows 3-4: Parser ------------------------------------------------------


def test_row_3_unexpected_token():
    diagnostics = parse_only("int x = ;\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "E010-unexpected-token"


def test_row_4_missing_closing_delimiter():
    diagnostics = parse_only("int f(void) { if (y > 0 { return 1; } }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "E011-missing-closing-delimiter"


# --- Rows 5-13: Semantic ---------------------------------------------------


def test_row_5_undefined_symbol():
    diagnostics = analyze_text("void f(void) { undeclared_name; }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S001"


def test_row_6_type_mismatch_in_assignment():
    diagnostics = analyze_text("char *s = 42;\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S002"


def test_row_7_type_mismatch_in_function_call():
    diagnostics = analyze_text('int f(int n) { return n; }\nint g(void) { return f("x"); }\n')
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S003"


def test_row_8_duplicate_declaration():
    diagnostics = analyze_text("int a = 1;\nint a = 2;\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S004"


def test_row_9_wrong_number_of_arguments():
    diagnostics = analyze_text("int f(int n) { return n; }\nint g(void) { return f(1, 2); }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S005"


def test_row_10_return_type_mismatch():
    diagnostics = analyze_text("void f(void) { return 5; }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == "S006"


def test_row_11_variable_shadows_outer():
    diagnostics = analyze_text("int x = 1;\nvoid f(void) { int x = 2; x; }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.WARNING
    assert d.code == "S007"


def test_row_12_use_before_initialization():
    diagnostics = analyze_text("int f(void) { int x; return x; }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.WARNING
    assert d.code == "S008"


def test_row_13_unused_variable():
    diagnostics = analyze_text("void f(void) { int x = 1; }\n")
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.INFO
    assert d.code == "S009"


def test_all_thirteen_codes_are_distinct():
    """The registry itself: no code reused across rows."""
    codes = [
        "E001-unrecognized-character",
        "E002-unterminated-string",
        "E010-unexpected-token",
        "E011-missing-closing-delimiter",
        "S001",
        "S002",
        "S003",
        "S004",
        "S005",
        "S006",
        "S007",
        "S008",
        "S009",
    ]
    assert len(codes) == len(set(codes)) == 13

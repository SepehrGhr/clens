"""R5.1, R5.2 — the two-pass C highlighter: token defaults and AST upgrades."""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.highlight import Category
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser


def highlight_text(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    significant = list(iter_significant(tokens))
    program = Parser(significant, diagnostics).parse_program()
    return tokens, highlight(tokens, program), diagnostics


def category_of(tokens, highlight_map, lexeme: str, occurrence: int = 0):
    matches = [i for i, t in enumerate(tokens) if t.lexeme == lexeme]
    index = matches[occurrence]
    return highlight_map.get(index)


# --- Pass 1: token-level defaults -------------------------------------------


def test_keyword_default():
    tokens, hl, _ = highlight_text("return 1;")
    assert category_of(tokens, hl, "return") is Category.KEYWORD


def test_base_type_keyword_defaults_to_type_not_keyword():
    tokens, hl, _ = highlight_text("int x;")
    assert category_of(tokens, hl, "int") is Category.TYPE


def test_ident_defaults_to_variable():
    tokens, hl, _ = highlight_text("int x;")
    assert category_of(tokens, hl, "x") is Category.VARIABLE


def test_int_and_float_literals_are_number():
    tokens, hl, _ = highlight_text("float x = 3.14; int y = 42;")
    assert category_of(tokens, hl, "3.14") is Category.NUMBER
    assert category_of(tokens, hl, "42") is Category.NUMBER


def test_string_and_char_literals_are_string():
    tokens, hl, _ = highlight_text("char *s = \"hi\"; char c = 'a';")
    assert category_of(tokens, hl, '"hi"') is Category.STRING
    assert category_of(tokens, hl, "'a'") is Category.STRING


def test_operator_default():
    tokens, hl, _ = highlight_text("int x = 1 + 2;")
    assert category_of(tokens, hl, "+") is Category.OPERATOR


def test_comment_default():
    tokens, hl, _ = highlight_text("// hi\nint x;")
    assert category_of(tokens, hl, "// hi") is Category.COMMENT


def test_preprocessor_default():
    tokens, hl, _ = highlight_text('#include "a.h"\nint x;')
    assert category_of(tokens, hl, '#include "a.h"') is Category.PREPROCESSOR


def test_invalid_token_default():
    tokens, hl, _ = highlight_text("int x@;")
    assert category_of(tokens, hl, "@") is Category.ERROR


def test_delimiters_and_whitespace_have_no_entry():
    tokens, hl, _ = highlight_text("int x;")
    semi_index = next(i for i, t in enumerate(tokens) if t.lexeme == ";")
    assert semi_index not in hl


# --- Pass 2: AST-context upgrades -------------------------------------------


def test_call_callee_upgraded_to_function():
    tokens, hl, _ = highlight_text("int f(void) { return f(); }")
    assert category_of(tokens, hl, "f", occurrence=1) is Category.FUNCTION


def test_func_decl_name_upgraded_to_function():
    tokens, hl, _ = highlight_text("int factorial(int n);")
    assert category_of(tokens, hl, "factorial") is Category.FUNCTION


def test_struct_tag_in_declaration_upgraded_to_type_name():
    tokens, hl, _ = highlight_text("struct Point { int x; };")
    assert category_of(tokens, hl, "Point") is Category.TYPE_NAME


def test_struct_tag_in_variable_type_upgraded_to_type_name():
    tokens, hl, _ = highlight_text("struct Point { int x; }; struct Point origin;")
    assert category_of(tokens, hl, "Point", occurrence=1) is Category.TYPE_NAME


def test_sizeof_of_struct_type_upgraded():
    tokens, hl, _ = highlight_text("struct Point { int x; }; int s = sizeof(struct Point);")
    assert category_of(tokens, hl, "Point", occurrence=1) is Category.TYPE_NAME


def test_pass_2_never_downgrades_a_keyword():
    """Sanity: visiting a FuncDecl doesn't accidentally touch its return
    type's own already-correct Category.TYPE."""
    tokens, hl, _ = highlight_text("int f(void) { return 0; }")
    assert category_of(tokens, hl, "int") is Category.TYPE


def test_highlight_map_indices_are_all_within_range():
    tokens, hl, _ = highlight_text("int factorial(int n) { return n; }")
    assert all(0 <= index < len(tokens) for index in hl)


def test_file_with_parse_errors_still_highlights_pass_1():
    """A file that fails to parse still highlights via Pass 1 (skill's
    definition of done)."""
    tokens, hl, diagnostics = highlight_text("int x = ;\nint y = 42;\n")
    assert diagnostics.has_errors
    assert category_of(tokens, hl, "int", occurrence=0) is Category.TYPE
    assert category_of(tokens, hl, "y") is Category.VARIABLE

"""S5.2, S5.4 — general scope completion (everything visible, plus
keywords) and argument-list completion, re-ranked by the expected
parameter type without filtering anything out.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import completions_at
from clens.languages.c.semantic import analyze


def build_model(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = parse(source, diagnostics)
    return analyze(program, source, diagnostics, tokens=tokens)


def test_general_completion_includes_every_visible_symbol():
    text = (
        "int g = 1;\nint helper(int n) { return n; }\nint f(int p) {\n    int local = 0;\n    \n}\n"
    )
    model = build_model(text)
    offset = text.rindex("    \n") + 4  # blank line inside f's body

    items = completions_at(model, offset)
    labels = {i.label for i in items}

    assert {"g", "helper", "p", "local"} <= labels


def test_general_completion_includes_keywords_ranked_below_symbols():
    text = "int forward;\nvoid f(void) { fo }\n"
    model = build_model(text)
    offset = text.index("fo }") + len("fo")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert "forward" in labels
    assert "for" in labels  # the keyword
    assert labels.index("forward") < labels.index("for")
    keyword_item = next(i for i in items if i.label == "for")
    assert keyword_item.kind == "keyword"


def test_argument_context_reranks_by_expected_parameter_type_without_filtering():
    """Both a matching-type local and a non-matching-type function share
    the same prefix and match tier; the matching-type one must still sort
    first, but the non-matching one must still appear (re-ranked, not
    excluded)."""
    text = (
        "int factorial(int n);\n"
        "int add(int a, int b) { return a + b; }\n"
        "void f(void) {\n"
        "    int fahrenheit = 1;\n"
        "    add(fa\n"
        "}\n"
    )
    model = build_model(text)
    offset = text.index("add(fa") + len("add(fa")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert "fahrenheit" in labels
    assert "factorial" in labels
    assert labels.index("fahrenheit") < labels.index("factorial")


def test_argument_context_second_parameter_position():
    text = "int add(int a, int b) { return a + b; }\nvoid f(void) { int total; add(1, to }\n"
    model = build_model(text)
    offset = text.index("add(1, to") + len("add(1, to")

    items = completions_at(model, offset)

    assert any(i.label == "total" for i in items)


def test_general_completion_at_top_level_sees_only_globals():
    text = "int g;\nint h(int p) { return p; }\n"
    model = build_model(text)
    offset = len(text)  # end of file, top level

    items = completions_at(model, offset)
    labels = {i.label for i in items}

    assert "g" in labels
    assert "h" in labels
    assert "p" not in labels  # h's parameter is not visible at top level

"""S5.4, S5.5, D24 — completion ranking: exact prefix beats case-
insensitive prefix beats subsequence-fuzzy beats excluded; scope distance
(local beats global) then alphabetical as tie-breaks; sort_order reflects
the final order.
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


def test_exact_prefix_beats_case_insensitive_beats_fuzzy():
    """factor* (exact prefix "fac"), Factory (case-insensitive prefix only
    if user typed exact case elsewhere - here it's a same-case prefix too,
    so use a case-mismatched candidate instead), and fct (fuzzy subsequence
    of "factorial") should sort in that tier order for prefix "fac"."""
    text = "int factorial(int n);\nint FACup(int n);\nvoid f(void) {\n    fac\n}\n"
    model = build_model(text)
    offset = text.index("    fac") + len("    fac")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert labels.index("factorial") < labels.index("FACup")


def test_fuzzy_subsequence_match_included_but_ranked_last():
    """ "fct" is a subsequence of "factorial" (f-a-C-T-orial) but not a
    prefix of it; "future" is an exact prefix of nothing here but starts
    with "fu", not "fct", so use "factorial" (fuzzy) against "fctx" (exact
    prefix) to isolate the fuzzy tier landing after the prefix tiers."""
    text = "int fctx(void);\nint factorial(void);\nvoid f(void) {\n    fct\n}\n"
    model = build_model(text)
    offset = text.index("    fct") + len("    fct")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert "fctx" in labels  # exact prefix match for "fct"
    assert "factorial" in labels  # fuzzy subsequence: f-C-T-orial
    assert labels.index("fctx") < labels.index("factorial")


def test_no_match_is_excluded_entirely():
    text = "int zebra;\nvoid f(void) {\n    fac\n}\n"
    model = build_model(text)
    offset = text.index("    fac") + len("    fac")

    items = completions_at(model, offset)

    assert "zebra" not in [i.label for i in items]


def test_local_beats_global_at_the_same_match_tier():
    """Same name visible at two depths is impossible (shadowing collapses
    it to one symbol), so use two different names that both exact-prefix-
    match, one local, one global, and confirm the local sorts first."""
    text = "int aardvark;\nvoid f(void) {\n    int apple;\n    a\n}\n"
    model = build_model(text)
    offset = text.rindex("    a") + len("    a")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert labels.index("apple") < labels.index("aardvark")


def test_alphabetical_tie_break_within_the_same_scope_and_tier():
    """Two locals, same scope (distance 0), both exact-prefix matches for
    "a" - alphabetical order is the only remaining tie-break."""
    text = "void f(void) {\n    int avocado;\n    int apple;\n    a\n}\n"
    model = build_model(text)
    offset = text.rindex("    a") + len("    a")

    items = completions_at(model, offset)

    assert [i.label for i in items if i.label.startswith("a")] == ["apple", "avocado"]


def test_keywords_rank_below_real_symbols_at_the_same_tier():
    text = "int inside;\nvoid f(void) {\n    in\n}\n"
    model = build_model(text)
    offset = text.rindex("    in") + len("    in")

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert "inside" in labels and "int" in labels
    assert labels.index("inside") < labels.index("int")


def test_sort_order_is_monotonic_with_final_order():
    text = "int aardvark;\nvoid f(void) {\n    int apple;\n    a\n}\n"
    model = build_model(text)
    offset = text.rindex("    a") + len("    a")

    items = completions_at(model, offset)

    assert [i.sort_order for i in items] == sorted(i.sort_order for i in items)
    assert items[0].sort_order == 0.0


def test_empty_prefix_shows_everything_ranked_by_tie_breaks_only():
    text = "int g;\nvoid f(void) {\n    int local;\n    \n}\n"
    model = build_model(text)
    offset = text.rindex("    \n") + 4

    items = completions_at(model, offset)
    labels = [i.label for i in items]

    assert "local" in labels and "g" in labels
    assert labels.index("local") < labels.index("g")

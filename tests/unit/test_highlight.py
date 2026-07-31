"""R5.2 — the Category enum has exactly the twelve required categories."""

from clens.core.highlight import Category


def test_all_twelve_r5_2_categories_present():
    required = {
        "keyword",
        "type",
        "variable",
        "function",
        "type_name",
        "number",
        "string",
        "boolean",
        "operator",
        "comment",
        "preprocessor",
        "error",
    }
    assert required == {member.value for member in Category}

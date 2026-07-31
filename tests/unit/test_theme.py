"""D10 — the Category -> Style theme table: all twelve categories present,
ANSI/CSS derivation correct.
"""

import pytest

from clens.core.highlight import Category
from clens.core.theme import ANSI_RESET, THEME, Style


def test_theme_covers_every_category():
    assert set(THEME) == set(Category)


def test_ansi_resets_to_default():
    assert ANSI_RESET == "\x1b[0m"


def test_ansi_encodes_truecolor_hex():
    style = Style("#569CD6")
    assert style.ansi == "\x1b[38;2;86;156;214m"


def test_ansi_includes_bold_italic_underline_codes():
    assert Style("#000000", bold=True).ansi == "\x1b[1;38;2;0;0;0m"
    assert Style("#000000", italic=True).ansi == "\x1b[3;38;2;0;0;0m"
    assert Style("#000000", underline=True).ansi == "\x1b[4;38;2;0;0;0m"


def test_css_declarations_include_color():
    assert Style("#569CD6").css_declarations == "color: #569CD6;"


def test_css_declarations_include_modifiers():
    style = Style("#F44747", underline=True)
    assert style.css_declarations == "color: #F44747; text-decoration: underline;"


@pytest.mark.parametrize(
    "category,expected_flag",
    [
        (Category.KEYWORD, "bold"),
        (Category.COMMENT, "italic"),
        (Category.ERROR, "underline"),
    ],
)
def test_specific_categories_carry_their_documented_modifier(category, expected_flag):
    assert getattr(THEME[category], expected_flag) is True

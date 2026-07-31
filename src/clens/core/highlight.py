"""Category enum and the highlight map (R5.2). Language-agnostic: these
twelve categories are the contract every language's highlighter fills in;
nothing here knows which C (or later, Java) construct maps to which.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Category", "HighlightMap"]


class Category(Enum):
    """The twelve highlighting categories required by R5.2."""

    KEYWORD = "keyword"
    TYPE = "type"
    VARIABLE = "variable"
    FUNCTION = "function"
    TYPE_NAME = "type_name"
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    OPERATOR = "operator"
    COMMENT = "comment"
    PREPROCESSOR = "preprocessor"
    ERROR = "error"


#: Maps a token's index in the full (trivia-included) token list to the
#: category it should render as. Tokens with no entry (delimiters,
#: whitespace, EOF) render with no styling — see `.agents/skills/highlighter/SKILL.md`
#: on why the map is keyed by index rather than by node: it lets the
#: renderer walk the original source in order, independent of the AST.
HighlightMap = dict[int, Category]

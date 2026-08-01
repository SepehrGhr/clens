"""The one query layer (D23): `completions_at`, `hover_at`, `symbols_of`,
`diagnostics_of`, all pure functions over a `SemanticModel`. The CLI, the web
server, and any future LSP server are thin adapters over these — no feature
logic belongs in an adapter.

Lives in `languages/c/`, not `core/queries.py` as the skill's illustrative
snippet shows: every function here takes a `SemanticModel`, which embeds the
C-specific AST, so this module can't live in core without violating the
core/language layering rule — same reason `SemanticModel` itself and
`resolve_type_spec` live here instead of in `core/`.

All position parameters are a 0-based **offset**, not line/column — adapters
convert via `SourceFile`. One conversion point, one place for off-by-one
bugs to live (D23).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from clens.core.scopes import Scope, ScopeKind, scope_at, symbols_visible_at
from clens.core.symbols import Symbol, SymbolKind
from clens.core.token import Span, Token, TokenType
from clens.core.types import PointerType, StructType, Type
from clens.core.visitor import walk
from clens.languages.c.keywords import KEYWORDS

if TYPE_CHECKING:
    from clens.core.diagnostics import Diagnostic
    from clens.languages.c.semantic import SemanticModel

__all__ = [
    "CompletionItem",
    "DefinitionInfo",
    "HoverInfo",
    "ReferenceInfo",
    "completions_at",
    "definition_info_to_dict",
    "diagnostics_of",
    "find_references",
    "find_references_by_name",
    "find_references_to_dict",
    "goto_definition_at",
    "hover_at",
    "references_at",
    "scope_to_dict",
    "symbol_to_dict",
    "symbols_of",
]

#: A symbol this far from the cursor's scope always sorts after any real,
#: lexically-reachable symbol (D24: "keywords ranked below real symbols").
_KEYWORD_DISTANCE = 1_000_000

_MEMBER_OPERATORS = frozenset({".", "->"})
_SUPPRESSED_TYPES = frozenset(
    {TokenType.LINE_COMMENT, TokenType.BLOCK_COMMENT, TokenType.STRING_LIT}
)

_KIND_LABELS = {
    SymbolKind.VARIABLE: "variable",
    SymbolKind.FUNCTION: "function",
    SymbolKind.PARAMETER: "parameter",
    SymbolKind.TYPE: "type",
    SymbolKind.FIELD: "field",
}


@dataclass(slots=True, frozen=True)
class CompletionItem:
    """One completion candidate (S5.5). `sort_order` is a float; lower
    sorts first — it is not meaningful on its own, only relative to other
    items in the same `completions_at` result.
    """

    label: str
    kind: str
    detail: str
    sort_order: float


@dataclass(slots=True, frozen=True)
class HoverInfo:
    """S7: a symbol's full type signature, its enclosing scope description,
    and its attached doc comment, if any."""

    signature: str
    scope_description: str
    doc_comment: str | None


def symbols_of(model: SemanticModel) -> list[Symbol]:
    """Every symbol in the model, flattened from the by-name index."""
    return [symbol for symbols in model.symbols_by_name.values() for symbol in symbols]


def scope_to_dict(scope: Scope) -> dict:
    """The scope tree as a JSON-shaped dict, recursively — the CLI's
    `clens symbols --json` and the web UI's symbol tree panel are the same
    shape, so both adapters share this rather than each re-deriving it.
    """
    return {
        "kind": scope.kind.value,
        "symbols": [symbol_to_dict(s) for s in scope.symbols.values()],
        "children": [scope_to_dict(c) for c in scope.children],
    }


def symbol_to_dict(symbol: Symbol) -> dict:
    return {
        "name": symbol.name,
        "kind": symbol.kind.value,
        "type": str(symbol.type),
        "line": symbol.definition_loc.line,
        "column": symbol.definition_loc.column,
        "is_used": symbol.is_used,
        "is_initialized": symbol.is_initialized,
    }


def diagnostics_of(model: SemanticModel) -> list[Diagnostic]:
    """Every diagnostic recorded while building the model, sorted."""
    return model.diagnostics.sorted()


# --- completions_at (S5.1-S5.6, D24) -----------------------------------------


def completions_at(model: SemanticModel, offset: int) -> list[CompletionItem]:
    """Completions for the cursor at `offset`.

    Context is read straight from the token stream, not the AST: `p.` with
    nothing typed after the dot is a syntax error (the parser can't build a
    `MemberExpr` from it), and that is the *normal*, most common state while
    a user is mid-typing. Relying on a clean parse would make completion
    fail exactly when it matters most.
    """
    prefix, preceding = _cursor_context(model.tokens, offset)
    if prefix is None:
        return []  # inside a comment or string literal (S5.2)

    if preceding is not None and _is_member_operator(preceding):
        return _member_completions(model, preceding, prefix)

    expected_param_type = _expected_argument_type(model, offset)
    return _general_completions(model, offset, prefix, expected_param_type)


def _member_completions(
    model: SemanticModel, dot_token: Token, prefix: str
) -> list[CompletionItem]:
    target = _resolve_member_base(model, dot_token)
    if not isinstance(target, StructType):
        return []
    struct_scope = _struct_scope(model, target)
    if struct_scope is None:
        return []
    ranked = []
    for field_symbol in struct_scope.symbols.values():
        rank = _match_rank(field_symbol.name, prefix)
        if rank is None:
            continue
        ranked.append((rank, field_symbol.name.lower(), _completion_item(field_symbol)))
    return _finalize(ranked)


def _general_completions(
    model: SemanticModel, offset: int, prefix: str, expected_param_type: Type | None
) -> list[CompletionItem]:
    cursor_scope = scope_at(model.global_scope, offset)
    ranked = []
    for symbol in symbols_visible_at(model.global_scope, offset):
        rank = _match_rank(symbol.name, prefix)
        if rank is None:
            continue
        matches_param = expected_param_type is not None and symbol.type == expected_param_type
        type_bonus = 0 if matches_param else 1
        distance = _scope_distance(cursor_scope, symbol.scope)
        ranked.append((rank, type_bonus, distance, symbol.name.lower(), _completion_item(symbol)))
    for keyword in KEYWORDS:
        rank = _match_rank(keyword, prefix)
        if rank is None:
            continue
        item = CompletionItem(label=keyword, kind="keyword", detail="keyword", sort_order=0.0)
        ranked.append((rank, 1, _KEYWORD_DISTANCE, keyword, item))
    return _finalize(ranked)


def _finalize(ranked: list[tuple]) -> list[CompletionItem]:
    """Sort by every key but the trailing `CompletionItem`, then stamp
    `sort_order` with the final rank so consumers don't need to re-derive
    it from the tuple."""
    ranked.sort(key=lambda entry: entry[:-1])
    return [replace(item, sort_order=float(i)) for i, (*_keys, item) in enumerate(ranked)]


def _completion_item(symbol: Symbol) -> CompletionItem:
    if symbol.kind is SymbolKind.FUNCTION and symbol.signature is not None:
        detail = str(symbol.signature)
    else:
        detail = str(symbol.type)
    kind = _KIND_LABELS[symbol.kind]
    return CompletionItem(label=symbol.name, kind=kind, detail=detail, sort_order=0.0)


def _match_rank(label: str, prefix: str) -> int | None:
    """D24's three tiers, lowest sorts first; `None` means excluded
    entirely. An empty prefix (nothing typed yet) matches everything at the
    best tier - tie-breaks alone decide the order."""
    if prefix == "" or label.startswith(prefix):
        return 0
    if label.lower().startswith(prefix.lower()):
        return 1
    if _is_subsequence(prefix.lower(), label.lower()):
        return 2
    return None


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def _scope_distance(from_scope: Scope, to_scope: Scope) -> int:
    """Hops from `from_scope` outward to `to_scope`: 0 if the symbol is
    declared in the cursor's own scope, 1 in its immediate parent, and so
    on - the "local beats global" tie-break (D24)."""
    distance = 0
    current: Scope | None = from_scope
    while current is not None:
        if current is to_scope:
            return distance
        current = current.parent
        distance += 1
    return distance  # defensive: to_scope wasn't an ancestor; sorts last


# --- context detection (S5.2) ------------------------------------------------


def _cursor_context(tokens: list[Token], offset: int) -> tuple[str | None, Token | None]:
    """`(prefix, preceding_significant_token)` for the cursor at `offset`.

    `prefix is None` signals suppression (inside a comment or string
    literal - S5.2's easy-to-forget row). `::` (scope resolution) has no
    lexeme in this subset's operator set at all, so it needs no handling
    here; documented N/A per S5.2.
    """
    for token in tokens:
        if token.type is TokenType.IDENT and token.start_offset <= offset <= token.end_offset:
            prefix = token.lexeme[: offset - token.start_offset]
            preceding = _last_significant_before(tokens, token.start_offset)
            return prefix, preceding
        if token.start_offset <= offset < token.end_offset:
            if token.type in _SUPPRESSED_TYPES:
                return None, None
            preceding = _last_significant_before(tokens, token.start_offset)
            return "", preceding
    return "", _last_significant_before(tokens, offset)


def _last_significant_before(tokens: list[Token], offset: int) -> Token | None:
    result = None
    for token in tokens:
        if token.is_trivia:
            continue
        if token.end_offset > offset:
            break
        result = token
    return result


def _is_member_operator(token: Token) -> bool:
    return token.type is TokenType.OPERATOR and token.lexeme in _MEMBER_OPERATORS


def _resolve_member_base(model: SemanticModel, dot_token: Token) -> Type | None:
    """The type completion (or hover) should look fields up on, for a `.`
    or `->` at `dot_token`: resolve the identifier immediately before it
    through the scope tree, deref one pointer level if needed. Token-based,
    not AST-based - works whether or not the member expression itself
    parsed cleanly.
    """
    base_token = _last_significant_before(model.tokens, dot_token.start_offset)
    if base_token is None or base_token.type is not TokenType.IDENT:
        return None
    scope = scope_at(model.global_scope, base_token.start_offset)
    symbol = scope.lookup(base_token.lexeme)
    if symbol is None:
        return None
    obj_type = symbol.type
    if isinstance(obj_type, PointerType):
        obj_type = obj_type.pointee
    return obj_type


def _struct_scope(model: SemanticModel, struct_type: StructType) -> Scope | None:
    for scope in model.all_scopes:
        if scope.kind is ScopeKind.STRUCT and scope.owner is struct_type.decl:
            return scope
    return None


# --- argument-list context (S5.2) --------------------------------------------

_OPENERS = frozenset({"(", "["})
_CLOSERS = frozenset({")", "]"})
_STATEMENT_BOUNDARY = frozenset({"{", "}", ";"})


def _expected_argument_type(model: SemanticModel, offset: int) -> Type | None:
    """If the cursor sits inside a call's argument list, the parameter
    type at the current argument index - re-ranking completions by it,
    without filtering anything out (ARGUMENT is "general, but re-ranked").
    """
    call = _enclosing_call(model.tokens, offset)
    if call is None:
        return None
    callee_name, arg_index = call
    scope = scope_at(model.global_scope, offset)
    symbol = scope.lookup(callee_name)
    if symbol is None or symbol.signature is None:
        return None
    params = symbol.signature.params
    if arg_index >= len(params):
        return None
    return params[arg_index]


def _enclosing_call(tokens: list[Token], offset: int) -> tuple[str, int] | None:
    """Walk backward from `offset` tracking bracket depth. Returns
    `(function_name, argument_index)` if the nearest unmatched opening
    bracket is a `(` immediately preceded by an identifier; `None` if the
    cursor isn't inside a call at all (crossing a `;`/`{`/`}` first, or
    inside a `[...]` instead).
    """
    relevant = [t for t in tokens if not t.is_trivia and t.end_offset <= offset]
    depth = 0
    arg_index = 0
    for i in range(len(relevant) - 1, -1, -1):
        token = relevant[i]
        if token.type is not TokenType.DELIMITER:
            continue
        lexeme = token.lexeme
        if lexeme in _CLOSERS:
            depth += 1
        elif lexeme in _OPENERS:
            if depth > 0:
                depth -= 1
                continue
            if lexeme != "(" or i == 0:
                return None
            prev = relevant[i - 1]
            if prev.type is not TokenType.IDENT:
                return None
            return prev.lexeme, arg_index
        elif lexeme in _STATEMENT_BOUNDARY:
            return None
        elif lexeme == "," and depth == 0:
            arg_index += 1
    return None


# --- hover_at (S7) -------------------------------------------------------


def hover_at(model: SemanticModel, offset: int) -> HoverInfo | None:
    token = _identifier_token_at(model.tokens, offset)
    if token is None:
        return None

    preceding = _last_significant_before(model.tokens, token.start_offset)
    if preceding is not None and _is_member_operator(preceding):
        return _hover_member(model, preceding, token)

    scope = scope_at(model.global_scope, offset)
    symbol = scope.lookup(token.lexeme)
    if symbol is None:
        return None
    return _hover_for_symbol(model, symbol)


def _hover_member(model: SemanticModel, dot_token: Token, field_token: Token) -> HoverInfo | None:
    target = _resolve_member_base(model, dot_token)
    if not isinstance(target, StructType):
        return None
    struct_scope = _struct_scope(model, target)
    if struct_scope is None:
        return None
    field_symbol = struct_scope.lookup_local(field_token.lexeme)
    if field_symbol is None:
        return None
    return _hover_for_symbol(model, field_symbol)


def _hover_for_symbol(model: SemanticModel, symbol: Symbol) -> HoverInfo:
    if symbol.kind is SymbolKind.FUNCTION and symbol.signature is not None:
        signature = str(symbol.signature)
    else:
        signature = str(symbol.type)
    return HoverInfo(
        signature=signature,
        scope_description=_scope_description(symbol.scope),
        doc_comment=_doc_comment(model, symbol),
    )


def _identifier_token_at(tokens: list[Token], offset: int) -> Token | None:
    for token in tokens:
        if token.type is TokenType.IDENT and token.start_offset <= offset <= token.end_offset:
            return token
    return None


def _scope_description(scope: Scope) -> str:
    if scope.kind is ScopeKind.GLOBAL:
        return "global scope"
    if scope.kind is ScopeKind.FUNCTION:
        name = getattr(scope.owner, "name", None)
        return f"function '{name}'" if name else "function scope"
    if scope.kind is ScopeKind.STRUCT:
        name = getattr(scope.owner, "name", None)
        return f"struct '{name}'" if name else "struct scope"
    if scope.kind is ScopeKind.FOR_INIT:
        return "for-loop scope"
    # BLOCK: describe via the nearest enclosing function, if any.
    parent = scope.parent
    while parent is not None and parent.kind is not ScopeKind.FUNCTION:
        parent = parent.parent
    name = getattr(parent, "owner", None) and getattr(parent.owner, "name", None)
    return f"function '{name}'" if name else "block scope"


# --- Navigation (A4.1-A4.4) --------------------------------------------------
#
# Phase 2 already populated Symbol.definition_loc and Symbol.references
# during resolution exactly so these would be lookups, not analyses: if
# this section ever starts walking the AST, that is a sign of re-deriving
# data that already exists.


@dataclass(slots=True, frozen=True)
class DefinitionInfo:
    """A4.1's result: which symbol the cursor was on, and where it was
    declared."""

    symbol: Symbol
    location: Span


@dataclass(slots=True, frozen=True)
class ReferenceInfo:
    """One entry in a `find_references` result. Same shape as `Reference`
    plus `is_definition`, since the declaration site is folded into the
    same list rather than returned separately (A4.2)."""

    span: Span
    is_read: bool
    is_write: bool
    is_definition: bool


def _symbol_at(model: SemanticModel, offset: int) -> Symbol | None:
    """The `Symbol` the identifier at `offset` refers to, whether a plain
    name or the right-hand side of `.`/`->`. Shared by `goto_definition_at`
    and `references_at` so both resolve a cursor position identically.
    """
    token = _identifier_token_at(model.tokens, offset)
    if token is None:
        return None
    preceding = _last_significant_before(model.tokens, token.start_offset)
    if preceding is not None and _is_member_operator(preceding):
        return _member_symbol_at(model, preceding, token)
    scope = scope_at(model.global_scope, offset)
    return scope.lookup(token.lexeme)


def _member_symbol_at(model: SemanticModel, dot_token: Token, field_token: Token) -> Symbol | None:
    target = _resolve_member_base(model, dot_token)
    if not isinstance(target, StructType):
        return None
    struct_scope = _struct_scope(model, target)
    if struct_scope is None:
        return None
    return struct_scope.lookup_local(field_token.lexeme)


def goto_definition_at(model: SemanticModel, offset: int) -> DefinitionInfo | None:
    """A4.1: the exact location of the declaration of whatever is at
    `offset` -- a variable, parameter, function, struct tag, or field.
    Cursor already on the declaration itself resolves to that same
    declaration, not `None`: scope lookup does not distinguish "this is
    the defining occurrence" from any other occurrence of the name.
    """
    symbol = _symbol_at(model, offset)
    if symbol is None:
        return None
    return DefinitionInfo(symbol=symbol, location=symbol.definition_loc)


def find_references(model: SemanticModel, symbol: Symbol) -> list[ReferenceInfo]:
    """A4.2: `symbol.references` plus the definition site itself (flagged,
    per the skill -- a references list that omits the declaration looks
    incomplete), sorted by offset since insertion order is resolution
    order, which is close but not guaranteed identical.
    """
    definition = ReferenceInfo(
        span=symbol.definition_loc, is_read=False, is_write=False, is_definition=True
    )
    others = [
        ReferenceInfo(span=r.span, is_read=r.is_read, is_write=r.is_write, is_definition=False)
        for r in symbol.references
    ]
    combined = [definition, *others]
    combined.sort(key=lambda r: r.span.start_offset)
    return combined


def references_at(model: SemanticModel, offset: int) -> list[ReferenceInfo] | None:
    """The cursor-driven form of `find_references`, for the web UI's
    click-to-navigate and a CLI position-based lookup."""
    symbol = _symbol_at(model, offset)
    if symbol is None:
        return None
    return find_references(model, symbol)


def find_references_by_name(
    model: SemanticModel, name: str
) -> list[tuple[Symbol, list[ReferenceInfo]]]:
    """`clens find-refs` takes a **name**, per the course document's
    example, not a cursor position. If the name is ambiguous (declared in
    several scopes -- e.g. a local shadowing a global), every match is
    returned rather than guessing which one was meant.
    """
    return [
        (symbol, find_references(model, symbol)) for symbol in model.symbols_by_name.get(name, [])
    ]


def _symbol_type_str(symbol: Symbol) -> str:
    if symbol.kind is SymbolKind.FUNCTION and symbol.signature is not None:
        return str(symbol.signature)
    return str(symbol.type)


def definition_info_to_dict(model: SemanticModel, info: DefinitionInfo) -> dict:
    return {
        "symbol": info.symbol.name,
        "kind": info.symbol.kind.value,
        "type": _symbol_type_str(info.symbol),
        "defined_at": {
            "file": model.source.filename,
            "line": info.location.line,
            "col": info.location.column,
        },
    }


def find_references_to_dict(
    model: SemanticModel, symbol: Symbol, references: list[ReferenceInfo]
) -> dict:
    """The course document's §6.3 shape, exactly -- note the key is `col`,
    not `column` (`Diagnostic.to_dict()` uses `column`; the two specs are
    matched independently, never unified). The definition site is not
    repeated inside `references`: it is already `defined_at`.
    """
    return {
        "symbol": symbol.name,
        "kind": symbol.kind.value,
        "type": _symbol_type_str(symbol),
        "defined_at": {
            "file": model.source.filename,
            "line": symbol.definition_loc.line,
            "col": symbol.definition_loc.column,
        },
        "references": [
            {"file": model.source.filename, "line": r.span.line, "col": r.span.column}
            for r in references
            if not r.is_definition
        ],
    }


# --- doc comments (S7, R1.8) --------------------------------------------


def _doc_comment(model: SemanticModel, symbol: Symbol) -> str | None:
    decl_start = _decl_span_start(model, symbol)
    return _preceding_comment_block(model.tokens, decl_start)


def _decl_span_start(model: SemanticModel, symbol: Symbol) -> int:
    """The start offset of the whole declaration `symbol` was declared by
    (its `name_span` alone would land on just the name, e.g. `factorial`,
    not the `int` a doc comment actually precedes)."""
    for node in walk(model.program):
        if getattr(node, "name_span", None) == symbol.definition_loc:
            return node.span.start_offset
    return symbol.definition_loc.start_offset


def _preceding_comment_block(tokens: list[Token], decl_start: int) -> str | None:
    before = [t for t in tokens if t.end_offset <= decl_start]
    i = len(before) - 1
    while i >= 0 and before[i].type is TokenType.WHITESPACE:
        i -= 1
    if i < 0:
        return None
    if before[i].type is TokenType.BLOCK_COMMENT:
        return _strip_block_comment(before[i].lexeme)
    if before[i].type is not TokenType.LINE_COMMENT:
        return None
    lines: list[str] = []
    while i >= 0 and before[i].type is TokenType.LINE_COMMENT:
        lines.append(_strip_line_comment(before[i].lexeme))
        i -= 1
        while i >= 0 and before[i].type is TokenType.WHITESPACE:
            i -= 1
    lines.reverse()
    return "\n".join(lines)


def _strip_line_comment(lexeme: str) -> str:
    return lexeme[2:].strip()


def _strip_block_comment(lexeme: str) -> str:
    inner = lexeme[2:-2]
    lines = []
    for raw_line in inner.split("\n"):
        line = raw_line.strip()
        if line.startswith("*"):
            line = line[1:].strip()
        if line:
            lines.append(line)
    return "\n".join(lines)

"""Recursive CFG construction for the C subset (A1.1-A1.5, A8.1).

`switch`, `goto`, and labels are out of scope (`10-phase2-interfaces.md`), so
every construct here is structured: `if`, `while`, `for`, `return`, `break`,
`continue` are the only ways control ever transfers. That means the
recursive builder below always terminates with one well-formed, reducible
graph — never an arbitrary jump target to resolve.

The core recipe (`.agents/skills/cfg/SKILL.md`): `_build_stmt(stmt, current)`
returns the block control continues in, or `None` if control never falls out
the bottom (`return`/`break`/`continue`). A `None` result with statements
still left in the enclosing block is exactly a post-jump unreachable region
(A2.3) — built into a fresh, disconnected block so "no incoming edges"
catches it structurally instead of a special case.
"""

from __future__ import annotations

from clens.core.ast_nodes import Decl, ErrorExpr, ErrorStmt, Expr, Node
from clens.core.cfg import BasicBlock, BlockKind, ControlFlowGraph, EdgeLabel
from clens.languages.c.ast_nodes import (
    AssignExpr,
    BinaryExpr,
    Block,
    BreakStmt,
    CallExpr,
    CharLiteral,
    ContinueStmt,
    EmptyStmt,
    ExprStmt,
    FloatLiteral,
    ForStmt,
    FuncDecl,
    Identifier,
    IfStmt,
    IndexExpr,
    IntLiteral,
    MemberExpr,
    ReturnStmt,
    SizeofExpr,
    StringLiteral,
    TernaryExpr,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)

__all__ = ["build_cfg", "describe_node", "render_cfg_text"]


class _LoopContext:
    """Where `break` and `continue` jump to for the loop currently being
    built. `continue_target` is the loop header for `while` (nothing to run
    before re-testing the condition) but a separate latch block for `for`
    (the update expression must run before the condition is re-tested).
    """

    __slots__ = ("continue_target", "after")

    def __init__(self, continue_target: BasicBlock, after: BasicBlock) -> None:
        self.continue_target = continue_target
        self.after = after


def build_cfg(func: FuncDecl) -> ControlFlowGraph | None:
    """Build the CFG for one function definition (A1.1). `None` for a
    prototype (`body is None`, A8.1) — a declaration with no body has no
    control flow to graph, and building an empty one would be misleading.
    """
    if func.body is None:
        return None
    return _Builder(func.name).build(func.body)


def _condition_always_true(cond: Expr) -> bool:
    """Recognizes the literal `while(1)` / `for(;;)` idiom (A8.1) so the
    false edge is omitted rather than wired to a block that can never
    actually be reached — that missing edge is exactly what makes the loop's
    EXIT genuinely unreachable when there is no `break`, which the course
    document calls out as correct, not a bug.
    """
    return isinstance(cond, IntLiteral) and cond.value != 0


def _condition_always_false(cond: Expr) -> bool:
    return isinstance(cond, IntLiteral) and cond.value == 0


class _Builder:
    def __init__(self, function_name: str) -> None:
        self._function_name = function_name
        self._next_id = 1
        self._blocks: list[BasicBlock] = []
        self._loop_stack: list[_LoopContext] = []
        self._exit: BasicBlock

    def build(self, body: Block) -> ControlFlowGraph:
        entry = self._new_block(BlockKind.ENTRY)
        self._exit = self._new_block(BlockKind.EXIT)
        tail = self._build_stmt(body, entry)
        if tail is not None:
            tail.add_successor(self._exit, EdgeLabel.FALLTHROUGH)
        return ControlFlowGraph(
            function_name=self._function_name,
            entry=entry,
            exit=self._exit,
            blocks=self._blocks,
        )

    def _new_block(self, kind: BlockKind) -> BasicBlock:
        if kind is BlockKind.NORMAL:
            block = BasicBlock(id=self._next_id, kind=kind)
            self._next_id += 1
        else:
            block = BasicBlock(id=0, kind=kind)
        self._blocks.append(block)
        return block

    def _ensure_normal(self, current: BasicBlock) -> BasicBlock:
        if current.kind is BlockKind.NORMAL:
            return current
        new = self._new_block(BlockKind.NORMAL)
        current.add_successor(new, EdgeLabel.FALLTHROUGH)
        return new

    def _append(self, current: BasicBlock, stmt: Node) -> BasicBlock:
        block = self._ensure_normal(current)
        block.statements.append(stmt)
        return block

    def _build_stmt(self, stmt: Node, current: BasicBlock) -> BasicBlock | None:
        if isinstance(stmt, Block):
            return self._build_block(stmt, current)
        if isinstance(stmt, IfStmt):
            return self._build_if(stmt, current)
        if isinstance(stmt, WhileStmt):
            return self._build_while(stmt, current)
        if isinstance(stmt, ForStmt):
            return self._build_for(stmt, current)
        if isinstance(stmt, ReturnStmt):
            block = self._append(current, stmt)
            block.add_successor(self._exit, EdgeLabel.FALLTHROUGH)
            return None
        if isinstance(stmt, BreakStmt):
            block = self._append(current, stmt)
            target = self._loop_stack[-1].after if self._loop_stack else self._exit
            block.add_successor(target, EdgeLabel.FALLTHROUGH)
            return None
        if isinstance(stmt, ContinueStmt):
            block = self._append(current, stmt)
            # `continue`/`break` outside any loop is already a parse-level
            # concern, but a recovered AST can still hand us one (A8.1): fall
            # through to EXIT rather than raise on an empty loop stack.
            target = self._loop_stack[-1].continue_target if self._loop_stack else self._exit
            block.add_successor(target, EdgeLabel.BACK)
            return None
        # ExprStmt, VarDecl, EmptyStmt, ErrorStmt/ErrorExpr, or anything else
        # with no control effect: straight-line, append and continue. Error
        # nodes are treated as opaque (A8.1) -- never inspected inside.
        return self._append(current, stmt)

    def _build_block(self, block: Block, current: BasicBlock) -> BasicBlock | None:
        tail: BasicBlock | None = current
        for item in block.body:
            if tail is None:
                tail = self._new_block(BlockKind.NORMAL)
            tail = self._build_stmt(item, tail)
        return tail

    def _build_if(self, stmt: IfStmt, current: BasicBlock) -> BasicBlock | None:
        head = self._append(current, stmt.condition)

        then_entry = self._new_block(BlockKind.NORMAL)
        head.add_successor(then_entry, EdgeLabel.TRUE)
        then_tail = self._build_stmt(stmt.then_branch, then_entry)

        else_tail: BasicBlock | None = None
        if stmt.else_branch is not None:
            else_entry = self._new_block(BlockKind.NORMAL)
            head.add_successor(else_entry, EdgeLabel.FALSE)
            else_tail = self._build_stmt(stmt.else_branch, else_entry)

        join = self._new_block(BlockKind.NORMAL)
        if then_tail is not None:
            then_tail.add_successor(join, EdgeLabel.FALLTHROUGH)
        if stmt.else_branch is not None:
            if else_tail is not None:
                else_tail.add_successor(join, EdgeLabel.FALLTHROUGH)
        else:
            head.add_successor(join, EdgeLabel.FALSE)

        return join

    def _build_while(self, stmt: WhileStmt, current: BasicBlock) -> BasicBlock | None:
        header = self._new_block(BlockKind.NORMAL)
        current.add_successor(header, EdgeLabel.FALLTHROUGH)
        header.statements.append(stmt.condition)

        always_true = _condition_always_true(stmt.condition)
        always_false = _condition_always_false(stmt.condition)

        body_entry = self._new_block(BlockKind.NORMAL)
        if not always_false:
            header.add_successor(body_entry, EdgeLabel.TRUE)

        after = self._new_block(BlockKind.NORMAL)
        if not always_true:
            header.add_successor(after, EdgeLabel.FALSE)

        self._loop_stack.append(_LoopContext(continue_target=header, after=after))
        body_tail = self._build_stmt(stmt.body, body_entry)
        self._loop_stack.pop()

        if body_tail is not None:
            body_tail.add_successor(header, EdgeLabel.BACK)

        return after

    def _build_for(self, stmt: ForStmt, current: BasicBlock) -> BasicBlock | None:
        current = self._build_for_init(stmt.init, current)

        header = self._new_block(BlockKind.NORMAL)
        current.add_successor(header, EdgeLabel.FALLTHROUGH)
        if stmt.condition is not None:
            header.statements.append(stmt.condition)

        always_true = stmt.condition is None or _condition_always_true(stmt.condition)
        always_false = stmt.condition is not None and _condition_always_false(stmt.condition)

        body_entry = self._new_block(BlockKind.NORMAL)
        if not always_false:
            header.add_successor(body_entry, EdgeLabel.TRUE)

        after = self._new_block(BlockKind.NORMAL)
        if not always_true:
            header.add_successor(after, EdgeLabel.FALSE)

        latch = self._new_block(BlockKind.NORMAL)
        if stmt.update is not None:
            latch.statements.append(stmt.update)
        latch.add_successor(header, EdgeLabel.BACK)

        self._loop_stack.append(_LoopContext(continue_target=latch, after=after))
        body_tail = self._build_stmt(stmt.body, body_entry)
        self._loop_stack.pop()

        if body_tail is not None:
            body_tail.add_successor(latch, EdgeLabel.FALLTHROUGH)

        return after

    def _build_for_init(self, init: object, current: BasicBlock) -> BasicBlock:
        if init is None:
            return current
        if isinstance(init, list):
            for decl in init:
                current = self._append(current, decl)
            return current
        result = self._build_stmt(init, current)
        # An init clause is a declaration or expression statement; neither
        # ever terminates control. Guarded anyway (A8.1) against a
        # malformed/recovered AST rather than trusting that invariant.
        return result if result is not None else current


def describe_node(node: Node) -> str:
    """Render `node` as a short, human-readable label for CFG and call-graph
    display: a compact reconstruction from the AST, not a verbatim source
    slice, so stray whitespace and comments never leak into a block label.
    """
    if isinstance(node, ReturnStmt):
        return "return" if node.value is None else f"return {describe_node(node.value)}"
    if isinstance(node, BreakStmt):
        return "break"
    if isinstance(node, ContinueStmt):
        return "continue"
    if isinstance(node, ExprStmt):
        return describe_node(node.expr)
    if isinstance(node, VarDecl):
        base = f"{node.type.base}{'*' * node.type.pointer_depth} {node.name}"
        return f"{base} = {describe_node(node.init)}" if node.init is not None else base
    if isinstance(node, EmptyStmt):
        return ";"
    if isinstance(node, ErrorStmt | ErrorExpr):
        return f"<error: {node.message}>" if node.message else "<error>"
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, IntLiteral | FloatLiteral):
        return str(node.value)
    if isinstance(node, StringLiteral):
        return f'"{node.value}"'
    if isinstance(node, CharLiteral):
        return f"'{node.value}'"
    if isinstance(node, BinaryExpr):
        return f"{describe_node(node.left)} {node.op} {describe_node(node.right)}"
    if isinstance(node, UnaryExpr):
        if node.prefix:
            return f"{node.op}{describe_node(node.operand)}"
        return f"{describe_node(node.operand)}{node.op}"
    if isinstance(node, AssignExpr):
        return f"{describe_node(node.target)} {node.op} {describe_node(node.value)}"
    if isinstance(node, TernaryExpr):
        return (
            f"{describe_node(node.condition)} ? {describe_node(node.then_expr)}"
            f" : {describe_node(node.else_expr)}"
        )
    if isinstance(node, CallExpr):
        args = ", ".join(describe_node(a) for a in node.args)
        return f"{node.callee}({args})"
    if isinstance(node, IndexExpr):
        return f"{describe_node(node.array)}[{describe_node(node.index)}]"
    if isinstance(node, MemberExpr):
        op = "->" if node.arrow else "."
        return f"{describe_node(node.obj)}{op}{node.member}"
    if isinstance(node, SizeofExpr):
        target = node.target
        inner = describe_node(target) if isinstance(target, Expr) else target.base
        return f"sizeof({inner})"
    if isinstance(node, Decl):
        name = getattr(node, "name", None)
        return name if name is not None else type(node).__name__
    return type(node).__name__


def render_cfg_text(cfg: ControlFlowGraph) -> str:
    """The plain-text form for `clens show-cfg` (A7.2): block contents and
    labelled successor edges, ENTRY first and EXIT last regardless of build
    order, matching the shape of the course document's §6.1 example.
    """
    normals = sorted((b for b in cfg.blocks if b.kind is BlockKind.NORMAL), key=lambda b: b.id)
    ordered = [cfg.entry, *normals, cfg.exit]

    blocks_text = []
    for block in ordered:
        content = "; ".join(describe_node(s) for s in block.statements)
        header = f"{block.label()}: {content}" if content else block.label()
        edge_lines = [_edge_line(target, label) for target, label in block.successors]
        blocks_text.append("\n".join([header, *edge_lines]))
    return "\n\n".join(blocks_text)


def _edge_line(target: BasicBlock, label: EdgeLabel) -> str:
    if label in (EdgeLabel.TRUE, EdgeLabel.FALSE, EdgeLabel.BACK):
        return f"  --{label.value}--> {target.label()}"
    return f"  -> {target.label()}"

# Interactive web UI

## Goal

A browser-based editor: type C source on the left, see it highlighted,
diagnosed, completed, and hovered on the right — plus, as of Phase 3,
tabs for the control-flow graph, call graph, and dead-code report of the
function under the cursor. This is the course document's bonus
"interface" item, and it doubles as the answer to **A7.1/§6.6**'s Phase 3
requirement for *some* interactive way to reach the new navigation/CFG/
call-graph features — stated plainly here so it isn't missed: the web UI
*is* that interface, there is no separate one.

## Motivation

Every Phase 1–3 feature (`highlight`, `check`, `complete`, `hover`,
`goto-def`, `find-refs`, `show-cfg`, `callgraph`, `dead-code`) already
exists as a pure function over a `SemanticModel`/`ProgramAnalysis` — the
CLI is one thin adapter over that. A web UI is a second thin adapter over
the exact same functions, and it is a far better way to *demonstrate* the
project than a terminal transcript: a grader can type an edit and watch
diagnostics, the CFG, and the dead-code list all update live, which is
the actual point of an IDE feature set.

## Implementation

`src/clens/web/server.py` — stdlib `http.server` only, **zero third-party
dependencies** (D22), consistent with the rest of the project. Each
`/api/*` route is a plain function taking/returning a dict
(`handle_analyze`, `handle_complete`, `handle_hover`, `handle_cfg`,
`handle_callgraph`, `handle_dead_code`), routed through a `_POST_ROUTES`
dict and a pure `dispatch_post(path, raw_body) -> (payload, status)` —
kept separate from `ClensRequestHandler`'s socket handling so every route,
including error cases (unknown path, malformed JSON, non-dict body), is
tested by calling `dispatch_post` directly, no socket involved
(`tests/unit/test_web_server.py`).

Every request rebuilds the model from scratch (`_build_model`: tokenize →
parse → analyze) — no incremental re-parse (see the deferred item in
`docs/future-work.md`). At this file size that is fast enough that
correctness beats latency (D21).

`src/clens/web/static/` — vanilla JS (`app.js`, ~550 lines), no build
step, no framework:

- **Editor pane**: a `<textarea>` posts to `/api/analyze` on every edit
  (debounced), rendering the highlighted HTML, squiggly diagnostics, and
  the symbol tree sidebar.
- **Completion and hover**: keyboard-driven completion popup
  (`/api/complete`) and a hover card on click (`/api/hover`), both exact
  adapters over `languages/c/queries.py` — no client-side logic decides
  ranking or content.
- **Analysis tabs** (`analysis-tabs` / `analysis-panel` in
  `index.html`), added in Phase 3:
  - **Control Flow Graph** — a function picker (`#function-picker`,
    populated from the symbol tree's top-level functions) drives
    `/api/cfg`, rendering the returned SVG directly.
  - **Call Graph** — `/api/callgraph` renders the whole program's call
    graph as SVG, plus plain lists of dead and recursive functions.
    Clicking a node in the SVG (`attachCallgraphClickHandler`) jumps to
    that function's definition in the editor, or shows its callers list
    — using the `edges` array `/api/callgraph` returns alongside the SVG
    so this needs no second request.
  - **Dead Code** — `/api/dead-code` renders all five A6 categories
    (unreachable functions, unreachable blocks, post-jump statements,
    unused variables, dead assignments) as a clickable list; clicking a
    row jumps to its location in the editor, same as a diagnostic.
- Every panel is a thin renderer over its endpoint's JSON — no analysis
  logic lives in JavaScript, matching the CLI/web symmetry the rest of
  the project holds to.

## Seeing it work

```bash
clens serve --port 8000
```

Open `http://127.0.0.1:8000`, then:

1. Type or paste a C program (e.g. the contents of
   `tests/fixtures/valid/factorial.c`) into the left pane — highlighting,
   diagnostics, and the symbol tree update as you type.
2. Click a symbol to see its hover card; place the cursor after a `.` or
   partial identifier and start typing to see completions.
3. Switch to the **Control Flow Graph** tab, pick a function from the
   dropdown, and see its CFG rendered as SVG.
4. Switch to **Call Graph** to see the whole-program call graph; click any
   function node to jump to its definition, and see its dead/recursive
   status and caller list.
5. Switch to **Dead Code** to see all five categories for the current
   source; click any row to jump to it in the editor.

Screenshots of each panel are in `docs/images/`:
`web-ui-overview.png`, `web-ui-completion.png`, `web-ui-hover.png`,
`web-ui-diagnostics.png`, `web-ui-cfg.png`, `web-ui-callgraph.png`,
`web-ui-deadcode.png`.

Tested without a browser via `tests/unit/test_web_server.py` (routing,
all six handlers) and `tests/unit/test_web_renderer.py` (the interactive
HTML renderer).

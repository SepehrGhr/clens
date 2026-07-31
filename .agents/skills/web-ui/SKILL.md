---
name: web-ui
description: The interactive web interface for c-lens — stdlib http.server backend, vanilla JS front end, side-by-side editor and rendered pane, completion popup and hover cards. Use whenever touching web/, and read it before adding any interactivity, because Phase 1's HTML renderer must stay frozen and JavaScript-free.
---

# Web UI

Requirements: S8.2, S8.3. Decision: D22.

This is the "cool demo" surface and the source of the README screenshots. It also
satisfies the course document's Phase 3 interface requirement (§6.6 lists Web UI as
one of three acceptable options), so it is Phase 3 work pulled forward, not extra.

## Rule zero: do not touch `render/html.py`

R6.2 requires a self-contained, **JavaScript-free** HTML output, and a golden test
pins it byte-for-byte. Adding `data-*` attributes or a script tag there breaks a
graded Phase 1 requirement.

The web UI gets **its own renderer**, `web/renderer.py`, which may emit whatever
attributes it likes. Both call the same highlighter and theme. Two renderers, one
category map — exactly the extensibility R6.3 asked for, now being used.

## Constraints that keep this cheap (D22)

- **stdlib `http.server` only.** No Flask, no FastAPI. Preserves the
  zero-runtime-dependency claim, which is a line in the README.
- **Vanilla JS.** No framework, no build step, no CDN, no npm. The whole front end
  is three static files.
- **Side-by-side panes.** A plain `<textarea>` on the left, the rendered highlighted
  pane on the right. **Do not** attempt a transparent-textarea-over-highlighted-`pre`
  overlay. That trick is where browser editors get expensive — caret alignment, font
  metrics, scroll sync, IME — and it buys nothing a grader will notice.

If you find yourself writing scroll-sync or caret-position math against a
contenteditable, stop: you have drifted into the expensive design.

## Backend

`web/server.py` — a `BaseHTTPRequestHandler` with a small dict router.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /` | — | `index.html` |
| `GET /static/*` | — | JS and CSS |
| `POST /api/analyze` | `{source}` | `{html, diagnostics, symbols}` |
| `POST /api/complete` | `{source, line, column}` | `{items}` |
| `POST /api/hover` | `{source, line, column}` | `{info}` |

Each handler is a thin adapter over `core/queries.py` (D23): convert line/column to
an offset via `SourceFile`, call the query, serialise. **No feature logic in the
server.**

Analysis is a full re-run per request (D21). Files are small; correctness beats
latency.

Bind to `127.0.0.1` by default. `clens serve --port 8000 [--host]`.

## Front end

Three files under `web/static/`:

- `index.html` — layout: toolbar, editor pane, rendered pane, side panels.
- `app.js` — debounced (~300 ms) POST to `/api/analyze`; render the returned HTML;
  handle clicks, Ctrl+Space, and hover.
- `style.css` — reuse the theme colors from `core/theme.py`. Emit them from Python
  into a generated stylesheet rather than duplicating hex values by hand; a test
  should assert the two agree.

Panels, in value order:

1. **Diagnostics list** — severity icon, message, `line:col`. Click scrolls the
   editor to that position. Also render squiggles in the rendered pane using the
   diagnostic spans.
2. **Symbol tree** — the scope tree, indented, each symbol with kind and type.
   This is the most visually convincing panel for a compiler course; it makes the
   symbol table something a grader can *see*.
3. **Hover card** — click or hover a token in the rendered pane → signature, scope,
   doc comment.
4. **Completion popup** — on typing after `.` / `->`, and on Ctrl+Space. Position
   it from the caret: get `textarea.selectionStart`, convert to line/column
   client-side, and place the popup using a hidden mirror element or simply anchor
   it under the editor. Anchoring under the editor is ugly but works; do that first
   and improve it only if there is time.

## Testing without a socket

Test the handlers directly — build the request object and call the routing function.
No live server, no ports, no flakiness in CI. One test per endpoint plus malformed
JSON, a missing field, and a source that fails to parse.

The front end is not unit tested. Add one end-to-end smoke test that starts the
server on port 0, fetches `/`, and shuts down.

## Screenshots

`docs/images/`, embedded in the README. Take them at the end (P7.7): the highlighted
pane with the symbol tree, a completion popup mid-type, a hover card, and the
diagnostics panel showing a type error. Four images, and the README stops looking
like a CLI tool.

## Definition of done

- [ ] `render/html.py` byte-identical to Phase 1; golden test still green
- [ ] `clens serve` starts, binds locally, serves the page
- [ ] All three API endpoints tested via the handler, plus malformed input
- [ ] Live re-analysis on typing, debounced
- [ ] Diagnostics panel with click-to-jump and inline squiggles
- [ ] Symbol tree panel showing the scope hierarchy
- [ ] Hover card on click
- [ ] Completion popup on `.` and Ctrl+Space
- [ ] Theme colors provably shared with `core/theme.py`, not duplicated
- [ ] Zero runtime dependencies added
- [ ] Four screenshots in the README

// c-lens web UI front end. Vanilla JS, no framework, no build step (D22).
// Talks to /api/analyze, /api/complete, /api/hover, /api/cfg,
// /api/callgraph, /api/dead-code.
"use strict";

(() => {
  const editor = document.getElementById("editor");
  const rendered = document.getElementById("rendered");
  const statusEl = document.getElementById("status");
  const diagnosticsList = document.getElementById("diagnostics-list");
  const symbolTree = document.getElementById("symbol-tree");
  const completionPopup = document.getElementById("completion-popup");
  const hoverCard = document.getElementById("hover-card");

  // Phase 3: CFG / call graph / dead code panels.
  const analysisTabs = document.querySelectorAll(".analysis-tab");
  const analysisPanels = {
    cfg: document.getElementById("analysis-cfg"),
    callgraph: document.getElementById("analysis-callgraph"),
    deadcode: document.getElementById("analysis-deadcode"),
  };
  const functionPicker = document.getElementById("function-picker");
  const cfgGraph = document.getElementById("cfg-graph");
  const callgraphGraph = document.getElementById("callgraph-graph");
  const deadFunctionsList = document.getElementById("dead-functions-list");
  const recursiveFunctionsList = document.getElementById("recursive-functions-list");
  const callersHeading = document.getElementById("callers-heading");
  const callersList = document.getElementById("callers-list");
  const deadCodeList = document.getElementById("dead-code-list");

  let activeAnalysisTab = "cfg";
  let latestFunctionNames = [];
  let latestCallgraphEdges = [];

  const SAMPLE = [
    "struct Point {",
    "    int x;",
    "    int y;",
    "};",
    "",
    "/* Computes n factorial recursively. */",
    "int factorial(int n) {",
    "    return n <= 1 ? 1 : n * factorial(n - 1);",
    "}",
    "",
    "int main(void) {",
    "    struct Point p;",
    "    p.x = factorial(4);",
    "    return 0;",
    "}",
    "",
  ].join("\n");

  let latestDiagnostics = [];
  let debounceTimer = null;
  let completionItems = [];
  let completionActiveIndex = 0;

  // --- position helpers (server speaks 1-based line/column; the DOM only
  // gives us a 0-based caret offset, so this is the one conversion point). ---

  function offsetToLineColumn(text, offset) {
    let line = 1;
    let column = 1;
    const limit = Math.min(offset, text.length);
    for (let i = 0; i < limit; i++) {
      if (text[i] === "\n") {
        line++;
        column = 1;
      } else {
        column++;
      }
    }
    return { line, column };
  }

  function lineColumnToOffset(text, line, column) {
    let offset = 0;
    let currentLine = 1;
    while (currentLine < line) {
      const newline = text.indexOf("\n", offset);
      if (newline === -1) return text.length;
      offset = newline + 1;
      currentLine++;
    }
    return offset + (column - 1);
  }

  async function postJSON(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return response.json();
  }

  // --- analyze: debounced re-run on every keystroke (~300ms) -----------

  function scheduleAnalyze() {
    statusEl.textContent = "analyzing…";
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(analyze, 300);
  }

  async function analyze() {
    const source = editor.value;
    let result;
    try {
      result = await postJSON("/api/analyze", { source });
    } catch (err) {
      statusEl.textContent = "server unreachable";
      return;
    }
    latestDiagnostics = (result.diagnostics || []).map((d) => ({
      ...d,
      startOffset: lineColumnToOffset(source, d.start.line, d.start.column),
      endOffset: lineColumnToOffset(source, d.end.line, d.end.column),
    }));
    rendered.innerHTML = result.html || "";
    applySquiggles();
    renderDiagnostics(latestDiagnostics);
    renderSymbolTree(result.symbols);
    updateFunctionPicker(result.symbols);
    refreshActiveAnalysisTab();
    statusEl.textContent = latestDiagnostics.length
      ? `${latestDiagnostics.length} diagnostic(s)`
      : "no diagnostics";
  }

  function applySquiggles() {
    const spans = rendered.querySelectorAll("span[data-start]");
    for (const span of spans) {
      const start = Number(span.dataset.start);
      const end = Number(span.dataset.end);
      span.classList.remove("diag-error", "diag-warning", "diag-info");
      for (const diag of latestDiagnostics) {
        if (start < diag.endOffset && end > diag.startOffset) {
          span.classList.add(`diag-${diag.severity}`);
        }
      }
    }
  }

  // --- diagnostics panel (click-to-jump) --------------------------------

  function renderDiagnostics(diagnostics) {
    diagnosticsList.innerHTML = "";
    if (!diagnostics.length) {
      const li = document.createElement("li");
      li.textContent = "no diagnostics";
      diagnosticsList.appendChild(li);
      return;
    }
    for (const diag of diagnostics) {
      const li = document.createElement("li");
      const severity = document.createElement("span");
      severity.className = `diag-severity ${diag.severity}`;
      severity.textContent = diag.severity[0].toUpperCase();
      const message = document.createTextNode(` ${diag.message} `);
      const location = document.createElement("span");
      location.className = "diag-location";
      location.textContent = `${diag.start.line}:${diag.start.column}`;
      li.append(severity, message, location);
      li.addEventListener("click", () => jumpTo(diag.start.line, diag.start.column));
      diagnosticsList.appendChild(li);
    }
  }

  function jumpTo(line, column) {
    const offset = lineColumnToOffset(editor.value, line, column);
    editor.focus();
    editor.setSelectionRange(offset, offset);
    const lineHeight = parseFloat(getComputedStyle(editor).lineHeight) || 20;
    editor.scrollTop = Math.max(0, (line - 3) * lineHeight);
  }

  // --- symbol tree panel -------------------------------------------------

  function renderSymbolTree(scope) {
    symbolTree.innerHTML = "";
    if (!scope) return;
    symbolTree.appendChild(buildScopeNode(scope));
  }

  function buildScopeNode(scope) {
    const wrapper = document.createElement("div");
    const kindLabel = document.createElement("div");
    kindLabel.className = "symbol-scope-kind";
    kindLabel.textContent = scope.kind;
    wrapper.appendChild(kindLabel);

    if (scope.symbols.length) {
      const list = document.createElement("ul");
      for (const symbol of scope.symbols) {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.className = "symbol-name";
        name.textContent = symbol.name;
        const detail = document.createElement("span");
        detail.className = "symbol-detail";
        detail.textContent = ` : ${symbol.kind} ${symbol.type}`;
        item.append(name, detail);
        list.appendChild(item);
      }
      wrapper.appendChild(list);
    }

    for (const child of scope.children) {
      wrapper.appendChild(buildScopeNode(child));
    }
    return wrapper;
  }

  // --- hover card ----------------------------------------------------

  rendered.addEventListener("click", async (event) => {
    hideCompletion();
    const span = event.target.closest("span[data-start]");
    if (!span) {
      hideHover();
      return;
    }
    const offset = Number(span.dataset.start);
    const { line, column } = offsetToLineColumn(editor.value, offset);
    const result = await postJSON("/api/hover", { source: editor.value, line, column });
    if (!result.info) {
      hideHover();
      return;
    }
    showHoverCard(result.info);
  });

  function showHoverCard(info) {
    hoverCard.innerHTML = "";
    const sig = document.createElement("div");
    sig.className = "hover-signature";
    sig.textContent = info.signature;
    hoverCard.appendChild(sig);
    const scope = document.createElement("div");
    scope.className = "hover-scope";
    scope.textContent = info.scopeDescription;
    hoverCard.appendChild(scope);
    if (info.docComment) {
      const doc = document.createElement("div");
      doc.className = "hover-doc";
      doc.textContent = info.docComment;
      hoverCard.appendChild(doc);
    }
    hoverCard.classList.remove("hidden");
  }

  function hideHover() {
    hoverCard.classList.add("hidden");
  }

  // --- completion popup ------------------------------------------------
  // Anchored under the editor rather than at the caret (the skill's own
  // "ugly but works, do that first" guidance) - avoids caret-position
  // math against a plain <textarea>.

  editor.addEventListener("input", () => {
    scheduleAnalyze();
    const pos = editor.selectionStart;
    const before = editor.value.slice(Math.max(0, pos - 2), pos);
    if (before.endsWith(".") || before.endsWith("->")) {
      triggerCompletion();
    } else {
      hideCompletion();
    }
  });

  editor.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.code === "Space") {
      event.preventDefault();
      triggerCompletion();
      return;
    }
    if (event.key === "Escape") {
      hideCompletion();
      return;
    }
    if (!completionVisible()) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveCompletionSelection(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      moveCompletionSelection(-1);
    } else if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      applyCompletionSelection();
    }
  });

  async function triggerCompletion() {
    const pos = editor.selectionStart;
    const { line, column } = offsetToLineColumn(editor.value, pos);
    const result = await postJSON("/api/complete", { source: editor.value, line, column });
    completionItems = result.items || [];
    completionActiveIndex = 0;
    renderCompletionPopup();
  }

  function completionVisible() {
    return !completionPopup.classList.contains("hidden");
  }

  function renderCompletionPopup() {
    if (!completionItems.length) {
      hideCompletion();
      return;
    }
    completionPopup.innerHTML = "";
    const list = document.createElement("ul");
    completionItems.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = index === completionActiveIndex ? "active" : "";
      const label = document.createElement("span");
      label.textContent = item.label;
      const kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = `${item.kind}  ${item.detail}`;
      li.append(label, kind);
      li.addEventListener("mousedown", (event) => {
        event.preventDefault();
        completionActiveIndex = index;
        applyCompletionSelection();
      });
      list.appendChild(li);
    });
    completionPopup.appendChild(list);
    completionPopup.classList.remove("hidden");
  }

  function moveCompletionSelection(delta) {
    const count = completionItems.length;
    completionActiveIndex = (completionActiveIndex + delta + count) % count;
    renderCompletionPopup();
  }

  function applyCompletionSelection() {
    const item = completionItems[completionActiveIndex];
    if (!item) return;
    insertCompletion(item.label);
    hideCompletion();
  }

  function insertCompletion(label) {
    const pos = editor.selectionStart;
    const text = editor.value;
    let start = pos;
    while (start > 0 && /[A-Za-z0-9_]/.test(text[start - 1])) {
      start--;
    }
    editor.value = text.slice(0, start) + label + text.slice(pos);
    const newPos = start + label.length;
    editor.setSelectionRange(newPos, newPos);
    editor.focus();
    scheduleAnalyze();
  }

  function hideCompletion() {
    completionPopup.classList.add("hidden");
    completionItems = [];
  }

  // --- program analysis: CFG / call graph / dead code (Phase 3) --------

  function collectFunctionSymbols(scope, out) {
    if (!scope) return out;
    for (const symbol of scope.symbols) {
      if (symbol.kind === "function") out.push(symbol);
    }
    for (const child of scope.children) collectFunctionSymbols(child, out);
    return out;
  }

  function updateFunctionPicker(rootScope) {
    const functions = collectFunctionSymbols(rootScope, []);
    latestFunctionNames = functions.map((f) => f.name);
    const previous = functionPicker.value;
    functionPicker.innerHTML = "";
    for (const name of latestFunctionNames) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      functionPicker.appendChild(option);
    }
    if (latestFunctionNames.includes(previous)) {
      functionPicker.value = previous;
    }
  }

  function switchAnalysisTab(tab) {
    activeAnalysisTab = tab;
    for (const button of analysisTabs) {
      button.classList.toggle("active", button.dataset.tab === tab);
    }
    for (const [name, panel] of Object.entries(analysisPanels)) {
      panel.classList.toggle("hidden", name !== tab);
    }
    refreshActiveAnalysisTab();
  }

  function refreshActiveAnalysisTab() {
    if (activeAnalysisTab === "cfg") refreshCfgPane();
    else if (activeAnalysisTab === "callgraph") refreshCallgraphPane();
    else if (activeAnalysisTab === "deadcode") refreshDeadCodePane();
  }

  for (const button of analysisTabs) {
    button.addEventListener("click", () => switchAnalysisTab(button.dataset.tab));
  }

  functionPicker.addEventListener("change", refreshCfgPane);

  async function refreshCfgPane() {
    const functionName = functionPicker.value;
    if (!functionName) {
      cfgGraph.innerHTML = "<p>No functions with a body in this file.</p>";
      return;
    }
    const result = await postJSON("/api/cfg", { source: editor.value, function: functionName });
    cfgGraph.innerHTML = result.svg || `<p>${result.error || "no graph"}</p>`;
  }

  async function refreshCallgraphPane() {
    const result = await postJSON("/api/callgraph", { source: editor.value });
    callgraphGraph.innerHTML = result.svg || "";
    latestCallgraphEdges = result.edges || [];
    renderPlainList(deadFunctionsList, result.deadFunctions, "(none)");
    renderPlainList(recursiveFunctionsList, result.recursiveFunctions, "(none)");
    callersHeading.textContent = "Callers";
    callersList.innerHTML = "";
    attachCallgraphClickHandler();
  }

  function renderPlainList(listEl, items, emptyText) {
    listEl.innerHTML = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.textContent = emptyText;
      listEl.appendChild(li);
      return;
    }
    for (const item of items) {
      const li = document.createElement("li");
      li.textContent = item;
      listEl.appendChild(li);
    }
  }

  let callgraphClickHandlerAttached = false;

  function attachCallgraphClickHandler() {
    if (callgraphClickHandlerAttached) return;
    callgraphClickHandlerAttached = true;
    callgraphGraph.addEventListener("click", (event) => {
      const group = event.target.closest('g[id^="node-"]');
      if (!group) return;
      const name = group.id.slice("node-".length);
      jumpToFunctionDefinition(name);
      showCallersOf(name);
    });
  }

  function jumpToFunctionDefinition(name) {
    fetchFunctionLocationAndJump(name);
  }

  async function fetchFunctionLocationAndJump(name) {
    const result = await postJSON("/api/analyze", { source: editor.value });
    const functions = collectFunctionSymbols(result.symbols, []);
    const match = functions.find((f) => f.name === name);
    if (match) jumpTo(match.line, match.column);
  }

  function showCallersOf(name) {
    callersHeading.textContent = `Callers of ${name}`;
    const callers = latestCallgraphEdges
      .filter((edge) => edge.callee === name)
      .map((edge) => edge.caller);
    renderPlainList(callersList, callers, "(none)");
  }

  async function refreshDeadCodePane() {
    const result = await postJSON("/api/dead-code", { source: editor.value });
    renderDeadCodeList(result);
  }

  function renderDeadCodeList(report) {
    deadCodeList.innerHTML = "";
    const rows = [];
    for (const name of report.unreachableFunctions || []) {
      rows.push({ severity: "warning", text: `unreachable function: ${name}` });
    }
    for (const b of report.unreachableBlocks || []) {
      rows.push({ severity: "warning", text: `unreachable block ${b.block} in ${b.function}` });
    }
    for (const p of report.postJumpStatements || []) {
      rows.push({
        severity: "warning",
        text: `${p.function}: unreachable: ${p.text}`,
        line: p.line,
        column: p.col,
      });
    }
    for (const u of report.unusedVariables || []) {
      rows.push({
        severity: "info",
        text: `${u.function}: unused variable '${u.name}'`,
        line: u.line,
        column: 1,
      });
    }
    for (const d of report.deadAssignments || []) {
      rows.push({
        severity: "warning",
        text: `${d.function}: dead assignment to '${d.name}'`,
        line: d.line,
        column: d.col,
      });
    }
    if (!rows.length) {
      const li = document.createElement("li");
      li.textContent = "no dead code found";
      deadCodeList.appendChild(li);
      return;
    }
    for (const row of rows) {
      const li = document.createElement("li");
      const severity = document.createElement("span");
      severity.className = `diag-severity ${row.severity}`;
      severity.textContent = row.severity[0].toUpperCase();
      const message = document.createTextNode(` ${row.text} `);
      li.append(severity, message);
      if (row.line) {
        const location = document.createElement("span");
        location.className = "diag-location";
        location.textContent = `${row.line}:${row.column || 1}`;
        li.appendChild(location);
        li.addEventListener("click", () => jumpTo(row.line, row.column || 1));
        li.style.cursor = "pointer";
      }
      deadCodeList.appendChild(li);
    }
  }

  // --- boot ------------------------------------------------------------

  editor.value = SAMPLE;
  analyze();
})();

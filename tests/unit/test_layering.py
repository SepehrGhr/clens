"""D12 — src/clens/core/** must never import from clens.languages."""

import ast
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2] / "src" / "clens" / "core"


def _imports_languages(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any("languages" in alias.name.split(".") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "languages" in module.split("."):
                return True
    return False


def test_core_never_imports_languages():
    offenders = [str(path) for path in CORE_ROOT.rglob("*.py") if _imports_languages(path)]
    assert not offenders, f"core/ must not import from languages/: {offenders}"


def test_detector_catches_absolute_and_relative_violations(tmp_path):
    """Guard against the checker itself going blind (D12 is enforced, not aspirational)."""
    absolute = tmp_path / "absolute.py"
    absolute.write_text("from clens.languages.c import keywords\n")
    relative = tmp_path / "relative.py"
    relative.write_text("from ..languages.c import keywords\n")
    plain_import = tmp_path / "plain_import.py"
    plain_import.write_text("import clens.languages.c.keywords\n")
    clean = tmp_path / "clean.py"
    clean.write_text("from clens.core.token import Token\n")

    assert _imports_languages(absolute) is True
    assert _imports_languages(relative) is True
    assert _imports_languages(plain_import) is True
    assert _imports_languages(clean) is False

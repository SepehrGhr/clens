"""Shared pytest fixtures: locating and reading files under tests/fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_path() -> Path:
    """Root directory of the seeded .c test fixtures."""
    return FIXTURES_ROOT


def read_fixture(relative_path: str) -> str:
    """Read a fixture file's text given a path relative to tests/fixtures/."""
    return (FIXTURES_ROOT / relative_path).read_text()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Regenerate tests/golden/expected/ files instead of comparing against them.",
    )


@pytest.fixture
def golden(request: pytest.FixtureRequest):
    """`golden(path, actual)`: compare `actual` against `path`'s contents,
    or overwrite `path` with `actual` when run with `--regen-golden`.
    Always eyeball a regenerated file before committing it — a snapshot
    that is blindly regenerated tests nothing.
    """
    regen = request.config.getoption("--regen-golden")

    def _check(path: Path, actual: str) -> None:
        if regen:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual)
            return
        expected = path.read_text()
        assert actual == expected, f"{path} does not match; run with --regen-golden to update"

    return _check

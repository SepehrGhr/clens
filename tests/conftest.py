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

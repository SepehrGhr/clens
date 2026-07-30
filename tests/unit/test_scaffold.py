"""Trivial smoke test so CI is green before any real modules exist."""

import clens


def test_package_imports():
    assert clens.__doc__

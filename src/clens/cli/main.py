"""clens command-line entry point.

Subcommands (tokens, ast, highlight, check) are added in Stage 6; for now this
only wires up ``--help`` and a clean exit so packaging and Docker can be
verified end to end.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    return argparse.ArgumentParser(
        prog="clens",
        description="A code-aware IDE feature set for a subset of C.",
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point registered as the ``clens`` console script."""
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the CLI entry point stub (full subcommands land in Stage 6)."""

import pytest

from clens.cli.main import build_parser, main


def test_main_with_no_args_exits_zero():
    assert main([]) == 0


def test_help_flag_prints_usage_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    assert "usage: clens" in capsys.readouterr().out


def test_build_parser_prog_name():
    assert build_parser().prog == "clens"

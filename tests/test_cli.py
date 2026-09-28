from __future__ import annotations

from typer.testing import CliRunner

from cumap.cli import app

runner = CliRunner()

EXPECTED_GROUPS = [
    "data",
    "textbook",
    "gold",
    "labels",
    "kg",
    "student",
    "diagnose",
    "eval",
    "app",
]


def test_help_lists_all_command_groups():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in EXPECTED_GROUPS:
        assert group in result.output

"""Integration tests for DropSort CLI interface."""

from pathlib import Path
import tempfile
import pytest

from dropsort.cli import run_cli


def test_cli_list_rules(capsys):
    handled = run_cli(["--list-rules"])
    assert handled is True
    captured = capsys.readouterr()
    assert "Invoices & Receipts" in captured.out
    assert "Photos by Year" in captured.out


def test_cli_simulate(capsys):
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "invoice_august.pdf").write_text("dummy")
        (p / "holiday.jpg").write_text("dummy")

        handled = run_cli(["--simulate", "--path", str(p)])
        assert handled is True
        captured = capsys.readouterr()
        assert "invoice_august.pdf" in captured.out
        assert "Simulation Summary" in captured.out
        assert "Dry run mode" in captured.out


def test_cli_run_and_undo(capsys):
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        f = p / "invoice_test.pdf"
        f.write_text("dummy invoice content")

        handled = run_cli(["--run", "--path", str(p)])
        assert handled is True
        captured = capsys.readouterr()
        assert "Organization Complete!" in captured.out

        # Verify moved
        assert not f.exists()

        # Test CLI undo
        undo_handled = run_cli(["--undo", "last"])
        assert undo_handled is True
        captured_undo = capsys.readouterr()
        assert "Successfully restored" in captured_undo.out
        assert f.exists()


def test_cli_no_args_returns_false():
    handled = run_cli([])
    assert handled is False  # Instructs main to launch GUI

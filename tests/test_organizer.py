"""Unit and integration tests for DropSort Organizer, duplicate resolver, and undo engine."""

from datetime import datetime
from pathlib import Path
import tempfile
import pytest

from dropsort.config import get_default_rules
from dropsort.database import Database
from dropsort.models import (
    Action,
    Condition,
    ConditionField,
    ConditionGroup,
    ConditionOp,
    DuplicateAction,
    FileActionType,
    PlanItemStatus,
    Rule,
)
from dropsort.organizer import (
    create_preview,
    execute_plan,
    resolve_duplicate_filename,
    scan_folder,
    undo_batch,
    undo_move_record,
)
from dropsort.rule_engine import RuleEngine


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_scan_folder_and_ignore(temp_workspace):
    # Create sample files
    (temp_workspace / "photo.jpg").write_text("photo data")
    (temp_workspace / "invoice.pdf").write_text("invoice data")
    (temp_workspace / "download.tmp").write_text("temp data")
    (temp_workspace / ".hidden_file").write_text("hidden data")

    files, ignored = scan_folder(temp_workspace, recursive=False, ignored_patterns=["*.tmp"])
    file_names = [f.name for f in files]

    assert "photo.jpg" in file_names
    assert "invoice.pdf" in file_names
    assert "download.tmp" not in file_names
    assert ".hidden_file" not in file_names
    assert ignored >= 2


def test_duplicate_resolution_rename(temp_workspace):
    target = temp_workspace / "Documents" / "report.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing file")

    allocated = set()
    # First collision on disk
    res1, is_dup1 = resolve_duplicate_filename(target, allocated, DuplicateAction.RENAME)
    assert is_dup1 is True
    assert res1.name == "report (1).pdf"
    allocated.add(str(res1.resolve()))

    # Second collision within allocated set
    res2, is_dup2 = resolve_duplicate_filename(target, allocated, DuplicateAction.RENAME)
    assert is_dup2 is True
    assert res2.name == "report (2).pdf"


def test_duplicate_resolution_skip(temp_workspace):
    target = temp_workspace / "Documents" / "report.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing file")

    allocated = set()
    res, is_dup = resolve_duplicate_filename(target, allocated, DuplicateAction.SKIP)
    assert is_dup is True
    assert res.name == "report.pdf"


def test_execute_plan_and_undo(temp_workspace):
    src_folder = temp_workspace / "Downloads"
    src_folder.mkdir(parents=True, exist_ok=True)

    db_path = temp_workspace / "test.db"
    db = Database(db_path)

    # Create dummy files
    f1 = src_folder / "invoice_2026.pdf"
    f1.write_text("invoice pdf contents")
    f2 = src_folder / "song.mp3"
    f2.write_text("music audio bytes")

    rules = [
        Rule(
            name="Invoices",
            priority=10,
            conditions=ConditionGroup(
                conditions=[Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf")]
            ),
            action=Action(destination="Documents/Invoices/"),
        ),
        Rule(
            name="Music",
            priority=20,
            conditions=ConditionGroup(
                conditions=[Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "mp3")]
            ),
            action=Action(destination="Music/"),
        ),
    ]

    engine = RuleEngine(rules)
    files, _ = scan_folder(src_folder)
    plan = create_preview(files, engine, src_folder)

    assert len(plan.items) == 2
    assert plan.ready_count == 2

    # Execute
    res = execute_plan(plan, db)
    assert res["executed"] == 2
    assert res["failed"] == 0

    target_inv = src_folder / "Documents" / "Invoices" / "invoice_2026.pdf"
    target_mp3 = src_folder / "Music" / "song.mp3"

    assert target_inv.exists()
    assert target_mp3.exists()
    assert not f1.exists()
    assert not f2.exists()

    # Verify History logged in DB
    history = db.get_history(batch_id=res["batch_id"])
    assert len(history) == 2

    # Perform Undo Entire Batch
    undo_res = undo_batch(res["batch_id"], db, clean_empty_parents=True)
    assert undo_res["undone"] == 2
    assert undo_res["failed"] == 0

    # Original files should be restored
    assert f1.exists()
    assert f2.exists()
    assert not target_inv.exists()
    assert not target_mp3.exists()

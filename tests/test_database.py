"""Unit tests for SQLite Database layer."""

from datetime import datetime
from pathlib import Path
import tempfile
import pytest

from dropsort.database import Database
from dropsort.models import MoveRecord, MoveRecordStatus


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_dropsort.db"
        yield Database(db_path)


def test_batch_creation_and_retrieval(temp_db):
    batch = temp_db.create_batch(target_folder="/test/folder", total_moves=5)
    assert batch.id is not None
    assert batch.total_moves == 5
    assert batch.status == "completed"

    fetched = temp_db.get_batch(batch.id)
    assert fetched is not None
    assert fetched.target_folder == "/test/folder"

    latest = temp_db.get_latest_batch()
    assert latest is not None
    assert latest.id == batch.id


def test_history_logging_and_undo_status(temp_db):
    batch = temp_db.create_batch(target_folder="/test/folder", total_moves=1)

    record = MoveRecord(
        id="m1",
        batch_id=batch.id,
        original_path="/test/folder/a.pdf",
        target_path="/test/folder/Documents/a.pdf",
        file_size=1024,
        rule_name="PDFs",
        action_type="move",
        status=MoveRecordStatus.COMPLETED,
        timestamp=datetime.now(),
    )

    temp_db.log_moves([record])

    history = temp_db.get_history(batch_id=batch.id)
    assert len(history) == 1
    assert history[0].id == "m1"
    assert history[0].status == MoveRecordStatus.COMPLETED

    # Mark as undone
    assert temp_db.mark_move_undone("m1") is True

    # Re-fetch
    updated = temp_db.get_move("m1")
    assert updated.status == MoveRecordStatus.UNDONE

    # Check batch status auto-updated to undone
    updated_batch = temp_db.get_batch(batch.id)
    assert updated_batch.status == "undone"
    assert updated_batch.undone_count == 1


def test_stats_today(temp_db):
    batch = temp_db.create_batch(target_folder="/test/folder", total_moves=2)
    records = [
        MoveRecord(
            id=f"rec-{i}",
            batch_id=batch.id,
            original_path=f"/test/folder/{i}.pdf",
            target_path=f"/test/folder/Documents/{i}.pdf",
            file_size=1024,
            rule_name="PDFs",
            action_type="move",
            status=MoveRecordStatus.COMPLETED,
            timestamp=datetime.now(),
        )
        for i in range(2)
    ]
    temp_db.log_moves(records)

    stats = temp_db.get_stats_today()
    assert stats["organized_today"] == 2
    assert stats["bytes_today"] == 2048
    assert stats["batches_today"] >= 1

"""SQLite database layer for history logging, session batches, and 1-click undo state."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dropsort.config import get_app_data_dir
from dropsort.models import BatchRecord, MoveRecord, MoveRecordStatus, Rule


class Database:
    """Thread-safe SQLite database manager for DropSort."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            self.db_path = get_app_data_dir() / "dropsort.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextlib.contextmanager
    def _get_connection(self):
        """Create a new connection with Row factory and guarantee closing."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_tables(self) -> None:
        """Initialize database schema and indices."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Batches table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    target_folder TEXT NOT NULL,
                    total_moves INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    undone_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            # Move history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    rule_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    timestamp TEXT NOT NULL,
                    error_message TEXT DEFAULT '',
                    FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
                )
                """
            )

            # Rules table (optional DB sync)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Indices for lightning-fast queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_batch ON history(batch_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_status ON history(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_timestamp ON batches(timestamp)")
            conn.commit()

    # --- Batch Operations ---

    def create_batch(self, target_folder: str, total_moves: int, batch_id: Optional[str] = None) -> BatchRecord:
        """Register a new organization batch session."""
        bid = batch_id or str(uuid.uuid4())
        now = datetime.now()
        record = BatchRecord(
            id=bid,
            target_folder=target_folder,
            total_moves=total_moves,
            timestamp=now,
            status="completed",
            undone_count=0,
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO batches (id, target_folder, total_moves, timestamp, status, undone_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (record.id, record.target_folder, record.total_moves, record.timestamp.isoformat(), record.status, record.undone_count),
            )
            conn.commit()
        return record

    def get_batches(self, limit: int = 50) -> List[BatchRecord]:
        """Fetch list of recent batches."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM batches ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            return [
                BatchRecord(
                    id=row["id"],
                    target_folder=row["target_folder"],
                    total_moves=row["total_moves"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    status=row["status"],
                    undone_count=row["undone_count"],
                )
                for row in rows
            ]

    def get_batch(self, batch_id: str) -> Optional[BatchRecord]:
        """Fetch a single batch record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return BatchRecord(
                id=row["id"],
                target_folder=row["target_folder"],
                total_moves=row["total_moves"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                status=row["status"],
                undone_count=row["undone_count"],
            )

    def get_latest_batch(self) -> Optional[BatchRecord]:
        """Fetch the most recent batch record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batches ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return BatchRecord(
                id=row["id"],
                target_folder=row["target_folder"],
                total_moves=row["total_moves"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                status=row["status"],
                undone_count=row["undone_count"],
            )

    # --- History & Move Operations ---

    def log_moves(self, records: List[MoveRecord]) -> None:
        """Batch insert executed move records."""
        if not records:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            params = [
                (
                    r.id,
                    r.batch_id,
                    r.original_path,
                    r.target_path,
                    r.file_size,
                    r.rule_name,
                    r.action_type,
                    r.status.value if isinstance(r.status, MoveRecordStatus) else str(r.status),
                    r.timestamp.isoformat(),
                    r.error_message,
                )
                for r in records
            ]
            cursor.executemany(
                """
                INSERT INTO history (
                    id, batch_id, original_path, target_path, file_size,
                    rule_name, action_type, status, timestamp, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            conn.commit()

    def get_history(
        self,
        batch_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MoveRecord]:
        """Retrieve move history with optional filters."""
        query = "SELECT * FROM history WHERE 1=1"
        params: List[Any] = []

        if batch_id:
            query += " AND batch_id = ?"
            params.append(batch_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if search:
            query += " AND (original_path LIKE ? OR target_path LIKE ? OR rule_name LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                MoveRecord(
                    id=row["id"],
                    batch_id=row["batch_id"],
                    original_path=row["original_path"],
                    target_path=row["target_path"],
                    file_size=row["file_size"],
                    rule_name=row["rule_name"],
                    action_type=row["action_type"],
                    status=MoveRecordStatus(row["status"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    error_message=row["error_message"] or "",
                )
                for row in rows
            ]

    def get_move(self, move_id: str) -> Optional[MoveRecord]:
        """Fetch a single move record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history WHERE id = ?", (move_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return MoveRecord(
                id=row["id"],
                batch_id=row["batch_id"],
                original_path=row["original_path"],
                target_path=row["target_path"],
                file_size=row["file_size"],
                rule_name=row["rule_name"],
                action_type=row["action_type"],
                status=MoveRecordStatus(row["status"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                error_message=row["error_message"] or "",
            )

    def mark_move_undone(self, move_id: str) -> bool:
        """Mark a move record as undone and increment batch undone counter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT batch_id, status FROM history WHERE id = ?", (move_id,))
            row = cursor.fetchone()
            if not row or row["status"] == "undone":
                return False

            batch_id = row["batch_id"]
            cursor.execute(
                "UPDATE history SET status = 'undone' WHERE id = ?", (move_id,)
            )
            cursor.execute(
                "UPDATE batches SET undone_count = undone_count + 1 WHERE id = ?", (batch_id,)
            )
            # Check if all items in batch are undone
            cursor.execute("SELECT total_moves, undone_count FROM batches WHERE id = ?", (batch_id,))
            b_row = cursor.fetchone()
            if b_row and b_row["undone_count"] >= b_row["total_moves"]:
                cursor.execute("UPDATE batches SET status = 'undone' WHERE id = ?", (batch_id,))
            conn.commit()
            return True

    def mark_batch_undone(self, batch_id: str) -> int:
        """Mark all records in a batch as undone."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE history SET status = 'undone' WHERE batch_id = ? AND status = 'completed'",
                (batch_id,),
            )
            count = cursor.rowcount
            cursor.execute(
                "UPDATE batches SET status = 'undone', undone_count = total_moves WHERE id = ?",
                (batch_id,),
            )
            conn.commit()
            return count

    # --- Metrics & Stats ---

    def get_stats_today(self) -> Dict[str, Any]:
        """Get aggregate counts for today."""
        today_str = date.today().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as organized_count, COALESCE(SUM(file_size), 0) as total_bytes
                FROM history
                WHERE timestamp >= ? AND status = 'completed'
                """,
                (today_str,),
            )
            row = cursor.fetchone()
            org_count = row["organized_count"] if row else 0
            total_bytes = row["total_bytes"] if row else 0

            cursor.execute("SELECT COUNT(*) as total_batches FROM batches WHERE timestamp >= ?", (today_str,))
            b_row = cursor.fetchone()
            total_batches = b_row["total_batches"] if b_row else 0

            return {
                "organized_today": org_count,
                "bytes_today": total_bytes,
                "batches_today": total_batches,
            }

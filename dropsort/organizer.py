"""File scanning, preview planning, duplicate resolution, execution, and undo engine."""

from __future__ import annotations

import fnmatch
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

from dropsort.database import Database
from dropsort.models import (
    BatchRecord,
    DuplicateAction,
    FileActionType,
    FileMetadata,
    MoveRecord,
    MoveRecordStatus,
    PlanItem,
    PlanItemStatus,
    PreviewPlan,
    Rule,
)
from dropsort.rule_engine import RuleEngine


def should_ignore(path: Path, ignored_patterns: Optional[List[str]] = None) -> bool:
    """Check if a file or path matches ignore filters."""
    if not ignored_patterns:
        ignored_patterns = ["*.tmp", "*.crdownload", "*.part", "*.download", ".git", ".DS_Store", "Thumbs.db", "~$*"]

    name = path.name
    # Ignore hidden files on Unix/Windows
    if name.startswith(".") and name not in [".", ".."]:
        return True

    for pattern in ignored_patterns:
        if fnmatch.fnmatch(name.lower(), pattern.lower()):
            return True
        if pattern in str(path):
            return True
    return False


def scan_folder(
    folder_path: Union[str, Path],
    recursive: bool = False,
    ignored_patterns: Optional[List[str]] = None,
) -> Tuple[List[FileMetadata], int]:
    """Scan folder for files and extract rich metadata. Returns (file_list, ignored_count)."""
    p = Path(folder_path).resolve()
    if not p.exists() or not p.is_dir():
        return [], 0

    files: List[FileMetadata] = []
    ignored_count = 0

    if recursive:
        iterator = p.rglob("*")
    else:
        iterator = p.iterdir()

    for item in iterator:
        try:
            if not item.is_file():
                continue
            if should_ignore(item, ignored_patterns):
                ignored_count += 1
                continue

            meta = FileMetadata.from_path(item)
            files.append(meta)
        except (PermissionError, OSError):
            ignored_count += 1

    return files, ignored_count


def resolve_duplicate_filename(
    target_path: Path,
    allocated_paths: Set[str],
    strategy: DuplicateAction,
) -> Tuple[Path, bool]:
    """
    Resolve target path conflicts given existing files on disk and paths already allocated in this batch.
    Returns (final_target_path, was_duplicate).
    """
    target_str = str(target_path.resolve())
    exists_on_disk = target_path.exists()
    already_allocated = target_str in allocated_paths

    if not exists_on_disk and not already_allocated:
        return target_path, False

    # A duplicate conflict exists
    if strategy == DuplicateAction.SKIP:
        return target_path, True

    if strategy == DuplicateAction.REPLACE:
        return target_path, True

    # strategy == DuplicateAction.RENAME: Generate filename (1).ext, (2).ext
    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix

    counter = 1
    while True:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = parent / candidate_name
        candidate_str = str(candidate_path.resolve())

        if not candidate_path.exists() and candidate_str not in allocated_paths:
            return candidate_path, True
        counter += 1


def create_preview(
    files: List[FileMetadata],
    rule_engine: RuleEngine,
    base_folder: Path,
    default_strategy: DuplicateAction = DuplicateAction.RENAME,
) -> PreviewPlan:
    """Generate a PreviewPlan mapping files to target destinations with duplicate resolution."""
    items: List[PlanItem] = []
    allocated_paths: Set[str] = set()

    for meta in files:
        match_res = rule_engine.plan_file(meta, base_folder)
        if match_res is None:
            # File did not match any active rule
            continue

        rule, initial_target = match_res
        strategy = (
            rule.action.on_duplicate
            if isinstance(rule.action.on_duplicate, DuplicateAction)
            else DuplicateAction(str(rule.action.on_duplicate).lower())
        )

        final_target, is_dup = resolve_duplicate_filename(initial_target, allocated_paths, strategy)

        # Check if source and target are the same file
        if meta.path.resolve() == final_target.resolve():
            status = PlanItemStatus.SKIPPED
            reason = "File is already in target destination"
        elif is_dup and strategy == DuplicateAction.SKIP:
            status = PlanItemStatus.SKIPPED
            reason = "Destination exists (Skipped by rule policy)"
        elif is_dup and strategy == DuplicateAction.REPLACE:
            status = PlanItemStatus.CONFLICT
            reason = "Overwriting existing destination file"
            allocated_paths.add(str(final_target.resolve()))
        elif is_dup and strategy == DuplicateAction.RENAME:
            status = PlanItemStatus.READY
            reason = f"Renamed duplicate to '{final_target.name}'"
            allocated_paths.add(str(final_target.resolve()))
        else:
            status = PlanItemStatus.READY
            reason = "Ready to organize"
            allocated_paths.add(str(final_target.resolve()))

        action_type = (
            rule.action.action_type
            if isinstance(rule.action.action_type, FileActionType)
            else FileActionType(str(rule.action.action_type).lower())
        )

        item = PlanItem(
            file_meta=meta,
            target_path=final_target,
            rule_id=rule.id,
            rule_name=rule.name,
            action_type=action_type,
            on_duplicate=strategy,
            status=status,
            is_duplicate=is_dup,
            original_target_path=initial_target,
            reason=reason,
            selected=(status in (PlanItemStatus.READY, PlanItemStatus.CONFLICT)),
        )
        items.append(item)

    return PreviewPlan(
        items=items,
        base_folder=base_folder,
        total_files_scanned=len(files),
    )


def execute_plan(
    plan: PreviewPlan,
    database: Database,
    progress_callback: Optional[Callable[[int, int, PlanItem, bool, str], None]] = None,
) -> Dict[str, Any]:
    """
    Execute selected actions from a PreviewPlan and record history in the Database.
    Returns summary statistics.
    """
    actionable = [item for item in plan.items if item.selected and item.status != PlanItemStatus.SKIPPED]
    if not actionable:
        return {"batch_id": None, "executed": 0, "failed": 0, "skipped": len(plan.items)}

    batch_id = str(uuid.uuid4())
    batch = database.create_batch(
        target_folder=str(plan.base_folder),
        total_moves=len(actionable),
        batch_id=batch_id,
    )

    records: List[MoveRecord] = []
    executed_count = 0
    failed_count = 0

    for idx, item in enumerate(actionable, start=1):
        src = item.source_path
        dst = item.target_path
        rec_id = str(uuid.uuid4())
        success = False
        err_msg = ""

        try:
            if not src.exists():
                raise FileNotFoundError(f"Source file not found: {src}")

            # Ensure destination directory exists
            dst.parent.mkdir(parents=True, exist_ok=True)

            if item.action_type == FileActionType.COPY:
                shutil.copy2(src, dst)
            else:
                shutil.move(str(src), str(dst))

            success = True
            executed_count += 1

            records.append(
                MoveRecord(
                    id=rec_id,
                    batch_id=batch_id,
                    original_path=str(src),
                    target_path=str(dst),
                    file_size=item.file_meta.size_bytes,
                    rule_name=item.rule_name,
                    action_type=item.action_type.value,
                    status=MoveRecordStatus.COMPLETED,
                    timestamp=datetime.now(),
                    error_message="",
                )
            )
        except Exception as e:
            failed_count += 1
            err_msg = str(e)
            records.append(
                MoveRecord(
                    id=rec_id,
                    batch_id=batch_id,
                    original_path=str(src),
                    target_path=str(dst),
                    file_size=item.file_meta.size_bytes,
                    rule_name=item.rule_name,
                    action_type=item.action_type.value,
                    status=MoveRecordStatus.FAILED,
                    timestamp=datetime.now(),
                    error_message=err_msg,
                )
            )

        if progress_callback:
            progress_callback(idx, len(actionable), item, success, err_msg)

    # Batch insert to DB
    database.log_moves(records)

    return {
        "batch_id": batch_id,
        "executed": executed_count,
        "failed": failed_count,
        "total": len(actionable),
    }


def clean_empty_directories(path: Path, stop_at: Path) -> None:
    """Recursively remove empty parent directories up to stop_at boundary."""
    try:
        curr = path
        stop_resolved = stop_at.resolve()
        while curr.resolve() != stop_resolved and curr.resolve() != curr.parent.resolve():
            if curr.exists() and curr.is_dir() and not any(curr.iterdir()):
                curr.rmdir()
                curr = curr.parent
            else:
                break
    except Exception:
        pass


def undo_move_record(
    record_id: str,
    database: Database,
    clean_empty_parents: bool = True,
) -> Tuple[bool, str]:
    """Undo a single file move action."""
    rec = database.get_move(record_id)
    if not rec:
        return False, "Record not found in database."

    if rec.status == MoveRecordStatus.UNDONE:
        return False, "This action has already been undone."

    curr_path = Path(rec.target_path)
    orig_path = Path(rec.original_path)

    if not curr_path.exists():
        return False, f"File no longer exists at target path: {curr_path}"

    try:
        orig_path.parent.mkdir(parents=True, exist_ok=True)
        if orig_path.exists():
            # If original path exists, rename restore
            orig_parent = orig_path.parent
            stem = orig_path.stem
            suffix = orig_path.suffix
            c = 1
            while orig_path.exists():
                orig_path = orig_parent / f"{stem} (restored {c}){suffix}"
                c += 1

        shutil.move(str(curr_path), str(orig_path))

        if clean_empty_parents:
            clean_empty_directories(curr_path.parent, curr_path.parent.parent.parent)

        database.mark_move_undone(rec.id)
        return True, f"Restored to {orig_path}"
    except Exception as e:
        return False, f"Undo failed: {e}"


def undo_batch(
    batch_id: str,
    database: Database,
    clean_empty_parents: bool = True,
) -> Dict[str, Any]:
    """Undo all completed moves in an entire batch session."""
    history = database.get_history(batch_id=batch_id, status="completed")
    if not history:
        return {"batch_id": batch_id, "undone": 0, "failed": 0, "total": 0}

    undone_count = 0
    failed_count = 0
    errors: List[str] = []

    # Reverse order of actions
    for rec in reversed(history):
        success, msg = undo_move_record(rec.id, database, clean_empty_parents)
        if success:
            undone_count += 1
        else:
            failed_count += 1
            errors.append(f"{rec.target_path}: {msg}")

    return {
        "batch_id": batch_id,
        "undone": undone_count,
        "failed": failed_count,
        "total": len(history),
        "errors": errors,
    }

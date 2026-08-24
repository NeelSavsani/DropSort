"""Data models and entity definitions for DropSort."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DuplicateAction(str, Enum):
    """Strategy for handling filename collisions at destination."""

    RENAME = "rename"
    REPLACE = "replace"
    SKIP = "skip"


class FileActionType(str, Enum):
    """File operation type."""

    MOVE = "move"
    COPY = "copy"


class LogicalOp(str, Enum):
    """Logical operator for combining conditions."""

    AND = "AND"
    OR = "OR"


class ConditionField(str, Enum):
    """Supported fields for rule evaluation."""

    EXTENSION = "extension"
    FILENAME = "filename"
    FILENAME_REGEX = "filename_regex"
    FILENAME_GLOB = "filename_glob"
    FILE_TYPE = "file_type"
    SIZE_BYTES = "size_bytes"
    DATE_MODIFIED = "date_modified"
    DATE_CREATED = "date_created"


class ConditionOp(str, Enum):
    """Supported condition operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES_REGEX = "matches_regex"
    MATCHES_GLOB = "matches_glob"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    WITHIN_DAYS = "within_days"
    BEFORE_DATE = "before_date"
    AFTER_DATE = "after_date"


class FileCategory(str, Enum):
    """Standard file categories."""

    IMAGES = "Images"
    DOCUMENTS = "Documents"
    SPREADSHEETS = "Spreadsheets"
    PRESENTATIONS = "Presentations"
    AUDIO = "Audio"
    VIDEOS = "Videos"
    ARCHIVES = "Archives"
    CODE = "Code"
    APPLICATIONS = "Applications"
    OTHER = "Other"


CATEGORY_EXTENSIONS: Dict[FileCategory, set[str]] = {
    FileCategory.IMAGES: {
        "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "tiff", "tif", "heic", "heif", "raw", "cr2", "nef"
    },
    FileCategory.DOCUMENTS: {
        "pdf", "doc", "docx", "txt", "rtf", "odt", "pages", "epub", "mobi", "md", "tex", "wpd"
    },
    FileCategory.SPREADSHEETS: {
        "xlsx", "xls", "csv", "tsv", "ods", "numbers", "xlsm"
    },
    FileCategory.PRESENTATIONS: {
        "pptx", "ppt", "odp", "key", "pps", "ppsx"
    },
    FileCategory.AUDIO: {
        "mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "aiff", "opus", "mid", "midi"
    },
    FileCategory.VIDEOS: {
        "mp4", "mkv", "mov", "avi", "webm", "wmv", "flv", "m4v", "mpg", "mpeg", "3gp", "ts"
    },
    FileCategory.ARCHIVES: {
        "zip", "tar", "gz", "tgz", "7z", "rar", "bz2", "xz", "iso", "dmg", "pkg"
    },
    FileCategory.CODE: {
        "py", "js", "ts", "jsx", "tsx", "html", "htm", "css", "scss", "sass", "less",
        "json", "yaml", "yml", "xml", "cpp", "c", "h", "hpp", "cs", "java", "rs", "go",
        "php", "rb", "sql", "sh", "bash", "bat", "ps1", "lua", "swift", "kt"
    },
    FileCategory.APPLICATIONS: {
        "exe", "msi", "app", "deb", "rpm", "apk", "jar"
    },
}


@dataclass
class Condition:
    """A single conditional expression evaluated against a file."""

    field: Union[ConditionField, str]
    operator: Union[ConditionOp, str]
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field.value if isinstance(self.field, ConditionField) else str(self.field),
            "operator": self.operator.value if isinstance(self.operator, ConditionOp) else str(self.operator),
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Condition:
        field_val = data.get("field", "extension")
        try:
            field_enum = ConditionField(field_val)
        except ValueError:
            field_enum = field_val

        op_val = data.get("operator", "equals")
        try:
            op_enum = ConditionOp(op_val)
        except ValueError:
            op_enum = op_val

        return cls(
            field=field_enum,
            operator=op_enum,
            value=data.get("value", ""),
        )


@dataclass
class ConditionGroup:
    """A group of conditions evaluated with AND or OR logic."""

    logical_operator: Union[LogicalOp, str] = LogicalOp.AND
    conditions: List[Union[Condition, ConditionGroup]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "logical_operator": (
                self.logical_operator.value
                if isinstance(self.logical_operator, LogicalOp)
                else str(self.logical_operator)
            ),
            "conditions": [
                c.to_dict() for c in self.conditions
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConditionGroup:
        log_op = data.get("logical_operator", "AND").upper()
        try:
            log_enum = LogicalOp(log_op)
        except ValueError:
            log_enum = LogicalOp.AND

        conds: List[Union[Condition, ConditionGroup]] = []
        raw_conds = data.get("conditions", [])

        # Backward compatibility / simplified 'when' dict formats:
        # e.g., {"extension": "pdf", "filename_contains": "invoice"}
        if isinstance(raw_conds, dict):
            raw_conds = [raw_conds]

        for item in raw_conds:
            if "conditions" in item:
                conds.append(cls.from_dict(item))
            elif "field" in item:
                conds.append(Condition.from_dict(item))
            else:
                # Shortcut syntax like {"extension": "pdf"} or {"extension": ["jpg", "png"]}
                for k, v in item.items():
                    if k == "extension":
                        if isinstance(v, list):
                            conds.append(Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, v))
                        else:
                            conds.append(Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, v))
                    elif k == "filename_contains":
                        conds.append(Condition(ConditionField.FILENAME, ConditionOp.CONTAINS, v))
                    elif k == "filename_regex":
                        conds.append(Condition(ConditionField.FILENAME_REGEX, ConditionOp.MATCHES_REGEX, v))
                    elif k == "filename_glob":
                        conds.append(Condition(ConditionField.FILENAME_GLOB, ConditionOp.MATCHES_GLOB, v))
                    elif k == "file_type":
                        conds.append(Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, v))
                    elif k == "size_greater_than":
                        conds.append(Condition(ConditionField.SIZE_BYTES, ConditionOp.GREATER_THAN, v))
                    elif k == "size_less_than":
                        conds.append(Condition(ConditionField.SIZE_BYTES, ConditionOp.LESS_THAN, v))
                    elif k == "modified_within_days":
                        conds.append(Condition(ConditionField.DATE_MODIFIED, ConditionOp.WITHIN_DAYS, v))

        return cls(logical_operator=log_enum, conditions=conds)


@dataclass
class Action:
    """Action to perform when a rule matches."""

    destination: str
    action_type: Union[FileActionType, str] = FileActionType.MOVE
    on_duplicate: Union[DuplicateAction, str] = DuplicateAction.RENAME
    create_subfolders: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "action_type": (
                self.action_type.value
                if isinstance(self.action_type, FileActionType)
                else str(self.action_type)
            ),
            "on_duplicate": (
                self.on_duplicate.value
                if isinstance(self.on_duplicate, DuplicateAction)
                else str(self.on_duplicate)
            ),
            "create_subfolders": self.create_subfolders,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Action:
        action_type_val = data.get("action_type", "move")
        try:
            action_type_enum = FileActionType(action_type_val)
        except ValueError:
            action_type_enum = FileActionType.MOVE

        on_dup_val = data.get("on_duplicate", "rename")
        try:
            on_dup_enum = DuplicateAction(on_dup_val)
        except ValueError:
            on_dup_enum = DuplicateAction.RENAME

        return cls(
            destination=data.get("destination", "Organized/"),
            action_type=action_type_enum,
            on_duplicate=on_dup_enum,
            create_subfolders=bool(data.get("create_subfolders", True)),
        )


@dataclass
class Rule:
    """A complete DropSort rule consisting of conditions, action, and priority."""

    name: str
    action: Action
    priority: int = 100
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    enabled: bool = True
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    stop_on_match: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "priority": self.priority,
            "when": self.conditions.to_dict(),
            "then": self.action.to_dict(),
            "stop_on_match": self.stop_on_match,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Rule:
        rule_id = data.get("id") or str(uuid.uuid4())[:8]
        name = data.get("name", "Untitled Rule")
        description = data.get("description", "")
        enabled = data.get("enabled", True)
        priority = int(data.get("priority", 100))
        stop_on_match = bool(data.get("stop_on_match", True))

        # Conditions parsing ('when' or 'conditions')
        when_data = data.get("when") or data.get("conditions") or {}
        if isinstance(when_data, list):
            conditions = ConditionGroup.from_dict({"conditions": when_data})
        elif isinstance(when_data, dict):
            if "conditions" in when_data or "logical_operator" in when_data:
                conditions = ConditionGroup.from_dict(when_data)
            else:
                # Shortcut format: {"extension": "pdf", "filename_contains": "invoice"}
                conditions = ConditionGroup.from_dict({"conditions": [when_data]})
        else:
            conditions = ConditionGroup()

        # Action parsing ('then' or 'action')
        then_data = data.get("then") or data.get("action") or {}
        if isinstance(then_data, str):
            action = Action(destination=then_data)
        else:
            action = Action.from_dict(then_data)

        return cls(
            id=rule_id,
            name=name,
            description=description,
            enabled=enabled,
            priority=priority,
            conditions=conditions,
            action=action,
            stop_on_match=stop_on_match,
        )


@dataclass
class FileMetadata:
    """Rich metadata extracted for a file."""

    path: Path
    name: str
    base_name: str
    extension: str  # without dot, lowercase
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    is_file: bool = True
    category: FileCategory = FileCategory.OTHER
    mime_type: Optional[str] = None

    @classmethod
    def from_path(cls, file_path: Union[str, Path]) -> FileMetadata:
        p = Path(file_path).resolve()
        stat = p.stat()
        name = p.name
        suffix = p.suffix.lower().lstrip(".")
        base = p.stem
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)
        
        # ctime on Windows is creation time, on unix it is metadata change time
        ctime_ts = getattr(stat, "st_ctime", stat.st_mtime)
        try:
            ctime = datetime.fromtimestamp(ctime_ts)
        except Exception:
            ctime = mtime

        # Determine category
        cat = FileCategory.OTHER
        for category, ext_set in CATEGORY_EXTENSIONS.items():
            if suffix in ext_set:
                cat = category
                break

        return cls(
            path=p,
            name=name,
            base_name=base,
            extension=suffix,
            size_bytes=size,
            created_at=ctime,
            modified_at=mtime,
            is_file=p.is_file(),
            category=cat,
        )

    def format_size(self) -> str:
        """Return human-readable file size."""
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{self.size_bytes} B"


class PlanItemStatus(str, Enum):
    READY = "ready"
    CONFLICT = "conflict"
    SKIPPED = "skipped"
    IGNORED = "ignored"


@dataclass
class PlanItem:
    """Proposed file action item generated during preview."""

    file_meta: FileMetadata
    target_path: Path
    rule_id: Optional[str]
    rule_name: str
    action_type: FileActionType
    on_duplicate: DuplicateAction
    status: PlanItemStatus = PlanItemStatus.READY
    is_duplicate: bool = False
    original_target_path: Optional[Path] = None
    reason: str = ""
    selected: bool = True  # For GUI checkbox toggling

    @property
    def source_path(self) -> Path:
        return self.file_meta.path

    @property
    def file_name(self) -> str:
        return self.file_meta.name

    @property
    def file_size_human(self) -> str:
        return self.file_meta.format_size()


@dataclass
class PreviewPlan:
    """Complete preview plan of actions to be applied."""

    items: List[PlanItem] = field(default_factory=list)
    base_folder: Path = field(default_factory=Path.cwd)
    total_files_scanned: int = 0
    ignored_count: int = 0

    @property
    def actionable_items(self) -> List[PlanItem]:
        return [item for item in self.items if item.selected and item.status in (PlanItemStatus.READY, PlanItemStatus.CONFLICT)]

    @property
    def ready_count(self) -> int:
        return sum(1 for item in self.items if item.status == PlanItemStatus.READY)

    @property
    def conflict_count(self) -> int:
        return sum(1 for item in self.items if item.status == PlanItemStatus.CONFLICT)

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if item.status == PlanItemStatus.SKIPPED)


class MoveRecordStatus(str, Enum):
    COMPLETED = "completed"
    UNDONE = "undone"
    FAILED = "failed"


@dataclass
class MoveRecord:
    """Database record of an executed move/copy action."""

    id: str
    batch_id: str
    original_path: str
    target_path: str
    file_size: int
    rule_name: str
    action_type: str
    status: MoveRecordStatus = MoveRecordStatus.COMPLETED
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "original_path": self.original_path,
            "target_path": self.target_path,
            "file_size": self.file_size,
            "rule_name": self.rule_name,
            "action_type": self.action_type,
            "status": self.status.value if isinstance(self.status, MoveRecordStatus) else str(self.status),
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
        }


@dataclass
class BatchRecord:
    """Database record of an organization session/batch."""

    id: str
    target_folder: str
    total_moves: int
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "completed"
    undone_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_folder": self.target_folder,
            "total_moves": self.total_moves,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "undone_count": self.undone_count,
        }


@dataclass
class AppSettings:
    """Global configuration settings for DropSort."""

    monitored_folder: str = ""
    recursive_scan: bool = False
    default_on_duplicate: DuplicateAction = DuplicateAction.RENAME
    clean_empty_folders: bool = True
    debounce_seconds: float = 1.5
    dark_mode: bool = True
    ignored_patterns: List[str] = field(
        default_factory=lambda: [
            "*.tmp",
            "*.crdownload",
            "*.part",
            "*.download",
            ".git",
            ".DS_Store",
            "Thumbs.db",
            "~$*",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monitored_folder": self.monitored_folder,
            "recursive_scan": self.recursive_scan,
            "default_on_duplicate": (
                self.default_on_duplicate.value
                if isinstance(self.default_on_duplicate, DuplicateAction)
                else str(self.default_on_duplicate)
            ),
            "clean_empty_folders": self.clean_empty_folders,
            "debounce_seconds": self.debounce_seconds,
            "dark_mode": self.dark_mode,
            "ignored_patterns": self.ignored_patterns,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppSettings:
        dup = data.get("default_on_duplicate", "rename")
        try:
            dup_enum = DuplicateAction(dup)
        except ValueError:
            dup_enum = DuplicateAction.RENAME

        return cls(
            monitored_folder=data.get("monitored_folder", ""),
            recursive_scan=bool(data.get("recursive_scan", False)),
            default_on_duplicate=dup_enum,
            clean_empty_folders=bool(data.get("clean_empty_folders", True)),
            debounce_seconds=float(data.get("debounce_seconds", 1.5)),
            dark_mode=bool(data.get("dark_mode", True)),
            ignored_patterns=list(data.get("ignored_patterns", [
                "*.tmp", "*.crdownload", "*.part", "*.download", ".git", ".DS_Store", "Thumbs.db", "~$*"
            ])),
        )

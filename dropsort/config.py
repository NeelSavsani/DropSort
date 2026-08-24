"""Configuration loader, default smart rules presets, and settings manager."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dropsort.models import (
    Action,
    AppSettings,
    Condition,
    ConditionField,
    ConditionGroup,
    ConditionOp,
    DuplicateAction,
    FileActionType,
    FileCategory,
    Rule,
)


def get_default_rules() -> List[Rule]:
    """Return default smart rules for intelligent organization."""
    return [
        Rule(
            id="rule-invoices",
            name="Invoices & Receipts",
            description="Route invoice PDFs into organized yearly subfolders",
            priority=10,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="AND",
                conditions=[
                    Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf"),
                    Condition(ConditionField.FILENAME, ConditionOp.MATCHES_REGEX, r"(?i)(invoice|receipt|bill|statement)"),
                ],
            ),
            action=Action(
                destination="Documents/Invoices/{year}/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-photos-year",
            name="Photos by Year",
            description="Organize image files into yearly folders based on photo date",
            priority=20,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.IMAGES.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["jpg", "jpeg", "png", "webp", "gif", "heic", "raw"]),
                ],
            ),
            action=Action(
                destination="Images/{year}/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-spreadsheets",
            name="Spreadsheets & Reports",
            description="Organize Excel, CSV, and tabular data sheets",
            priority=30,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.SPREADSHEETS.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["xlsx", "xls", "csv", "tsv", "ods"]),
                ],
            ),
            action=Action(
                destination="Spreadsheets/{year}/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-documents-general",
            name="Documents",
            description="Organize general PDF, Word, and text documents",
            priority=40,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.DOCUMENTS.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["pdf", "doc", "docx", "txt", "rtf", "odt", "epub"]),
                ],
            ),
            action=Action(
                destination="Documents/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-videos",
            name="Videos & Screen Recordings",
            description="Organize MP4, MKV, MOV, and video files",
            priority=50,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.VIDEOS.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["mp4", "mkv", "mov", "avi", "webm"]),
                ],
            ),
            action=Action(
                destination="Videos/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-music",
            name="Audio & Music",
            description="Organize MP3, WAV, FLAC audio files",
            priority=60,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.AUDIO.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["mp3", "wav", "flac", "aac", "ogg", "m4a"]),
                ],
            ),
            action=Action(
                destination="Music/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-archives",
            name="Archives & Compressed",
            description="Organize ZIP, 7Z, TAR, RAR archives",
            priority=70,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.ARCHIVES.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["zip", "7z", "tar", "gz", "rar", "bz2"]),
                ],
            ),
            action=Action(
                destination="Archives/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-applications",
            name="Applications & Setups",
            description="Organize installer setup files and executables",
            priority=80,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.APPLICATIONS.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["exe", "msi", "dmg", "pkg", "deb", "apk"]),
                ],
            ),
            action=Action(
                destination="Applications/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
        Rule(
            id="rule-code",
            name="Code & Scripts",
            description="Organize source code files and scripts",
            priority=90,
            enabled=True,
            conditions=ConditionGroup(
                logical_operator="OR",
                conditions=[
                    Condition(ConditionField.FILE_TYPE, ConditionOp.EQUALS, FileCategory.CODE.value),
                    Condition(ConditionField.EXTENSION, ConditionOp.IN_LIST, ["py", "js", "ts", "html", "css", "json", "cpp", "rs", "go"]),
                ],
            ),
            action=Action(
                destination="Code/{ext}/",
                action_type=FileActionType.MOVE,
                on_duplicate=DuplicateAction.RENAME,
            ),
        ),
    ]


def load_rules_from_file(file_path: Union[str, Path]) -> List[Rule]:
    """Load rules from a JSON or YAML file."""
    p = Path(file_path)
    if not p.exists():
        return get_default_rules()

    content = p.read_text(encoding="utf-8")
    if p.suffix.lower() in [".yaml", ".yml"]:
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise RuntimeError("PyYAML is required to parse YAML rule files.")
    else:
        data = json.loads(content)

    rules_data = data.get("rules", []) if isinstance(data, dict) else data
    rules = [Rule.from_dict(r) for r in rules_data if isinstance(r, dict)]
    # Sort rules by priority
    rules.sort(key=lambda r: r.priority)
    return rules


def save_rules_to_file(rules: List[Rule], file_path: Union[str, Path]) -> None:
    """Save rules to a JSON or YAML file."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    sorted_rules = sorted(rules, key=lambda r: r.priority)
    data = {"rules": [r.to_dict() for r in sorted_rules]}

    if p.suffix.lower() in [".yaml", ".yml"]:
        try:
            import yaml
            p.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
        except ImportError:
            raise RuntimeError("PyYAML is required to save YAML rule files.")
    else:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_app_data_dir() -> Path:
    """Get the persistent app data directory for SQLite DB and config."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    
    app_dir = Path(base) / "DropSort"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def load_settings(file_path: Optional[Union[str, Path]] = None) -> AppSettings:
    """Load settings from JSON file or return defaults."""
    if file_path is None:
        file_path = get_app_data_dir() / "settings.json"
    else:
        file_path = Path(file_path)

    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return AppSettings.from_dict(data)
        except Exception:
            pass
    return AppSettings()


def save_settings(settings: AppSettings, file_path: Optional[Union[str, Path]] = None) -> None:
    """Save settings to JSON file."""
    if file_path is None:
        file_path = get_app_data_dir() / "settings.json"
    else:
        file_path = Path(file_path)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")

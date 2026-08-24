"""Unit tests for DropSort data models."""

from datetime import datetime
from pathlib import Path
import tempfile
import pytest

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
    FileMetadata,
    LogicalOp,
    MoveRecord,
    MoveRecordStatus,
    PlanItem,
    PlanItemStatus,
    Rule,
)


def test_condition_serialization():
    c = Condition(field=ConditionField.EXTENSION, operator=ConditionOp.EQUALS, value="pdf")
    d = c.to_dict()
    assert d["field"] == "extension"
    assert d["operator"] == "equals"
    assert d["value"] == "pdf"

    c2 = Condition.from_dict(d)
    assert c2.field == ConditionField.EXTENSION
    assert c2.operator == ConditionOp.EQUALS
    assert c2.value == "pdf"


def test_condition_group_serialization():
    c1 = Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf")
    c2 = Condition(ConditionField.FILENAME, ConditionOp.CONTAINS, "invoice")
    group = ConditionGroup(logical_operator=LogicalOp.AND, conditions=[c1, c2])

    d = group.to_dict()
    assert d["logical_operator"] == "AND"
    assert len(d["conditions"]) == 2

    g2 = ConditionGroup.from_dict(d)
    assert g2.logical_operator == LogicalOp.AND
    assert len(g2.conditions) == 2


def test_rule_from_dict_and_to_dict():
    rule_data = {
        "id": "r1",
        "name": "Invoices",
        "description": "Invoice rule",
        "enabled": True,
        "priority": 10,
        "when": {
            "extension": "pdf",
            "filename_contains": "invoice",
        },
        "then": {
            "destination": "Documents/Invoices/{year}/",
            "on_duplicate": "rename",
            "action_type": "move",
        },
    }

    r = Rule.from_dict(rule_data)
    assert r.name == "Invoices"
    assert r.priority == 10
    assert r.action.destination == "Documents/Invoices/{year}/"
    assert r.action.on_duplicate == DuplicateAction.RENAME
    assert len(r.conditions.conditions) == 2

    d = r.to_dict()
    assert d["name"] == "Invoices"
    assert d["then"]["destination"] == "Documents/Invoices/{year}/"


def test_file_metadata_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "sample_test.png"
        test_file.write_bytes(b"hello image data")

        meta = FileMetadata.from_path(test_file)
        assert meta.name == "sample_test.png"
        assert meta.base_name == "sample_test"
        assert meta.extension == "png"
        assert meta.size_bytes == 16
        assert meta.category == FileCategory.IMAGES
        assert "B" in meta.format_size()


def test_app_settings_defaults():
    settings = AppSettings()
    assert settings.default_on_duplicate == DuplicateAction.RENAME
    assert settings.debounce_seconds == 1.5
    assert "*.tmp" in settings.ignored_patterns

    d = settings.to_dict()
    s2 = AppSettings.from_dict(d)
    assert s2.debounce_seconds == 1.5

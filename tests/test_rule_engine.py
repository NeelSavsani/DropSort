"""Unit tests for DropSort pure RuleEngine."""

from datetime import datetime, timedelta
from pathlib import Path
import pytest

from dropsort.config import get_default_rules
from dropsort.models import (
    Action,
    Condition,
    ConditionField,
    ConditionGroup,
    ConditionOp,
    DuplicateAction,
    FileActionType,
    FileCategory,
    FileMetadata,
    LogicalOp,
    Rule,
)
from dropsort.rule_engine import RuleEngine, parse_date, parse_size_to_bytes


def make_file_meta(
    name: str,
    size: int = 1024,
    mtime: datetime | None = None,
    category: FileCategory = FileCategory.OTHER,
) -> FileMetadata:
    p = Path("/mock/Downloads") / name
    dt = mtime or datetime(2026, 8, 24, 14, 30, 0)
    ext = p.suffix.lower().lstrip(".")
    return FileMetadata(
        path=p,
        name=name,
        base_name=p.stem,
        extension=ext,
        size_bytes=size,
        created_at=dt,
        modified_at=dt,
        category=category,
    )


def test_parse_size():
    assert parse_size_to_bytes("10MB") == 10 * 1024 * 1024
    assert parse_size_to_bytes("500KB") == 500 * 1024
    assert parse_size_to_bytes("1.5GB") == int(1.5 * 1024 * 1024 * 1024)
    assert parse_size_to_bytes("2048") == 2048


def test_single_condition_extension():
    engine = RuleEngine()
    cond = Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf")

    f_pdf = make_file_meta("doc.pdf")
    f_jpg = make_file_meta("pic.jpg")

    assert engine.evaluate_condition(cond, f_pdf) is True
    assert engine.evaluate_condition(cond, f_jpg) is False


def test_single_condition_regex_and_glob():
    engine = RuleEngine()

    cond_regex = Condition(ConditionField.FILENAME, ConditionOp.MATCHES_REGEX, r"invoice_\d{4}")
    cond_glob = Condition(ConditionField.FILENAME, ConditionOp.MATCHES_GLOB, "*report*.xlsx")

    assert engine.evaluate_condition(cond_regex, make_file_meta("invoice_2026.pdf")) is True
    assert engine.evaluate_condition(cond_regex, make_file_meta("invoice_test.pdf")) is False

    assert engine.evaluate_condition(cond_glob, make_file_meta("final_report_q3.xlsx")) is True
    assert engine.evaluate_condition(cond_glob, make_file_meta("data.xlsx")) is False


def test_single_condition_size():
    engine = RuleEngine()
    cond_large = Condition(ConditionField.SIZE_BYTES, ConditionOp.GREATER_THAN, "5MB")

    assert engine.evaluate_condition(cond_large, make_file_meta("huge.iso", size=10 * 1024 * 1024)) is True
    assert engine.evaluate_condition(cond_large, make_file_meta("small.txt", size=1024)) is False


def test_single_condition_date():
    engine = RuleEngine()
    now = datetime.now()
    two_days_ago = now - timedelta(days=2)
    ten_days_ago = now - timedelta(days=10)

    cond_recent = Condition(ConditionField.DATE_MODIFIED, ConditionOp.WITHIN_DAYS, 5)

    assert engine.evaluate_condition(cond_recent, make_file_meta("recent.txt", mtime=two_days_ago)) is True
    assert engine.evaluate_condition(cond_recent, make_file_meta("old.txt", mtime=ten_days_ago)) is False


def test_condition_group_and_logic():
    engine = RuleEngine()
    rule = Rule(
        name="Invoice PDFs",
        priority=10,
        conditions=ConditionGroup(
            logical_operator=LogicalOp.AND,
            conditions=[
                Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf"),
                Condition(ConditionField.FILENAME, ConditionOp.CONTAINS, "invoice"),
            ],
        ),
        action=Action(destination="Documents/Invoices/{year}/"),
    )

    engine.set_rules([rule])

    # Case 1: Matches both
    res1 = engine.find_matching_rule(make_file_meta("invoice_august.pdf"))
    assert res1 is not None
    assert res1.name == "Invoice PDFs"

    # Case 2: Only extension matches
    res2 = engine.find_matching_rule(make_file_meta("manual.pdf"))
    assert res2 is None

    # Case 3: Only contains matches
    res3 = engine.find_matching_rule(make_file_meta("invoice.txt"))
    assert res3 is None


def test_condition_group_or_logic():
    engine = RuleEngine()
    rule = Rule(
        name="Media Files",
        priority=10,
        conditions=ConditionGroup(
            logical_operator=LogicalOp.OR,
            conditions=[
                Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "mp3"),
                Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "mp4"),
            ],
        ),
        action=Action(destination="Media/"),
    )
    engine.set_rules([rule])

    assert engine.find_matching_rule(make_file_meta("song.mp3")) is not None
    assert engine.find_matching_rule(make_file_meta("video.mp4")) is not None
    assert engine.find_matching_rule(make_file_meta("sheet.xlsx")) is None


def test_priority_resolution():
    specific_rule = Rule(
        name="Invoice PDFs",
        priority=10,
        conditions=ConditionGroup(
            logical_operator=LogicalOp.AND,
            conditions=[
                Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf"),
                Condition(ConditionField.FILENAME, ConditionOp.CONTAINS, "invoice"),
            ],
        ),
        action=Action(destination="Documents/Invoices/{year}/"),
    )
    general_rule = Rule(
        name="General PDFs",
        priority=20,
        conditions=ConditionGroup(
            logical_operator=LogicalOp.AND,
            conditions=[
                Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf"),
            ],
        ),
        action=Action(destination="Documents/"),
    )

    engine = RuleEngine([general_rule, specific_rule])  # Passed out of order

    # Specific invoice should match priority 10 rule first
    match = engine.find_matching_rule(make_file_meta("invoice_2026.pdf"))
    assert match is not None
    assert match.name == "Invoice PDFs"

    # Other PDF should fall back to priority 20 rule
    match2 = engine.find_matching_rule(make_file_meta("resume.pdf"))
    assert match2 is not None
    assert match2.name == "General PDFs"


def test_template_destination_rendering():
    engine = RuleEngine()
    action = Action(destination="Documents/Invoices/{year}/{month}/")
    meta = make_file_meta("invoice_august_2026.pdf", mtime=datetime(2026, 8, 24, 10, 0, 0))
    base = Path("/mock/Downloads")

    dest = engine.render_destination(action, meta, base)
    assert str(dest).replace("\\", "/").endswith("Documents/Invoices/2026/08/invoice_august_2026.pdf")

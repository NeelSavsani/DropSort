"""Rule engine for evaluating file conditions and rendering dynamic destination paths."""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from dropsort.models import (
    Action,
    Condition,
    ConditionField,
    ConditionGroup,
    ConditionOp,
    FileCategory,
    FileMetadata,
    LogicalOp,
    Rule,
)


def parse_size_to_bytes(val: Union[int, float, str]) -> int:
    """Convert size expressions like '10MB', '500KB', '1.5GB', or integer bytes to byte count."""
    if isinstance(val, (int, float)):
        return int(val)
    
    val_str = str(val).strip().upper()
    units = {
        "TB": 1024 ** 4,
        "GB": 1024 ** 3,
        "MB": 1024 ** 2,
        "KB": 1024,
        "B": 1,
    }
    match = re.match(r"^([\d.]+)\s*([A-Z]+)?$", val_str)
    if match:
        num = float(match.group(1))
        unit = match.group(2) or "B"
        mult = units.get(unit, 1)
        return int(num * mult)
    try:
        return int(val_str)
    except ValueError:
        return 0


def parse_date(val: Union[datetime, str]) -> Optional[datetime]:
    """Parse date from datetime or common string formats."""
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            pass
    return None


class RuleEngine:
    """Pure rule evaluation engine."""

    def __init__(self, rules: Optional[List[Rule]] = None) -> None:
        self.rules: List[Rule] = rules or []
        self._sort_rules()

    def set_rules(self, rules: List[Rule]) -> None:
        """Update active rules."""
        self.rules = list(rules)
        self._sort_rules()

    def _sort_rules(self) -> None:
        """Ensure rules are sorted ascending by priority (1 before 2)."""
        self.rules.sort(key=lambda r: r.priority)

    def evaluate_condition(self, condition: Condition, file_meta: FileMetadata) -> bool:
        """Evaluate a single Condition against FileMetadata."""
        field_name = condition.field.value if isinstance(condition.field, ConditionField) else str(condition.field).lower()
        operator = condition.operator.value if isinstance(condition.operator, ConditionOp) else str(condition.operator).lower()
        expected = condition.value

        # Normalize file fields
        if field_name == "extension":
            actual = file_meta.extension.lower()
            if operator == "equals":
                return actual == str(expected).lower().lstrip(".")
            elif operator == "not_equals":
                return actual != str(expected).lower().lstrip(".")
            elif operator == "in_list":
                exp_list = [str(x).lower().lstrip(".") for x in (expected if isinstance(expected, list) else [expected])]
                return actual in exp_list
            elif operator == "not_in_list":
                exp_list = [str(x).lower().lstrip(".") for x in (expected if isinstance(expected, list) else [expected])]
                return actual not in exp_list

        elif field_name == "filename":
            actual = file_meta.name
            exp_str = str(expected)
            if operator == "contains":
                return exp_str.lower() in actual.lower()
            elif operator == "not_contains":
                return exp_str.lower() not in actual.lower()
            elif operator == "starts_with":
                return actual.lower().startswith(exp_str.lower())
            elif operator == "ends_with":
                return actual.lower().endswith(exp_str.lower())
            elif operator == "equals":
                return actual.lower() == exp_str.lower()
            elif operator == "not_equals":
                return actual.lower() != exp_str.lower()
            elif operator == "matches_regex":
                try:
                    return bool(re.search(exp_str, actual, re.IGNORECASE))
                except re.error:
                    return False
            elif operator == "matches_glob":
                return fnmatch.fnmatch(actual.lower(), exp_str.lower())

        elif field_name == "filename_regex":
            try:
                return bool(re.search(str(expected), file_meta.name, re.IGNORECASE))
            except re.error:
                return False

        elif field_name == "filename_glob":
            return fnmatch.fnmatch(file_meta.name.lower(), str(expected).lower())

        elif field_name == "file_type":
            actual_cat = file_meta.category.value if isinstance(file_meta.category, FileCategory) else str(file_meta.category)
            exp_str = expected.value if isinstance(expected, FileCategory) else str(expected)
            if operator == "equals":
                return actual_cat.lower() == exp_str.lower()
            elif operator == "not_equals":
                return actual_cat.lower() != exp_str.lower()
            elif operator == "in_list":
                exp_list = [str(x).lower() for x in (expected if isinstance(expected, list) else [expected])]
                return actual_cat.lower() in exp_list

        elif field_name == "size_bytes":
            actual_size = file_meta.size_bytes
            expected_size = parse_size_to_bytes(expected)
            if operator == "greater_than":
                return actual_size > expected_size
            elif operator == "less_than":
                return actual_size < expected_size
            elif operator == "equals":
                return actual_size == expected_size
            elif operator == "not_equals":
                return actual_size != expected_size

        elif field_name in ("date_modified", "date_created"):
            target_date = file_meta.modified_at if field_name == "date_modified" else file_meta.created_at
            now = datetime.now()

            if operator == "within_days":
                try:
                    days = float(expected)
                    diff = now - target_date
                    return timedelta(0) <= diff <= timedelta(days=days)
                except (ValueError, TypeError):
                    return False
            elif operator == "before_date":
                exp_dt = parse_date(expected)
                return bool(exp_dt and target_date < exp_dt)
            elif operator == "after_date":
                exp_dt = parse_date(expected)
                return bool(exp_dt and target_date > exp_dt)
            elif operator == "equals":
                # Year match or exact date match
                if str(expected).isdigit() and len(str(expected)) == 4:
                    return target_date.year == int(expected)
                exp_dt = parse_date(expected)
                return bool(exp_dt and target_date.date() == exp_dt.date())

        return False

    def evaluate_condition_group(self, group: ConditionGroup, file_meta: FileMetadata) -> bool:
        """Evaluate a ConditionGroup (handles AND / OR logic and nesting)."""
        if not group.conditions:
            return True

        is_and = group.logical_operator in (LogicalOp.AND, "AND")

        for item in group.conditions:
            if isinstance(item, ConditionGroup):
                result = self.evaluate_condition_group(item, file_meta)
            elif isinstance(item, Condition):
                result = self.evaluate_condition(item, file_meta)
            else:
                continue

            if is_and and not result:
                return False
            if not is_and and result:
                return True

        return is_and

    def match_rule(self, rule: Rule, file_meta: FileMetadata) -> bool:
        """Check if a file matches a rule's conditions."""
        if not rule.enabled:
            return False
        return self.evaluate_condition_group(rule.conditions, file_meta)

    def render_destination(self, action: Action, file_meta: FileMetadata, base_folder: Path) -> Path:
        """Render destination template with dynamic file variables."""
        dest_tpl = action.destination.strip()

        # Date replacements
        dt = file_meta.modified_at
        replacements = {
            "{year}": f"{dt.year:04d}",
            "{month}": f"{dt.month:02d}",
            "{month_name}": dt.strftime("%B"),
            "{day}": f"{dt.day:02d}",
            "{date}": dt.strftime("%Y-%m-%d"),
            "{time}": dt.strftime("%H-%M-%S"),
            "{ext}": file_meta.extension,
            "{extension}": file_meta.extension,
            "{name}": file_meta.name,
            "{filename}": file_meta.name,
            "{base_name}": file_meta.base_name,
            "{stem}": file_meta.base_name,
            "{category}": file_meta.category.value if isinstance(file_meta.category, FileCategory) else str(file_meta.category),
            "{size}": str(file_meta.size_bytes),
            "{size_human}": file_meta.format_size(),
        }

        rendered = dest_tpl
        for token, val in replacements.items():
            rendered = re.sub(re.escape(token), str(val), rendered, flags=re.IGNORECASE)

        # Normalize slashes
        rendered_clean = rendered.replace("\\", "/").strip()
        rendered_path = Path(rendered_clean)

        # If path is relative, resolve against base_folder
        if not rendered_path.is_absolute():
            resolved = base_folder / rendered_path
        else:
            resolved = rendered_path

        # If destination ends with a slash or is a folder, append original filename
        if (
            dest_tpl.endswith("/")
            or dest_tpl.endswith("\\")
            or not rendered_path.suffix
            or rendered_clean.endswith(f"/{file_meta.extension}") is False and rendered_path.name != file_meta.name and not rendered_path.suffix
        ):
            if resolved.name != file_meta.name:
                resolved = resolved / file_meta.name

        return resolved

    def find_matching_rule(self, file_meta: FileMetadata) -> Optional[Rule]:
        """Find first matching enabled rule for a given file."""
        for rule in self.rules:
            if self.match_rule(rule, file_meta):
                return rule
        return None

    def plan_file(self, file_meta: FileMetadata, base_folder: Path) -> Optional[Tuple[Rule, Path]]:
        """Evaluate file and return matched rule and target path."""
        matched = self.find_matching_rule(file_meta)
        if matched is None:
            return None
        target_path = self.render_destination(matched.action, file_meta, base_folder)
        return matched, target_path

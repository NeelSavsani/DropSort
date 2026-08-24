"""CLI Interface for headless and automated execution of DropSort."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dropsort.config import get_default_rules, load_rules_from_file, load_settings
from dropsort.database import Database
from dropsort.models import FileMetadata, PlanItemStatus
from dropsort.organizer import create_preview, execute_plan, scan_folder, undo_batch
from dropsort.rule_engine import RuleEngine
from dropsort.watcher import FolderWatcher


# Color utilities for terminal formatting
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner() -> None:
    banner = f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║               📂 DropSort — File Organizer                   ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def list_rules_cmd(rules_path: Optional[str] = None) -> None:
    """Print all configured rules."""
    rules = load_rules_from_file(rules_path) if rules_path else get_default_rules()
    print(f"\n{Colors.BOLD}Configured Rules ({len(rules)} total):{Colors.RESET}")
    print(f"{'Priority':<10} {'Name':<28} {'Destination':<32} {'Action'}")
    print("-" * 80)
    for r in sorted(rules, key=lambda x: x.priority):
        status_color = Colors.GREEN if r.enabled else Colors.DIM
        print(
            f"{status_color}{r.priority:<10} {r.name:<28} {r.action.destination:<32} {r.action.action_type.value if hasattr(r.action.action_type, 'value') else r.action.action_type}{Colors.RESET}"
        )
    print("")


def simulate_cmd(folder_path: str, rules_path: Optional[str] = None, recursive: bool = False) -> None:
    """Perform dry-run simulation and print preview table."""
    base_folder = Path(folder_path).resolve()
    if not base_folder.exists():
        print(f"{Colors.RED}Error: Folder '{base_folder}' does not exist.{Colors.RESET}")
        sys.exit(1)

    rules = load_rules_from_file(rules_path) if rules_path else get_default_rules()
    rule_engine = RuleEngine(rules)
    settings = load_settings()

    print(f"\n{Colors.CYAN}Scanning folder:{Colors.RESET} {base_folder}")
    files, ignored = scan_folder(base_folder, recursive=recursive, ignored_patterns=settings.ignored_patterns)
    print(f"Detected {len(files)} files ({ignored} ignored)")

    plan = create_preview(files, rule_engine, base_folder)

    if not plan.items:
        print(f"{Colors.YELLOW}No files matched active rules or need moving.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{'SOURCE FILE':<30} {'→ DESTINATION':<40} {'RULE':<20} {'STATUS'}{Colors.RESET}")
    print("=" * 105)

    for item in plan.items:
        try:
            rel_src = item.source_path.relative_to(base_folder)
        except ValueError:
            rel_src = item.source_path.name

        try:
            rel_dst = item.target_path.relative_to(base_folder)
        except ValueError:
            rel_dst = item.target_path

        status_tag = ""
        if item.status == PlanItemStatus.READY:
            status_tag = f"{Colors.GREEN}[READY]{Colors.RESET}"
        elif item.status == PlanItemStatus.CONFLICT:
            status_tag = f"{Colors.YELLOW}[REPLACE]{Colors.RESET}"
        elif item.status == PlanItemStatus.SKIPPED:
            status_tag = f"{Colors.DIM}[SKIPPED]{Colors.RESET}"

        src_disp = str(rel_src)[:28]
        dst_disp = str(rel_dst)[:38]
        rule_disp = item.rule_name[:18]

        print(f"{src_disp:<30} {dst_disp:<40} {rule_disp:<20} {status_tag}")

    print("-" * 105)
    print(
        f"{Colors.BOLD}Simulation Summary:{Colors.RESET} "
        f"{Colors.GREEN}{plan.ready_count} ready to move{Colors.RESET}, "
        f"{Colors.YELLOW}{plan.conflict_count} duplicate overrides{Colors.RESET}, "
        f"{Colors.DIM}{plan.skipped_count} skipped{Colors.RESET}\n"
    )
    print(f"{Colors.DIM}(Dry run mode: No files were touched. Run with --run to apply.){Colors.RESET}\n")


def run_cmd(folder_path: str, rules_path: Optional[str] = None, recursive: bool = False) -> None:
    """Execute organization rules on folder."""
    base_folder = Path(folder_path).resolve()
    if not base_folder.exists():
        print(f"{Colors.RED}Error: Folder '{base_folder}' does not exist.{Colors.RESET}")
        sys.exit(1)

    rules = load_rules_from_file(rules_path) if rules_path else get_default_rules()
    rule_engine = RuleEngine(rules)
    database = Database()
    settings = load_settings()

    print(f"\n{Colors.CYAN}Scanning folder:{Colors.RESET} {base_folder}")
    files, ignored = scan_folder(base_folder, recursive=recursive, ignored_patterns=settings.ignored_patterns)
    print(f"Detected {len(files)} files ({ignored} ignored)")

    plan = create_preview(files, rule_engine, base_folder)

    if not plan.actionable_items:
        print(f"{Colors.YELLOW}No files to organize.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}Applying organization rules to {len(plan.actionable_items)} files...{Colors.RESET}\n")

    def progress(cur: int, tot: int, item, success: bool, err: str) -> None:
        if success:
            print(f" [{cur}/{tot}] {Colors.GREEN}✔{Colors.RESET} {item.file_name} → {item.target_path.name}")
        else:
            print(f" [{cur}/{tot}] {Colors.RED}✘{Colors.RESET} {item.file_name} Error: {err}")

    summary = execute_plan(plan, database, progress_callback=progress)

    print("\n" + "=" * 60)
    print(f"{Colors.GREEN}{Colors.BOLD}Organization Complete!{Colors.RESET}")
    print(f"Moved/Copied: {summary['executed']}")
    print(f"Failed:       {summary['failed']}")
    print(f"Batch ID:     {Colors.CYAN}{summary['batch_id']}{Colors.RESET}")
    print(f"\nTo undo this entire batch, run:\n  python main.py --undo {summary['batch_id']}\n")


def watch_cmd(folder_path: str, rules_path: Optional[str] = None, recursive: bool = False) -> None:
    """Start continuous folder watcher daemon in console."""
    base_folder = Path(folder_path).resolve()
    if not base_folder.exists():
        print(f"{Colors.RED}Error: Folder '{base_folder}' does not exist.{Colors.RESET}")
        sys.exit(1)

    rules = load_rules_from_file(rules_path) if rules_path else get_default_rules()
    rule_engine = RuleEngine(rules)
    database = Database()
    settings = load_settings()

    print(f"\n{Colors.GREEN}{Colors.BOLD}📡 DropSort Live Watcher Active{Colors.RESET}")
    print(f"Monitoring: {Colors.CYAN}{base_folder}{Colors.RESET}")
    print(f"Press {Colors.BOLD}Ctrl+C{Colors.RESET} to stop watching.\n")

    def on_file_landed(path: Path) -> None:
        try:
            if not path.exists():
                return
            meta = FileMetadata.from_path(path)
            plan = create_preview([meta], rule_engine, base_folder)
            if plan.actionable_items:
                res = execute_plan(plan, database)
                if res["executed"] > 0:
                    item = plan.actionable_items[0]
                    print(
                        f"[{time.strftime('%H:%M:%S')}] {Colors.GREEN}Organized:{Colors.RESET} {meta.name} → {item.target_path.parent.name}/{item.target_path.name} ({item.rule_name})"
                    )
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] {Colors.RED}Error organizing {path.name}:{Colors.RESET} {e}")

    watcher = FolderWatcher(
        folder_path=base_folder,
        on_file_detected=on_file_landed,
        debounce_seconds=settings.debounce_seconds,
        recursive=recursive,
        ignored_patterns=settings.ignored_patterns,
    )

    watcher.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Stopping folder watcher...{Colors.RESET}")
        watcher.stop()
        print("Watcher stopped.")


def undo_cmd(batch_identifier: Optional[str] = None) -> None:
    """Undo the last batch or a specified batch ID."""
    database = Database()
    if not batch_identifier or batch_identifier.lower() == "last":
        latest = database.get_latest_batch()
        if not latest:
            print(f"{Colors.YELLOW}No organization history found to undo.{Colors.RESET}")
            return
        batch_id = latest.id
    else:
        batch_id = batch_identifier

    print(f"\n{Colors.CYAN}Undoing batch:{Colors.RESET} {batch_id} ...")
    res = undo_batch(batch_id, database)

    if res["undone"] > 0:
        print(f"{Colors.GREEN}{Colors.BOLD}Successfully restored {res['undone']} files!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}No files could be restored for batch {batch_id}.{Colors.RESET}")

    if res["failed"] > 0:
        print(f"{Colors.RED}Failed to restore {res['failed']} files:{Colors.RESET}")
        for err in res.get("errors", []):
            print(f"  - {err}")
    print("")


def run_cli(args: List[str]) -> bool:
    """Parse and execute CLI arguments. Returns True if handled in CLI mode, False if GUI should launch."""
    parser = argparse.ArgumentParser(
        description="DropSort — Intelligent File Organizer",
        add_help=True,
    )
    parser.add_argument("--simulate", action="store_true", help="Dry run: preview file moves without touching disk")
    parser.add_argument("--run", action="store_true", help="Organize folder immediately")
    parser.add_argument("--watch", action="store_true", help="Start continuous folder monitoring daemon")
    parser.add_argument("--undo", nargs="?", const="last", help="Undo last batch or specified batch ID")
    parser.add_argument("--list-rules", action="store_true", help="Display all active rules")
    parser.add_argument("--path", "-p", type=str, help="Target folder path to organize or watch")
    parser.add_argument("--rules", "-r", type=str, help="Path to custom rules JSON or YAML file")
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively")

    parsed, unknown = parser.parse_known_args(args)

    # If no CLI action flags are provided, return False to launch GUI
    is_cli = (
        parsed.simulate
        or parsed.run
        or parsed.watch
        or parsed.undo is not None
        or parsed.list_rules
    )

    if not is_cli:
        return False

    print_banner()

    if parsed.list_rules:
        list_rules_cmd(parsed.rules)
        return True

    if parsed.undo is not None:
        undo_cmd(parsed.undo)
        return True

    if not parsed.path:
        print(f"{Colors.RED}Error: --path <folder_path> is required for --simulate, --run, and --watch.{Colors.RESET}")
        sys.exit(1)

    if parsed.simulate:
        simulate_cmd(parsed.path, parsed.rules, parsed.recursive)
    elif parsed.run:
        run_cmd(parsed.path, parsed.rules, parsed.recursive)
    elif parsed.watch:
        watch_cmd(parsed.path, parsed.rules, parsed.recursive)

    return True

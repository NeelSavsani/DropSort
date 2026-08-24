"""Real-time folder monitoring with watchdog, debounce queue, and write-lock detection."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from dropsort.models import FileMetadata
from dropsort.organizer import should_ignore


def is_file_ready_and_stable(file_path: Path, check_interval: float = 0.5, retries: int = 4) -> bool:
    """
    Check if a newly created file has finished writing by comparing file sizes across intervals
    and checking for write-lock availability.
    """
    if not file_path.exists() or not file_path.is_file():
        return False

    prev_size = -1
    for _ in range(retries):
        try:
            current_size = file_path.stat().st_size
            if current_size == prev_size and current_size > 0:
                # Try opening file to verify write-lock released
                with open(file_path, "rb") as _:
                    pass
                return True
            prev_size = current_size
        except (PermissionError, OSError):
            pass
        time.sleep(check_interval)

    # If file size is 0 or stable after checks
    try:
        if file_path.exists():
            return True
    except Exception:
        pass
    return False


class DropSortWatcherHandler(FileSystemEventHandler):
    """Event handler for folder monitoring with debouncing."""

    def __init__(
        self,
        callback: Callable[[Path], None],
        debounce_seconds: float = 1.5,
        ignored_patterns: Optional[List[str]] = None,
    ) -> None:
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.ignored_patterns = ignored_patterns or []
        self._pending_files: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._queue_file(Path(event.src_path))

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._queue_file(Path(event.src_path))

    def _queue_file(self, file_path: Path) -> None:
        if should_ignore(file_path, self.ignored_patterns):
            return

        with self._lock:
            # Set debounce timestamp
            self._pending_files[str(file_path.resolve())] = time.time() + self.debounce_seconds

    def _process_queue(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            ready_paths: List[str] = []

            with self._lock:
                for path_str, trigger_time in list(self._pending_files.items()):
                    if now >= trigger_time:
                        ready_paths.append(path_str)
                        del self._pending_files[path_str]

            for path_str in ready_paths:
                p = Path(path_str)
                if p.exists() and p.is_file():
                    if is_file_ready_and_stable(p):
                        try:
                            self.callback(p)
                        except Exception as e:
                            print(f"[Watcher Error] Error processing {p}: {e}")

            time.sleep(0.3)

    def stop(self) -> None:
        self._stop_event.set()


class FolderWatcher:
    """Manages watchdog Observer for a monitored directory."""

    def __init__(
        self,
        folder_path: Union[str, Path],
        on_file_detected: Callable[[Path], None],
        debounce_seconds: float = 1.5,
        recursive: bool = False,
        ignored_patterns: Optional[List[str]] = None,
    ) -> None:
        self.folder_path = Path(folder_path).resolve()
        self.on_file_detected = on_file_detected
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive
        self.ignored_patterns = ignored_patterns
        self._observer: Optional[Observer] = None
        self._handler: Optional[DropSortWatcherHandler] = None
        self.is_running = False

    def start(self) -> bool:
        """Start monitoring target directory."""
        if self.is_running:
            return True

        if not self.folder_path.exists() or not self.folder_path.is_dir():
            raise FileNotFoundError(f"Folder to watch does not exist: {self.folder_path}")

        self._handler = DropSortWatcherHandler(
            callback=self.on_file_detected,
            debounce_seconds=self.debounce_seconds,
            ignored_patterns=self.ignored_patterns,
        )
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.folder_path), recursive=self.recursive)
        self._observer.start()
        self.is_running = True
        return True

    def stop(self) -> None:
        """Stop monitoring directory."""
        if not self.is_running:
            return

        if self._handler:
            self._handler.stop()
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3.0)
        self.is_running = False

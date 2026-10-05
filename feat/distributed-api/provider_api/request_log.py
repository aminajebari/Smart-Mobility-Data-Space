"""Request / exchange log of a provider API (who asked what, when, and the outcome)."""
import json
import threading
from collections import deque
from datetime import datetime
from pathlib import Path


class RequestLog:
    def __init__(self, directory: Path, max_in_memory: int = 2000):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "requests.jsonl"
        self._entries: deque[dict] = deque(maxlen=max_in_memory)
        self._lock = threading.Lock()

    def add(self, **entry) -> dict:
        entry = {"timestamp": datetime.now().isoformat(timespec="seconds"), **entry}
        with self._lock:
            self._entries.append(entry)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def latest(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._entries)[-limit:][::-1]

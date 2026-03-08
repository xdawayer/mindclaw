# input: pathlib, json
# output: 导出 SessionStore
# pos: Session JSONL 持久化，管理对话历史的磁盘读写和整合指针
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Session persistence using JSONL files with consolidation pointer tracking."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path


class SessionStore:
    """Persist conversation history as JSONL files.

    Storage layout: ``{data_dir}/sessions/{sanitized_key}.jsonl``

    Each line is either a message dict or a consolidation meta line::

        {"_meta":"consolidation","pointer":15,"consolidated_at":1741420900.0}

    The consolidation pointer tracks how many messages have already been
    summarised into long-term memory.  ``load()`` returns only the messages
    *after* the pointer.
    """

    _KEY_RE = re.compile(r"[^a-zA-Z0-9_\-]")

    def __init__(self, data_dir: Path) -> None:
        self._sessions_dir = data_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, session_key: str) -> tuple[list[dict], int]:
        """Return ``(unconsolidated_messages, total_message_count)``."""
        all_messages, pointer = self._read_lines(session_key)
        return all_messages[pointer:], len(all_messages)

    def append(self, session_key: str, messages: list[dict]) -> None:
        """Append *messages* to the JSONL file for *session_key*."""
        path = self._key_to_path(session_key)
        with path.open("a", encoding="utf-8") as fh:
            for msg in messages:
                fh.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def mark_consolidated(self, session_key: str, pointer: int) -> None:
        """Record that messages up to *pointer* have been consolidated."""
        path = self._key_to_path(session_key)
        meta = {
            "_meta": "consolidation",
            "pointer": pointer,
            "consolidated_at": time.time(),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(meta, ensure_ascii=False) + "\n")

    def load_for_consolidation(
        self, session_key: str, keep_recent: int = 10
    ) -> list[dict]:
        """Return messages in the consolidation window.

        The window spans ``messages[pointer : total - keep_recent]``.
        If there aren't enough messages beyond *keep_recent*, return ``[]``.
        """
        all_messages, pointer = self._read_lines(session_key)
        total = len(all_messages)
        end = total - keep_recent
        if end <= pointer:
            return []
        return all_messages[pointer:end]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_lines(self, session_key: str) -> tuple[list[dict], int]:
        """Read all message lines and current consolidation pointer.

        Returns ``(all_messages, pointer)`` where *all_messages* excludes
        meta lines and *pointer* is the latest consolidation pointer (0 if
        never consolidated).
        """
        path = self._key_to_path(session_key)
        if not path.exists():
            return [], 0

        messages: list[dict] = []
        pointer = 0

        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("_meta") == "consolidation":
                    pointer = record["pointer"]
                else:
                    messages.append(record)

        return messages, pointer

    def _key_to_path(self, session_key: str) -> Path:
        """Sanitise *session_key* into a safe filename."""
        safe = self._KEY_RE.sub("_", session_key)
        return self._sessions_dir / f"{safe}.jsonl"

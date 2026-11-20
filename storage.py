"""Простое JSON-хранилище: история отправленного (антидубли), лог действий, свои шаблоны."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MAX_SENT = 1000
MAX_LOG = 50


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "state.json"
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {
            "sent": [],
            "log": [],
            "templates": [],
            "promo_idx": -1,
        }
        data_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
            self._state.update(loaded)
        except Exception:
            log.exception("Не удалось прочитать state.json, начинаю с чистого состояния")

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    # --- антидубли ---
    def is_sent(self, key: str) -> bool:
        return key in self._state["sent"]

    async def mark_sent(self, key: str) -> None:
        async with self._lock:
            if key not in self._state["sent"]:
                self._state["sent"].append(key)
                self._state["sent"] = self._state["sent"][-MAX_SENT:]
                self._save()

    # --- лог действий ---
    async def add_log(self, kind: str, ok: bool, info: str) -> None:
        async with self._lock:
            self._state["log"].append(
                {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "kind": kind,
                    "ok": ok,
                    "info": info[:200],
                }
            )
            self._state["log"] = self._state["log"][-MAX_LOG:]
            self._save()

    def last_logs(self, n: int = 5) -> list[dict[str, Any]]:
        return self._state["log"][-n:]

    # --- шаблоны ---
    def user_templates(self) -> list[str]:
        return list(self._state["templates"])

    async def add_template(self, text: str) -> int:
        async with self._lock:
            self._state["templates"].append(text)
            self._save()
            return len(self._state["templates"])

    async def remove_template(self, index: int) -> bool:
        async with self._lock:
            if 0 <= index < len(self._state["templates"]):
                self._state["templates"].pop(index)
                self._save()
                return True
            return False

    def next_promo_index(self, total: int) -> int:
        return (self._state["promo_idx"] + 1) % max(total, 1)

    async def set_promo_index(self, idx: int) -> None:
        async with self._lock:
            self._state["promo_idx"] = idx
            self._save()

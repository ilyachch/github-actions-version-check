import json
import time
from pathlib import Path
from typing import Any, Callable, Protocol

CACHE_SCHEMA_VERSION = 1


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...

    def get_stale(self, key: str) -> Any | None: ...

    def set(self, key: str, payload: Any) -> None: ...


class JsonTTLCache(CacheBackend):
    def __init__(
        self,
        path: Path,
        ttl_seconds: int,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._path = path
        self._ttl_seconds = ttl_seconds
        self._now = now or time.time
        self._loaded = False
        self._entries: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entry_for(key)
        if entry is None:
            return None
        if self._is_stale(entry):
            return None
        return entry.get('payload')

    def get_stale(self, key: str) -> Any | None:
        entry = self._entry_for(key)
        if entry is None:
            return None
        return entry.get('payload')

    def set(self, key: str, payload: Any) -> None:
        self._ensure_loaded()
        self._prune_stale_entries()
        self._entries[key] = {'fetched_at': self._now(), 'payload': payload}
        self._write()

    def _entry_for(self, key: str) -> dict[str, Any] | None:
        self._ensure_loaded()
        entry = self._entries.get(key)
        if not isinstance(entry, dict):
            return None
        fetched_at = entry.get('fetched_at')
        if not isinstance(fetched_at, int | float):
            return None
        return entry

    def _is_stale(self, entry: dict[str, Any]) -> bool:
        fetched_at = float(entry.get('fetched_at', 0))
        return self._now() - fetched_at > self._ttl_seconds

    def _prune_stale_entries(self) -> None:
        self._entries = {
            key: value
            for key, value in self._entries.items()
            if isinstance(value, dict) and not self._is_stale(value)
        }

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._entries = {}

        if not self._path.exists():
            return

        try:
            loaded = json.loads(self._path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(loaded, dict):
            return
        if loaded.get('version') != CACHE_SCHEMA_VERSION:
            return

        entries = loaded.get('entries')
        if isinstance(entries, dict):
            self._entries = entries

    def _write(self) -> None:
        payload = {'version': CACHE_SCHEMA_VERSION, 'entries': self._entries}
        self._path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self._path.with_suffix(f'{self._path.suffix}.tmp')
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        temp_path.replace(self._path)


class NoopCache(CacheBackend):
    def get(self, key: str) -> Any | None:
        _ = key
        return None

    def get_stale(self, key: str) -> Any | None:
        _ = key
        return None

    def set(self, key: str, payload: Any) -> None:
        _ = (key, payload)

"""Local data cache layer — CSV + SQLite.

All fetched data can be cached to avoid repeated HTTP calls.
Supports TTL-based expiration and manual invalidation.
"""

from __future__ import annotations

import json
import logging
import os
import hashlib
import time
from pathlib import Path
from typing import Any

import pandas as pd

from mystrategy.config import CACHE_DIR, CACHE_ENABLED, CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class DataCache:
    """File-based cache for data vendor responses.

    Two storage modes:
    - CSV: for tabular data (K-line, fund flow, etc.)
    - JSON: for dict/list responses (quotes, news, etc.)

    Cache keys are derived from (namespace, args_hash).
    """

    def __init__(self, cache_dir: str | Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.csv_dir = self.cache_dir / "csv"
        self.json_dir = self.cache_dir / "json"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, namespace: str, *args) -> str:
        """Generate a cache key from namespace + arguments."""
        raw = f"{namespace}:{':'.join(str(a) for a in args)}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _csv_path(self, key: str) -> Path:
        return self.csv_dir / f"{key}.csv"

    def _json_path(self, key: str) -> Path:
        return self.json_dir / f"{key}.json"

    def _ttl_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.ttl"

    def _get_ttl(self, key: str) -> int:
        """Get TTL in seconds for a namespace."""
        for prefix, ttl in CACHE_TTL_SECONDS.items():
            if key.startswith(prefix):
                return ttl
        return 300  # default 5 minutes

    def _is_valid(self, key: str) -> bool:
        """Check if cache entry is still valid (within TTL)."""
        ttl_path = self._ttl_path(key)
        if not ttl_path.exists():
            return False
        try:
            stored_time = float(ttl_path.read_text().strip())
            ttl = self._get_ttl(key)
            return (time.time() - stored_time) < ttl
        except Exception:
            return False

    def _write_ttl(self, key: str):
        self._ttl_path(key).write_text(str(time.time()))

    # ── DataFrame (CSV) cache ──

    def get_df(self, key: str) -> pd.DataFrame | None:
        if not CACHE_ENABLED:
            return None
        path = self._csv_path(key)
        if path.exists() and self._is_valid(key):
            try:
                return pd.read_csv(path)
            except Exception:
                return None
        return None

    def set_df(self, key: str, df: pd.DataFrame):
        if not CACHE_ENABLED or df is None or df.empty:
            return
        path = self._csv_path(key)
        try:
            df.to_csv(path, index=False)
            self._write_ttl(key)
        except Exception as e:
            logger.debug("Cache write failed: %s", e)

    # ── Dict/List (JSON) cache ──

    def get_json(self, key: str) -> dict | list | None:
        if not CACHE_ENABLED:
            return None
        path = self._json_path(key)
        if path.exists() and self._is_valid(key):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def set_json(self, key: str, data: dict | list):
        if not CACHE_ENABLED:
            return
        path = self._json_path(key)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, default=str),
                          encoding="utf-8")
            self._write_ttl(key)
        except Exception as e:
            logger.debug("Cache write failed: %s", e)

    # ── Cache management ──

    def invalidate(self, key: str):
        """Remove a specific cache entry."""
        for path in [self._csv_path(key), self._json_path(key), self._ttl_path(key)]:
            if path.exists():
                path.unlink()

    def clear_all(self):
        """Clear all cached data."""
        for d in [self.csv_dir, self.json_dir, self.cache_dir]:
            if d.exists():
                for f in d.iterdir():
                    if f.is_file():
                        f.unlink()
        logger.info("Cache cleared")

    def stats(self) -> dict:
        """Return cache statistics."""
        csv_count = len(list(self.csv_dir.glob("*.csv"))) if self.csv_dir.exists() else 0
        json_count = len(list(self.json_dir.glob("*.json"))) if self.json_dir.exists() else 0
        total_size = sum(
            f.stat().st_size for d in [self.csv_dir, self.json_dir]
            if d.exists() for f in d.iterdir() if f.is_file()
        )
        return {
            "csv_entries": csv_count,
            "json_entries": json_count,
            "total_size_bytes": total_size,
        }


# Global cache instance
_cache: DataCache | None = None


def get_cache() -> DataCache:
    global _cache
    if _cache is None:
        _cache = DataCache()
    return _cache

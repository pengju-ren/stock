"""Base vendor class — rate limiting, retry, caching interface.

All data vendors extend this to get consistent throttling, retry, and cache behavior.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseVendor(ABC):
    """Abstract base for all data vendors.

    Subclasses implement the actual HTTP/TCP calls; the base provides
    rate-limiting, retry with jitter, and a cache hook.
    """

    # Override in subclass
    name: str = "base"

    # Rate limiting
    min_interval: float = 0.0  # seconds between calls (0 = no limit)
    _last_call: float = 0.0

    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    # Cache (set by router)
    cache: Any | None = None

    def _throttle(self) -> None:
        """Enforce minimum interval between calls with random jitter."""
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed + random.uniform(0.05, 0.3)
            time.sleep(sleep_time)

    def _mark_call(self) -> None:
        """Record call timestamp for throttling."""
        self._last_call = time.time()

    def _retry_sleep(self, attempt: int) -> None:
        """Exponential backoff with jitter."""
        delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
        time.sleep(delay)

    def _should_retry(self, status_code: int | None, attempt: int) -> bool:
        """Determine if a request should be retried."""
        if attempt >= self.max_retries:
            return False
        if status_code is None:
            return True  # Network error
        return status_code in (429, 502, 503, 504)

    @abstractmethod
    def health_check(self) -> bool:
        """Quick connectivity test. Returns True if vendor is reachable."""
        ...


class ThrottledSession:
    """A requests.Session wrapper that enforces rate limits + random jitter.

    Used by HTTP-based vendors (Eastmoney, etc.) to avoid IP bans.
    All eastmoney.com requests route through this to serialize calls.
    """

    def __init__(self, min_interval: float = 1.0, user_agent: str = ""):
        import requests as _requests

        self.session = _requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.min_interval = min_interval
        self._last_call = 0.0

    def get(self, url: str, params: dict | None = None,
            headers: dict | None = None, timeout: int = 15, **kwargs):
        """Throttled GET with jitter."""
        wait = self.min_interval - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.5))
        try:
            return self.session.get(
                url, params=params, headers=headers, timeout=timeout, **kwargs
            )
        finally:
            self._last_call = time.time()

    def post(self, url: str, json: dict | None = None,
             data: dict | None = None, headers: dict | None = None,
             timeout: int = 15, **kwargs):
        """Throttled POST with jitter."""
        wait = self.min_interval - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.5))
        try:
            return self.session.post(
                url, json=json, data=data, headers=headers, timeout=timeout, **kwargs
            )
        finally:
            self._last_call = time.time()

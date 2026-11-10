"""The only two HTTP clients in the pipeline.

Every EDGAR request goes through :class:`SecClient`, which sets the
User-Agent and enforces the rate limit, so a bug elsewhere cannot get the IP
blocked. Every talent-network request goes through :class:`TalentClient`,
which adds ``?source=just-raised``.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from . import config

log = logging.getLogger(__name__)


class _RateLimiter:
    """Minimum spacing between requests, shared by every thread."""

    def __init__(self, max_per_second: float) -> None:
        self._interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._interval


def _get_with_retry(client: httpx.Client, url: str, params: dict | None, before=None) -> httpx.Response:
    delay = 2.0
    for attempt in range(5):
        if before:
            before()
        try:
            resp = client.get(url, params=params)
        except httpx.TransportError as exc:
            log.warning("GET %s failed (%s), retry %d", url, exc, attempt + 1)
        else:
            if resp.status_code not in (429, 500, 502, 503, 504):
                return resp
            log.warning("GET %s -> %d, retry %d", url, resp.status_code, attempt + 1)
            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                delay = max(delay, float(retry_after))
        time.sleep(delay)
        delay *= 2
    resp.raise_for_status()  # type: ignore[possibly-undefined]
    return resp  # type: ignore[possibly-undefined]


class SecClient:
    _limiter = _RateLimiter(config.SEC_MAX_RPS)  # one limiter per process

    def __init__(self, cache_dir: Path = config.CACHE) -> None:
        self.cache_dir = cache_dir
        self.requests = 0
        self._client = httpx.Client(
            headers={"User-Agent": config.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            timeout=30.0,
            follow_redirects=True,
        )

    def _wait(self) -> None:
        self._limiter.wait()
        self.requests += 1

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return _get_with_retry(self._client, url, params, before=self._wait)

    def get_json(self, url: str, params: dict | None = None) -> Any:
        resp = self.get(url, params)
        resp.raise_for_status()
        return resp.json()

    def get_cached(self, url: str, cache_path: Path, refresh: bool = False) -> bytes | None:
        """Fetch once, then serve from disk forever. None on 404."""
        if cache_path.exists() and not refresh:
            return cache_path.read_bytes()
        resp = self.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp.write_bytes(resp.content)
        tmp.replace(cache_path)
        return resp.content

    def close(self) -> None:
        self._client.close()


class TalentClient:
    # Their API rate-limits bursts (429 after about ten quick calls); a nightly
    # job has no reason to hurry.
    _limiter = _RateLimiter(config.TALENT_MAX_RPS)

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=config.TALENT_BASE, timeout=30.0)

    def get(self, path: str, **params: Any) -> Any | None:
        params = {**params, "source": config.SOURCE_TAG}
        resp = _get_with_retry(self._client, path, params, before=self._limiter.wait)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_site_text(self, path: str) -> str:
        """A machine-readable page outside /api/v1, such as /jobs.md."""
        resp = _get_with_retry(self._client, f"{config.TALENT_SITE}{path}", None, before=self._limiter.wait)
        resp.raise_for_status()
        return resp.text

    def close(self) -> None:
        self._client.close()

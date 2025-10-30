"""Abstract API client with common HTTP logic."""
from __future__ import annotations

import abc
import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
try:
    from diskcache import Cache  # type: ignore
except Exception:  # noqa: BLE001
    Cache = None  # type: ignore

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

class APIClientError(RuntimeError):
    pass

class BaseAPIClient(abc.ABC):
    name: str = "base"

    def __init__(self, base_url: str, token: Optional[str] = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        settings = get_settings()
        timeout = settings.network.http_timeout
        # Some httpx versions may not accept 'proxies' in Client init reliably across platforms; omit for now.
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, verify=verify_ssl)
        self._cache = None
        # Lazy enable cache when env flags will exist; guarded to avoid mandatory dependency
        cache_enabled = getattr(settings.network, 'cache_enabled', False)
        if cache_enabled and Cache:
            cache_dir = Path(getattr(settings.network, 'cache_dir', '.api_cache'))
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache = Cache(str(cache_dir))
            self._cache_ttl = int(getattr(settings.network, 'cache_ttl', 300))

    @abc.abstractmethod
    def auth_headers(self) -> Dict[str, str]:
        ...

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = path if path.startswith('/') else f"/{path}"
        headers = kwargs.pop('headers', {})
        headers.update(self.auth_headers())
        logger.debug("%s request %s %s", self.name.upper(), method, url)
        cache_key = None
        use_cache = self._cache is not None and method.upper() == 'GET'
        if use_cache:
            import hashlib, json as _json
            cache_key = hashlib.sha256(
                (self.name + method + url + _json.dumps(kwargs.get('params') or {}, sort_keys=True)).encode()
            ).hexdigest()
            if cache_key in self._cache:  # type: ignore[operator]
                cached = self._cache[cache_key]  # type: ignore[index]
                return httpx.Response(200, request=httpx.Request(method, url), json=cached)
        try:
            resp = self._client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as e:
            raise APIClientError(f"HTTP error for {self.name}: {e}") from e
        if resp.status_code >= 400:
            snippet = resp.text[:500]
            raise APIClientError(f"API {self.name} error {resp.status_code}: {snippet}")
        if use_cache and cache_key:
            try:
                self._cache.set(cache_key, resp.json(), expire=self._cache_ttl)  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
        return resp

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self._request("GET", path, params=params)
        try:
            return r.json()
        except json.JSONDecodeError as e:
            raise APIClientError(f"Invalid JSON from {self.name}: {e}") from e

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

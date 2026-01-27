"""Base client and utilities for WB API SDK."""

import asyncio
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Callable, Self

import httpx
import ijson  # type: ignore[import-not-found]

from .exceptions import WBAPIError, WBAuthError, WBRateLimitError
from .types import APIItem, APIResult


class PingCache:
    """Simple in-memory cache with TTL for ping responses.

    Used to cache ping results to avoid hitting rate limits (3 req/30sec).
    """

    def __init__(self, ttl: float = 30.0) -> None:
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.monotonic() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value with current timestamp."""
        self._cache[key] = (value, time.monotonic())

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


@dataclass
class RetryConfig:
    """Configuration for automatic retry with exponential backoff.

    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay between retries.
        exponential_base: Multiplier for exponential backoff.
        jitter: If True, randomize delays to avoid thundering herd.
        retry_on_statuses: HTTP status codes that trigger retry.
        on_retry: Optional callback called before each retry.
    """

    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    on_retry: Callable[[int, float, Exception], None] | None = None

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay


@dataclass
class BaseAPIClient:
    """Base async client for WB API.

    Features:
    - Async context manager
    - Rate limiting via asyncio.Semaphore
    - Automatic retry with exponential backoff
    - Ping caching with TTL=30sec
    - Streaming support with ijson (optional)

    Attributes:
        token: API authorization token.
        base_url: Base URL for the API service.
        max_concurrent: Maximum concurrent requests (rate limiting).
        retry_config: Configuration for retry behavior.
        timeout: Request timeout in seconds.
    """

    token: str
    base_url: str
    max_concurrent: int = 10
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    timeout: float = 30.0

    _client: httpx.AsyncClient = field(init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)
    _ping_cache: PingCache = field(init=False, repr=False, default_factory=PingCache)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._ping_cache = PingCache(ttl=30.0)

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": self.token},
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    def _safe_json(self, response: httpx.Response) -> dict[str, Any]:
        """Safely parse JSON response, return empty dict on failure."""
        try:
            return response.json()
        except Exception:
            return {}

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise exception for non-2xx status codes."""
        status = response.status_code

        if 200 <= status < 300:
            return

        response_data = self._safe_json(response)
        message = response_data.get("title", f"HTTP {status}")

        if status == 401:
            raise WBAuthError(message, status_code=status, response_data=response_data)

        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise WBRateLimitError(
                message,
                status_code=status,
                retry_after=float(retry_after) if retry_after else None,
                response_data=response_data,
            )

        raise WBAPIError(message, status_code=status, response_data=response_data)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with rate limiting and retry logic."""
        async with self._semaphore:
            last_exception: Exception | None = None

            for attempt in range(self.retry_config.max_retries + 1):
                try:
                    response = await self._client.request(method, endpoint, **kwargs)

                    # 401 - no retry
                    if response.status_code == 401:
                        self._raise_for_status(response)

                    # Retry on configured statuses (429, 5xx)
                    if response.status_code in self.retry_config.retry_on_statuses:
                        if attempt < self.retry_config.max_retries:
                            delay = self.retry_config.calculate_delay(attempt)
                            if self.retry_config.on_retry:
                                exc = WBAPIError(
                                    f"HTTP {response.status_code}",
                                    status_code=response.status_code,
                                )
                                self.retry_config.on_retry(attempt, delay, exc)
                            await asyncio.sleep(delay)
                            continue
                        # Max retries reached
                        self._raise_for_status(response)

                    # Any other non-2xx - raise immediately
                    self._raise_for_status(response)

                    return response

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    last_exception = e
                    if attempt < self.retry_config.max_retries:
                        delay = self.retry_config.calculate_delay(attempt)
                        if self.retry_config.on_retry:
                            self.retry_config.on_retry(attempt, delay, e)
                        await asyncio.sleep(delay)
                        continue
                    raise WBAPIError(f"Network error: {e}") from e

            # Should not reach here, but just in case
            raise WBAPIError(
                f"Request failed: {last_exception}"
            ) from last_exception

    async def get(self, endpoint: str, **kwargs: Any) -> APIResult | list[Any]:
        """Make GET request and return JSON response."""
        response = await self._request("GET", endpoint, **kwargs)
        if response.status_code == 204:
            return []
        return response.json()

    async def stream_get(
        self,
        endpoint: str,
        json_path: str = "item",
        transform: Callable[[APIItem], APIItem] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[APIItem]:
        """Make GET request with streaming JSON parsing.

        Memory-efficient method that parses JSON incrementally using ijson.
        Yields items one by one without loading full response into memory.

        Args:
            endpoint: API endpoint path.
            json_path: JSON path for ijson iteration.
                - "item" for root array [{...}, {...}]
                - "result.item" for {"result": [{...}, {...}]}
            transform: Optional callback to transform each item before yielding.
            **kwargs: Additional arguments passed to httpx (params, headers, etc).

        Yields:
            Individual items from the JSON response.

        Raises:
            WBAPIError: If API returns an error.

        Note:
            Connection stays open during iteration - avoid slow processing.
        """
        async with self._semaphore:
            async with self._client.stream("GET", endpoint, **kwargs) as response:
                if response.status_code == 204:
                    return

                self._raise_for_status(response)

                async for item in ijson.items_async(
                    response.aiter_bytes(), json_path
                ):
                    yield transform(item) if transform else item

    async def stream_post(
        self,
        endpoint: str,
        json: Any = None,
        json_path: str = "item",
        transform: Callable[[APIItem], APIItem] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[APIItem]:
        """Make POST request with streaming JSON parsing.

        Same as stream_get() but for POST requests.
        Useful for APIs like OZON where all methods use POST.

        Args:
            endpoint: API endpoint path.
            json: JSON body to send.
            json_path: JSON path for ijson iteration.
            transform: Optional callback to transform each item.
            **kwargs: Additional arguments passed to httpx.

        Yields:
            Individual items from the JSON response.
        """
        async with self._semaphore:
            async with self._client.stream(
                "POST", endpoint, json=json, **kwargs
            ) as response:
                if response.status_code == 204:
                    return

                self._raise_for_status(response)

                async for item in ijson.items_async(
                    response.aiter_bytes(), json_path
                ):
                    yield transform(item) if transform else item

    async def post(self, endpoint: str, json: Any = None, **kwargs: Any) -> APIResult:
        """Make POST request and return JSON response."""
        response = await self._request("POST", endpoint, json=json, **kwargs)
        return response.json()

    async def put(self, endpoint: str, json: Any = None, **kwargs: Any) -> APIResult:
        """Make PUT request and return JSON response."""
        response = await self._request("PUT", endpoint, json=json, **kwargs)
        return response.json()

    async def delete(self, endpoint: str, **kwargs: Any) -> APIResult:
        """Make DELETE request and return JSON response."""
        response = await self._request("DELETE", endpoint, **kwargs)
        return response.json()

    async def patch(self, endpoint: str, json: Any = None, **kwargs: Any) -> APIResult:
        """Make PATCH request and return JSON response."""
        response = await self._request("PATCH", endpoint, json=json, **kwargs)
        return response.json()

    async def ping(self, endpoint: str = "/ping") -> APIResult:
        """Check service availability with caching.

        Results are cached for 30 seconds to respect rate limits
        (3 requests per 30 seconds).

        Args:
            endpoint: Ping endpoint path (default: /ping).

        Returns:
            Ping response from API or cached result.
        """
        cache_key = f"{self.base_url}{endpoint}"
        cached = self._ping_cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._request("GET", endpoint)
        result: APIResult = response.json()
        self._ping_cache.set(cache_key, result)
        return result

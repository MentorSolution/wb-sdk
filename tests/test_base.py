"""Tests for BaseAPIClient."""

import httpx
import pytest
import respx

from wb_api_sdk import StatisticAPIClient, WBAPIError, WBAuthError, WBRateLimitError
from wb_api_sdk.base import RetryConfig

BASE_URL = "https://statistics-api.wildberries.ru"


class TestGetMethod:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_success(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.get("/test")

        assert result == {"data": "value"}
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_204_returns_empty_list(self) -> None:
        respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(204)
        )

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.get("/test")

        assert result == []


class TestErrorHandling:
    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_error_401_no_retry(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized"})
        )

        async with StatisticAPIClient(token="bad-token") as client:
            with pytest.raises(WBAuthError) as exc_info:
                await client.get("/test")

        assert exc_info.value.status_code == 401
        assert exc_info.value.message == "Unauthorized"
        assert route.call_count == 1  # No retry

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_429_retries(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(
                429,
                json={"title": "Too Many Requests"},
                headers={"Retry-After": "5"},
            )
        )

        retry_config = RetryConfig(max_retries=2, base_delay=0.01)
        async with StatisticAPIClient(
            token="test-token", retry_config=retry_config
        ) as client:
            with pytest.raises(WBRateLimitError) as exc_info:
                await client.get("/test")

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 5.0
        assert route.call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_error_retries(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(500, json={"title": "Internal Error"})
        )

        retry_config = RetryConfig(max_retries=2, base_delay=0.01)
        async with StatisticAPIClient(
            token="test-token", retry_config=retry_config
        ) as client:
            with pytest.raises(WBAPIError) as exc_info:
                await client.get("/test")

        assert exc_info.value.status_code == 500
        assert route.call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_error_recovers(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        retry_config = RetryConfig(max_retries=2, base_delay=0.01)
        async with StatisticAPIClient(
            token="test-token", retry_config=retry_config
        ) as client:
            result = await client.get("/test")

        assert result == {"ok": True}
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_client_error_no_retry(self) -> None:
        route = respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(400, json={"title": "Bad Request"})
        )

        async with StatisticAPIClient(token="test-token") as client:
            with pytest.raises(WBAPIError) as exc_info:
                await client.get("/test")

        assert exc_info.value.status_code == 400
        assert route.call_count == 1  # No retry for 4xx (except 429)


class TestPingCaching:
    @pytest.mark.asyncio
    @respx.mock
    async def test_ping_cached(self) -> None:
        route = respx.get(f"{BASE_URL}/ping").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        async with StatisticAPIClient(token="test-token") as client:
            result1 = await client.ping()
            result2 = await client.ping()

        assert result1 == {"status": "ok"}
        assert result2 == {"status": "ok"}
        assert route.call_count == 1  # Second call uses cache


class TestStreaming:
    """Streaming tests require real HTTP responses.

    respx mocks don't provide file-like interface that ijson needs.
    These tests are skipped - use integration tests with sandbox for streaming.
    """

    @pytest.mark.skip(reason="respx mock incompatible with ijson streaming")
    @pytest.mark.asyncio
    @respx.mock
    async def test_stream_get_yields_items(self) -> None:
        json_data = b'[{"id": 1}, {"id": 2}, {"id": 3}]'
        respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(200, content=json_data)
        )

        async with StatisticAPIClient(token="test-token") as client:
            items = [item async for item in client.stream_get("/test")]

        assert items == [{"id": 1}, {"id": 2}, {"id": 3}]

    @pytest.mark.skip(reason="respx mock incompatible with ijson streaming")
    @pytest.mark.asyncio
    @respx.mock
    async def test_stream_get_with_transform(self) -> None:
        json_data = b'[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]'
        respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(200, content=json_data)
        )

        async with StatisticAPIClient(token="test-token") as client:
            items = [
                item
                async for item in client.stream_get(
                    "/test", transform=lambda x: {"id": x["id"]}
                )
            ]

        assert items == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    @respx.mock
    async def test_stream_get_204_empty(self) -> None:
        respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(204)
        )

        async with StatisticAPIClient(token="test-token") as client:
            items = [item async for item in client.stream_get("/test")]

        assert items == []


class TestRetryCallback:
    @pytest.mark.asyncio
    @respx.mock
    async def test_on_retry_called(self) -> None:
        respx.get(f"{BASE_URL}/test").mock(
            return_value=httpx.Response(500)
        )

        retries_log: list[tuple[int, float]] = []

        def on_retry(attempt: int, delay: float, exc: Exception) -> None:
            retries_log.append((attempt, delay))

        retry_config = RetryConfig(max_retries=2, base_delay=0.01, on_retry=on_retry)
        async with StatisticAPIClient(
            token="test-token", retry_config=retry_config
        ) as client:
            with pytest.raises(WBAPIError):
                await client.get("/test")

        assert len(retries_log) == 2
        assert retries_log[0][0] == 0  # First retry attempt
        assert retries_log[1][0] == 1  # Second retry attempt

"""Tests for ReportsAPI."""

from datetime import date, datetime

import httpx
import pytest
import respx

from wb_api_sdk import StatisticAPIClient
from wb_api_sdk.statistic.reports import ReportsAPI

BASE_URL = "https://statistics-api.wildberries.ru"
ENDPOINT = "/api/v5/supplier/reportDetailByPeriod"


class TestDateFormatting:
    def test_format_date(self) -> None:
        reports = ReportsAPI(None)  # type: ignore[arg-type]

        assert reports._format_date(date(2024, 1, 15)) == "2024-01-15"
        assert reports._format_date(datetime(2024, 1, 15, 10, 30, 0)) == "2024-01-15T10:30:00"
        assert reports._format_date("2024-01-15") == "2024-01-15"


class TestGetReportDetailByPeriod:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_page(self) -> None:
        data = [{"rrd_id": 1, "nm_id": 100}, {"rrd_id": 2, "nm_id": 200}]
        respx.get(f"{BASE_URL}{ENDPOINT}").mock(
            return_value=httpx.Response(200, json=data)
        )

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
            )

        assert result == data

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_all_pagination(self) -> None:
        page1 = [{"rrd_id": 1}, {"rrd_id": 2}]
        page2 = [{"rrd_id": 3}]

        route = respx.get(f"{BASE_URL}{ENDPOINT}").mock(
            side_effect=[
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
                httpx.Response(200, json=[]),  # Empty page signals end
            ]
        )

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                fetch_all=True,
            )

        assert result == [{"rrd_id": 1}, {"rrd_id": 2}, {"rrd_id": 3}]
        assert route.call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_transform(self) -> None:
        data = [
            {"rrd_id": 1, "nm_id": 100, "quantity": 5, "extra": "ignore"},
            {"rrd_id": 2, "nm_id": 200, "quantity": 3, "extra": "ignore"},
        ]
        respx.get(f"{BASE_URL}{ENDPOINT}").mock(
            return_value=httpx.Response(200, json=data)
        )

        def slim(item: dict) -> dict:
            return {"nm_id": item["nm_id"], "quantity": item["quantity"]}

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                transform=slim,
            )

        assert result == [
            {"nm_id": 100, "quantity": 5},
            {"nm_id": 200, "quantity": 3},
        ]

    @pytest.mark.asyncio
    @respx.mock
    async def test_204_returns_empty_list(self) -> None:
        respx.get(f"{BASE_URL}{ENDPOINT}").mock(
            return_value=httpx.Response(204)
        )

        async with StatisticAPIClient(token="test-token") as client:
            result = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
            )

        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_params_passed_correctly(self) -> None:
        route = respx.get(f"{BASE_URL}{ENDPOINT}").mock(
            return_value=httpx.Response(200, json=[])
        )

        async with StatisticAPIClient(token="test-token") as client:
            await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                limit=50000,
                rrdid=12345,
                period="daily",
            )

        assert route.called
        request = route.calls.last.request
        assert "dateFrom=2024-01-01" in str(request.url)
        assert "dateTo=2024-01-31" in str(request.url)
        assert "limit=50000" in str(request.url)
        assert "rrdid=12345" in str(request.url)
        assert "period=daily" in str(request.url)


class TestStreamReportDetailByPeriod:
    """Streaming tests use requests (sync) + ijson.

    Unit tests for streaming require mocking requests library.
    For now, streaming is tested via integration tests (test_integration.py).
    """

    def test_stream_method_exists(self) -> None:
        """Verify stream method exists and is sync (not async)."""
        from wb_api_sdk.statistic.reports import ReportsAPI
        import inspect

        assert hasattr(ReportsAPI, "stream_report_detail_by_period")
        method = getattr(ReportsAPI, "stream_report_detail_by_period")
        assert not inspect.iscoroutinefunction(method)

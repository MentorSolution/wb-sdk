"""Reports API for Statistics service."""

from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import TYPE_CHECKING, Callable, Literal

from wb_api_sdk.endpoints import StatisticsEndpoints
from wb_api_sdk.types import APIItem, APIItemsList

if TYPE_CHECKING:
    from wb_api_sdk.statistics.client import StatisticsAPIClient


class ReportsAPI:
    """Reports subclient for Statistics API."""

    def __init__(self, client: "StatisticsAPIClient") -> None:
        self._client = client

    def _format_date(self, value: date | datetime | str) -> str:
        """Format date/datetime to RFC3339 string."""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return value

    async def get_report_detail_by_period(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        limit: int = 100000,
        rrdid: int = 0,
        period: Literal["weekly", "daily"] = "weekly",
        fetch_all: bool = False,
        transform: Callable[[APIItem], APIItem] | None = None,
    ) -> APIItemsList:
        """Get sales report by realization period.

        Args:
            date_from: Report start date (RFC3339 format, Moscow timezone UTC+3).
            date_to: Report end date (RFC3339 format, Moscow timezone UTC+3).
            limit: Number of rows in response (max 100000).
            rrdid: Unique row ID for pagination. Start with 0, then use rrd_id
                   from last row of previous response.
            period: Report frequency - "weekly" or "daily".
            fetch_all: If True, fetches all pages automatically.
                       If False, returns single page (use rrdid for manual pagination).
            transform: Optional callback to transform each item.

        Returns:
            List of report rows. Empty list if no data (HTTP 204).
        """
        if fetch_all:
            all_rows: APIItemsList = []
            current_rrdid = 0

            while True:
                params = {
                    "dateFrom": self._format_date(date_from),
                    "dateTo": self._format_date(date_to),
                    "limit": limit,
                    "rrdid": current_rrdid,
                    "period": period,
                }
                result = await self._client.get(
                    StatisticsEndpoints.REPORT_DETAIL_BY_PERIOD,
                    params=params,
                )
                rows = result if isinstance(result, list) else []
                if not rows:
                    break

                if transform:
                    rows = [transform(row) for row in rows]
                all_rows.extend(rows)
                current_rrdid = rows[-1].get("rrd_id", 0)

            return all_rows

        params = {
            "dateFrom": self._format_date(date_from),
            "dateTo": self._format_date(date_to),
            "limit": limit,
            "rrdid": rrdid,
            "period": period,
        }
        result = await self._client.get(
            StatisticsEndpoints.REPORT_DETAIL_BY_PERIOD,
            params=params,
        )
        rows = result if isinstance(result, list) else []
        if transform:
            return [transform(row) for row in rows]
        return rows

    def stream_report_detail_by_period(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        limit: int = 100000,
        period: Literal["weekly", "daily"] = "weekly",
        fetch_all: bool = False,
        transform: Callable[[APIItem], APIItem] | None = None,
    ) -> AsyncIterator[APIItem]:
        """Stream sales report by realization period.

        Memory-efficient streaming version. Returns AsyncIterator directly
        (no await needed before async for).

        Args:
            date_from: Report start date (RFC3339 format, Moscow timezone UTC+3).
            date_to: Report end date (RFC3339 format, Moscow timezone UTC+3).
            limit: Number of rows in response (max 100000).
            period: Report frequency - "weekly" or "daily".
            fetch_all: If True, fetches all pages automatically.
            transform: Optional callback to transform each item.

        Returns:
            AsyncIterator yielding report rows one by one.
        """
        return self._stream_with_pagination(
            date_from, date_to, limit, period, fetch_all, transform
        )

    async def _stream_with_pagination(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        limit: int,
        period: Literal["weekly", "daily"],
        fetch_all: bool,
        transform: Callable[[APIItem], APIItem] | None,
    ) -> AsyncIterator[APIItem]:
        """Stream report with pagination support."""
        current_rrdid = 0

        while True:
            params = {
                "dateFrom": self._format_date(date_from),
                "dateTo": self._format_date(date_to),
                "limit": limit,
                "rrdid": current_rrdid,
                "period": period,
            }

            last_rrdid = 0
            row_count = 0

            async for item in self._client.stream_get(
                StatisticsEndpoints.REPORT_DETAIL_BY_PERIOD,
                json_path="item",
                transform=transform,
                params=params,
            ):
                yield item
                last_rrdid = item.get("rrd_id", 0)
                row_count += 1

            if row_count == 0 or not fetch_all:
                return

            current_rrdid = last_rrdid

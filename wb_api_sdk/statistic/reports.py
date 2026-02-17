"""Reports API for Statistics service."""

from collections.abc import Iterator
from datetime import date, datetime
from typing import TYPE_CHECKING, Callable, Literal

import ijson  # type: ignore[import-not-found]
import requests

from wb_api_sdk.endpoints import StatisticsEndpoints
from wb_api_sdk.exceptions import WBAPIError, WBAuthError, WBRateLimitError
from wb_api_sdk.types import APIItem, APIItemsList

if TYPE_CHECKING:
    from wb_api_sdk.statistic.client import StatisticAPIClient


class ReportsAPI:
    """Reports subclient for Statistics API."""

    def __init__(self, client: "StatisticAPIClient") -> None:
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

                last_rrdid = rows[-1].get("rrd_id", 0)
                if transform:
                    rows = [transform(row) for row in rows]
                all_rows.extend(rows)

                if last_rrdid == current_rrdid:
                    break
                current_rrdid = last_rrdid

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
        timeout: int = 120,
    ) -> Iterator[APIItem]:
        """Stream sales report by realization period.

        Memory-efficient streaming version using requests + ijson.
        Parses JSON row-by-row without loading full response into memory.

        Note: This is a sync method (uses requests, not httpx).
        Can be called from async code without issues.

        Args:
            date_from: Report start date (RFC3339 format, Moscow timezone UTC+3).
            date_to: Report end date (RFC3339 format, Moscow timezone UTC+3).
            limit: Number of rows per page (max 100000).
            period: Report frequency - "weekly" or "daily".
            fetch_all: If True, fetches all pages automatically.
            transform: Optional callback to transform each item.
            timeout: Request timeout in seconds.

        Yields:
            Report rows one by one.
        """
        base_url = self._client.base_url
        token = self._client.token
        endpoint = StatisticsEndpoints.REPORT_DETAIL_BY_PERIOD

        current_rrdid = 0

        while True:
            url = (
                f"{base_url}{endpoint}"
                f"?dateFrom={self._format_date(date_from)}"
                f"&dateTo={self._format_date(date_to)}"
                f"&limit={limit}"
                f"&rrdid={current_rrdid}"
                f"&period={period}"
            )
            headers = {"Authorization": token}

            with requests.get(
                url, headers=headers, stream=True, timeout=timeout
            ) as resp:
                if resp.status_code == 204:
                    return

                if resp.status_code == 401:
                    raise WBAuthError(
                        "Unauthorized", status_code=401, response_data={}
                    )

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    raise WBRateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                        retry_after=float(retry_after) if retry_after else None,
                    )

                if resp.status_code != 200:
                    raise WBAPIError(
                        f"HTTP {resp.status_code}",
                        status_code=resp.status_code,
                        response_data={},
                    )

                last_rrdid = 0
                row_count = 0

                for item in ijson.items(resp.raw, "item"):
                    rrd_id = item.get("rrd_id", 0)
                    if transform:
                        item = transform(item)
                    yield item
                    last_rrdid = rrd_id
                    row_count += 1

                if row_count == 0 or not fetch_all:
                    return

                if last_rrdid == current_rrdid:
                    return

                current_rrdid = last_rrdid

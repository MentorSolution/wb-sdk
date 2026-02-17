"""Statistics API client."""

from dataclasses import dataclass, field

from wb_api_sdk.base import BaseAPIClient
from wb_api_sdk.endpoints import BaseURLs
from .reports import ReportsAPI


@dataclass
class StatisticAPIClient(BaseAPIClient):
    """Client for WB Statistics API.

    Usage:
        async with StatisticsAPIClient(token="your-token") as client:
            report = await client.reports.get_report_detail_by_period(
                date_from="2024-01-01",
                date_to="2024-01-31",
            )
    """

    base_url: str = BaseURLs.STATISTICS

    reports: ReportsAPI = field(init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.reports = ReportsAPI(self)

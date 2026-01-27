"""Example usage of WB API SDK."""

import asyncio
from datetime import date

from wb_api_sdk import StatisticsAPIClient, WBAuthError


async def main() -> None:
    """Example: Fetch sales report from Statistics API."""
    async with StatisticsAPIClient(token="your-api-token") as client:
        try:
            # Standard mode - all data in memory
            report = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                fetch_all=True,
            )
            print(f"Got {len(report)} rows")

            # With transform - keep only needed fields
            def slim(item: dict) -> dict:
                return {k: item[k] for k in ["nm_id", "quantity", "retail_price"]}

            report = await client.reports.get_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                transform=slim,
            )
            print(f"Slim report: {report[:2]}")

            # Streaming mode - memory efficient
            row_count = 0
            async for item in client.reports.stream_report_detail_by_period(
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                fetch_all=True,
                transform=slim,
            ):
                row_count += 1
            print(f"Streamed {row_count} rows")

        except WBAuthError as e:
            print(f"Auth error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

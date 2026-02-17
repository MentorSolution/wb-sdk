"""Integration tests against real WB API.

Run with:
    uv run pytest tests/test_integration.py -m integration -v -s

The -s flag is required to allow interactive token input.
"""

import csv
import getpass
import json
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Generator

import pytest

from wb_api_sdk import StatisticAPIClient


@contextmanager
def profile(name: str) -> Generator[None, None, None]:
    """Context manager for profiling time and memory."""
    tracemalloc.start()
    start_time = time.perf_counter()
    start_mem = tracemalloc.get_traced_memory()[0]

    print(f"\n[{name}] Starting...")

    try:
        yield
    finally:
        end_time = time.perf_counter()
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        elapsed = end_time - start_time
        mem_used = (peak_mem - start_mem) / 1024 / 1024  # MB

        print(f"[{name}] Completed in {elapsed:.2f}s, peak memory: {mem_used:.1f} MB")

DEBUG_FILES_DIR = Path(__file__).parent / "debug_files"


def _can_be_csv(data: Any) -> bool:
    """Check if data can be converted to CSV (list of dicts)."""
    if not isinstance(data, list) or not data:
        return False
    return all(isinstance(item, dict) for item in data)


def _get_all_keys(data: list[dict]) -> list[str]:
    """Get all unique keys from list of dicts, preserving order."""
    keys: dict[str, None] = {}
    for item in data:
        for key in item.keys():
            keys[key] = None
    return list(keys.keys())


@pytest.fixture(scope="session")
def api_token() -> str:
    """Prompt for API token securely (not echoed to terminal)."""
    token = getpass.getpass("WB API Token: ")
    if not token:
        pytest.skip("No token provided")
    return token


@pytest.fixture(scope="session")
def date_range() -> tuple[date, date]:
    """Prompt for date range. Press Enter for defaults (last 7 days)."""
    today = date.today()
    week_ago = date(today.year, today.month, max(1, today.day - 7))

    date_from_str = input(f"Date from [{week_ago}]: ").strip()
    date_to_str = input(f"Date to [{today}]: ").strip()

    if date_from_str:
        date_from = date.fromisoformat(date_from_str)
    else:
        date_from = week_ago

    if date_to_str:
        date_to = date.fromisoformat(date_to_str)
    else:
        date_to = today

    print(f"Using date range: {date_from} to {date_to}")
    return date_from, date_to


@pytest.fixture(scope="session")
def debug_dir() -> Path:
    """Create timestamped debug directory for this test session."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    session_dir = DEBUG_FILES_DIR / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nDebug files directory: {session_dir}")
    return session_dir


@pytest.fixture
def save_debug_response(debug_dir: Path):
    """Factory fixture to save API responses for debugging.

    Saves as CSV if data is list of dicts, otherwise saves as JSON.
    Files saved to: debug_files/<timestamp>/<client>_<method>.<ext>
    """

    def _save(client_name: str, method_name: str, data: Any) -> Path:
        base_name = f"{client_name}_{method_name}"

        if _can_be_csv(data):
            filepath = debug_dir / f"{base_name}.csv"
            keys = _get_all_keys(data)

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)
        else:
            filepath = debug_dir / f"{base_name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        print(f"Saved: {filepath}")
        return filepath

    return _save


@pytest.mark.integration
async def test_statistics_get_report(
    api_token: str, date_range: tuple[date, date], save_debug_response
) -> None:
    """Test get_report_detail_by_period against real API."""
    date_from, date_to = date_range

    async with StatisticAPIClient(token=api_token) as client:
        with profile("get_report"):
            result = await client.reports.get_report_detail_by_period(
                date_from=date_from,
                date_to=date_to,
                fetch_all=True,
            )

        save_debug_response("statistics", "get_report", result)

        assert isinstance(result, list)
        print(f"Total rows: {len(result)}")


@pytest.mark.integration
async def test_statistics_stream_report(
    api_token: str, date_range: tuple[date, date], save_debug_response
) -> None:
    """Test stream_report_detail_by_period against real API."""
    date_from, date_to = date_range

    async with StatisticAPIClient(token=api_token) as client:
        items = []

        with profile("stream_report"):
            # Note: streaming is sync (uses requests), works fine in async context
            for item in client.reports.stream_report_detail_by_period(
                date_from=date_from,
                date_to=date_to,
                fetch_all=True,
            ):
                items.append(item)

        save_debug_response("statistics", "stream_report", items)

        assert isinstance(items, list)
        print(f"Total rows: {len(items)}")


@pytest.mark.integration
async def test_statistics_ping(api_token: str) -> None:
    """Test ping endpoint."""
    async with StatisticAPIClient(token=api_token) as client:
        result = await client.ping()

        print(f"\nPing response: {result}")
        assert result is not None


@pytest.mark.integration
async def test_get_report_with_aggregation(
    api_token: str, date_range: tuple[date, date], save_debug_response
) -> None:
    """Test get_report + aggregation transform profiling.

    Run with:
        uv run pytest tests/test_integration.py::test_get_report_with_aggregation -v -s
    """
    from tests.transform_aggregator import aggregate_rows_by_size_and_totals

    date_from, date_to = date_range

    async with StatisticAPIClient(token=api_token) as client:
        with profile("get_report (fetch)"):
            result = await client.reports.get_report_detail_by_period(
                date_from=date_from,
                date_to=date_to,
                fetch_all=True,
            )

        print(f"Total raw rows: {len(result)}")

        with profile("aggregate_rows_by_size_and_totals"):
            aggregated_rows, totals = aggregate_rows_by_size_and_totals(result)

        print(f"Aggregated rows: {len(aggregated_rows)}")
        print(f"Totals: {totals}")

        save_debug_response("statistics", "aggregated_rows", [asdict(r) for r in aggregated_rows])
        save_debug_response("statistics", "aggregated_totals", totals)


@pytest.mark.integration
async def test_stream_report_with_aggregation(
    api_token: str, date_range: tuple[date, date], save_debug_response
) -> None:
    """Test stream_report + streaming aggregation profiling.

    Run with:
        uv run pytest tests/test_integration.py::test_stream_report_with_aggregation -v -s
    """
    from tests.transform_aggregator import aggregate_rows_streaming

    date_from, date_to = date_range

    async with StatisticAPIClient(token=api_token) as client:

        def page_generator():
            """Wrap stream into page-sized chunks for streaming aggregation."""
            page: list[dict] = []
            page_size = 10000

            for item in client.reports.stream_report_detail_by_period(
                date_from=date_from,
                date_to=date_to,
                fetch_all=True,
            ):
                page.append(item)
                if len(page) >= page_size:
                    yield page
                    page = []

            if page:
                yield page

        with profile("stream_report + aggregate_rows_streaming"):
            aggregated_rows, totals = aggregate_rows_streaming(page_generator())

        print(f"Aggregated rows: {len(aggregated_rows)}")
        print(f"Totals: {totals}")

        save_debug_response("statistics", "stream_aggregated_rows", [asdict(r) for r in aggregated_rows])
        save_debug_response("statistics", "stream_aggregated_totals", totals)


@pytest.mark.supplier_oper_names
async def test_extract_supplier_oper_names(
    api_token: str, date_range: tuple[date, date], debug_dir: Path
) -> None:
    """Extract unique supplier_oper_name values from report.

    Run with:
        uv run pytest tests/test_integration.py -m supplier_oper_names -v -s
    """
    date_from, date_to = date_range

    async with StatisticAPIClient(token=api_token) as client:
        with profile("get_report"):
            result = await client.reports.get_report_detail_by_period(
                date_from=date_from,
                date_to=date_to,
                fetch_all=True,
            )

    unique_names: set[str] = set()
    for item in result:
        name = item.get("supplier_oper_name")
        if name:
            unique_names.add(name)

    sorted_names = sorted(unique_names)

    filepath = debug_dir / "supplier_oper_names.csv"
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["supplier_oper_name"])
        for name in sorted_names:
            writer.writerow([name])

    print(f"\nFound {len(sorted_names)} unique supplier_oper_name values")
    print(f"Saved: {filepath}")

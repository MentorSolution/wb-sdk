# WB API SDK

> **⚠️ Pre-Alpha | Active Development**
>
> This SDK is in early development stage. API may change without notice.
> Not recommended for production use yet.

Python SDK for Wildberries API. Thin async client with streaming support.

## Features

- **Async/await** — built on `httpx`
- **Automatic retries** — exponential backoff for 429/5xx errors
- **Rate limiting** — configurable concurrent request limit
- **Streaming** — memory-efficient JSON parsing with `ijson`
- **Transparent errors** — full WB API response in exceptions
- **Ping caching** — respects 3 req/30sec limit

## Requirements

- Python 3.13+
- httpx
- ijson
- requests (for sync streaming)

## Installation

```bash
# Using uv (recommended)
uv add wb-api-sdk

# From GitHub (latest)
uv add git+https://github.com/Kashikuroni/wb-api-sdk.git

# Using pip
pip install wb-api-sdk
```

For development:

```bash
git clone https://github.com/your-org/wb-api-sdk.git
cd wb-api-sdk
uv sync
```

## Quick Start

```python
import asyncio
from datetime import date
from wb_api_sdk import StatisticsAPIClient

async def main():
    async with StatisticsAPIClient(token="your-api-token") as client:
        # Fetch sales report
        report = await client.reports.get_report_detail_by_period(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            fetch_all=True,
        )
        print(f"Got {len(report)} rows")

asyncio.run(main())
```

## Usage

### Basic Report Fetching

```python
from wb_api_sdk import StatisticsAPIClient

async with StatisticsAPIClient(token="your-token") as client:
    # Single page (manual pagination)
    page = await client.reports.get_report_detail_by_period(
        date_from="2024-01-01",
        date_to="2024-01-31",
    )

    # All pages (automatic pagination)
    full_report = await client.reports.get_report_detail_by_period(
        date_from="2024-01-01",
        date_to="2024-01-31",
        fetch_all=True,
    )
```

### Transform Function

Reduce memory usage by keeping only needed fields:

```python
def slim(item: dict) -> dict:
    """Keep only essential fields."""
    return {
        "nm_id": item.get("nm_id"),
        "quantity": item.get("quantity"),
        "retail_amount": item.get("retail_amount"),
    }

report = await client.reports.get_report_detail_by_period(
    date_from="2024-01-01",
    date_to="2024-01-31",
    fetch_all=True,
    transform=slim,
)
```

### Streaming Mode

Memory-efficient processing for large reports:

```python
# Streaming uses sync requests + ijson (works in async context)
for item in client.reports.stream_report_detail_by_period(
    date_from="2024-01-01",
    date_to="2024-01-31",
    fetch_all=True,
):
    process(item)  # Items are yielded one by one
```

Combine streaming with transform:

```python
for item in client.reports.stream_report_detail_by_period(
    date_from="2024-01-01",
    date_to="2024-01-31",
    fetch_all=True,
    transform=slim,
):
    process(item)
```

### Ping with Caching

```python
# Cached for 30 seconds (respects 3 req/30sec limit)
result = await client.ping()
```

## Configuration

### Retry Configuration

```python
from wb_api_sdk import StatisticsAPIClient, RetryConfig

config = RetryConfig(
    max_retries=5,           # Maximum retry attempts
    base_delay=1.0,          # Initial delay (seconds)
    max_delay=60.0,          # Maximum delay between retries
    exponential_base=2.0,    # Multiplier for backoff
    jitter=True,             # Randomize delays
    retry_on_statuses=(429, 500, 502, 503, 504),
)

async with StatisticsAPIClient(
    token="your-token",
    retry_config=config,
) as client:
    ...
```

### Retry Callback

```python
def on_retry(attempt: int, delay: float, error: Exception):
    print(f"Retry {attempt}, waiting {delay:.1f}s: {error}")

config = RetryConfig(on_retry=on_retry)
```

### Rate Limiting

```python
async with StatisticsAPIClient(
    token="your-token",
    max_concurrent=5,  # Maximum concurrent requests (default: 10)
    timeout=60.0,      # Request timeout in seconds (default: 30)
) as client:
    ...
```

### Sandbox Mode

```python
from wb_api_sdk import StatisticsAPIClient, SandboxURLs

async with StatisticsAPIClient(
    token="your-token",
    base_url=SandboxURLs.STATISTICS,
) as client:
    ...
```

## Error Handling

```python
from wb_api_sdk import (
    StatisticsAPIClient,
    WBAPIError,
    WBAuthError,
    WBRateLimitError,
)

async with StatisticsAPIClient(token="your-token") as client:
    try:
        report = await client.reports.get_report_detail_by_period(
            date_from="2024-01-01",
            date_to="2024-01-31",
        )
    except WBAuthError as e:
        # 401 - Invalid or expired token
        print(f"Auth failed: {e.message}")
        print(f"Status: {e.status_code}")
        print(f"Response: {e.response_data}")

    except WBRateLimitError as e:
        # 429 - Rate limit exceeded (after all retries)
        print(f"Rate limited: {e.message}")
        print(f"Retry after: {e.retry_after} seconds")

    except WBAPIError as e:
        # Other API errors (400, 403, 5xx after retries)
        print(f"API error: {e.message}")
        print(f"Status: {e.status_code}")
        print(f"Full response: {e.response_data}")
```

### Error Handling Summary

| Status Code | Exception | Retry |
|-------------|-----------|-------|
| 401 | `WBAuthError` | No |
| 429 | `WBRateLimitError` | Yes (with backoff) |
| 5xx | `WBAPIError` | Yes (with backoff) |
| 400, 403 | `WBAPIError` | No |

## Available Base URLs

```python
from wb_api_sdk import BaseURLs, SandboxURLs

# Production
BaseURLs.STATISTICS   # https://statistics-api.wildberries.ru
BaseURLs.CONTENT      # https://content-api.wildberries.ru
BaseURLs.ANALYTICS    # https://seller-analytics-api.wildberries.ru
BaseURLs.PRICES       # https://discounts-prices-api.wildberries.ru
BaseURLs.MARKETPLACE  # https://marketplace-api.wildberries.ru
BaseURLs.ADVERT       # https://advert-api.wildberries.ru
BaseURLs.FEEDBACKS    # https://feedbacks-api.wildberries.ru
BaseURLs.FINANCE      # https://finance-api.wildberries.ru
# ... and more

# Sandbox (not all services available)
SandboxURLs.STATISTICS
SandboxURLs.CONTENT
SandboxURLs.PRICES
SandboxURLs.ADVERT
SandboxURLs.FEEDBACKS
```

## API Reference

### StatisticsAPIClient

#### `reports.get_report_detail_by_period()`

Fetch sales report by realization period.

```python
await client.reports.get_report_detail_by_period(
    date_from: date | datetime | str,  # Report start date
    date_to: date | datetime | str,    # Report end date
    limit: int = 100000,               # Rows per page (max 100000)
    rrdid: int = 0,                    # Pagination cursor
    period: Literal["weekly", "daily"] = "weekly",
    fetch_all: bool = False,           # Auto-paginate all pages
    transform: Callable | None = None, # Transform each row
) -> list[dict]
```

#### `reports.stream_report_detail_by_period()`

Memory-efficient streaming version.

```python
for item in client.reports.stream_report_detail_by_period(
    date_from: date | datetime | str,
    date_to: date | datetime | str,
    limit: int = 100000,
    period: Literal["weekly", "daily"] = "weekly",
    fetch_all: bool = False,
    transform: Callable | None = None,
    timeout: int = 120,
) -> Iterator[dict]:
    ...
```

#### `ping()`

Check service availability (cached for 30s).

```python
result = await client.ping()
```

## Running Tests

```bash
# Unit tests
uv run pytest

# Integration tests (requires API token)
uv run pytest tests/test_integration.py -m integration -v -s
```

## License

MIT

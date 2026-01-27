"""Base URLs and endpoint constants for WB API.

WB API has multiple base URLs for different service categories.
"""

from enum import StrEnum


class BaseURLs(StrEnum):
    """Production base URLs for WB API services.

    Usage:
        client = SomeAPIClient(base_url=BaseURLs.FEEDBACKS, token="...")

    Each URL can be used directly as a string since StrEnum inherits from str.
    """

    CONTENT = "https://content-api.wildberries.ru"
    ANALYTICS = "https://seller-analytics-api.wildberries.ru"
    PRICES = "https://discounts-prices-api.wildberries.ru"
    MARKETPLACE = "https://marketplace-api.wildberries.ru"
    STATISTICS = "https://statistics-api.wildberries.ru"
    ADVERT = "https://advert-api.wildberries.ru"
    FEEDBACKS = "https://feedbacks-api.wildberries.ru"
    BUYER_CHAT = "https://buyer-chat-api.wildberries.ru"
    SUPPLIES = "https://supplies-api.wildberries.ru"
    RETURNS = "https://returns-api.wildberries.ru"
    DOCUMENTS = "https://documents-api.wildberries.ru"
    FINANCE = "https://finance-api.wildberries.ru"
    COMMON = "https://common-api.wildberries.ru"
    USER_MANAGEMENT = "https://user-management-api.wildberries.ru"


class SandboxURLs(StrEnum):
    """Sandbox base URLs for WB API services (for testing).

    Not all services have sandbox environments.
    """

    CONTENT = "https://content-api-sandbox.wildberries.ru"
    PRICES = "https://discounts-prices-api-sandbox.wildberries.ru"
    STATISTICS = "https://statistics-api-sandbox.wildberries.ru"
    ADVERT = "https://advert-api-sandbox.wildberries.ru"
    FEEDBACKS = "https://feedbacks-api-sandbox.wildberries.ru"


# Mapping: BaseURLs member name -> SandboxURLs (if exists)
_SANDBOX_MAP: dict[str, SandboxURLs] = {
    "CONTENT": SandboxURLs.CONTENT,
    "PRICES": SandboxURLs.PRICES,
    "STATISTICS": SandboxURLs.STATISTICS,
    "ADVERT": SandboxURLs.ADVERT,
    "FEEDBACKS": SandboxURLs.FEEDBACKS,
}


def get_sandbox_url(base_url: BaseURLs) -> SandboxURLs | None:
    """Get sandbox URL for a production URL if it exists.

    Args:
        base_url: Production base URL.

    Returns:
        Sandbox URL or None if sandbox not available for this service.

    Example:
        >>> get_sandbox_url(BaseURLs.FEEDBACKS)
        SandboxURLs.FEEDBACKS
        >>> get_sandbox_url(BaseURLs.FINANCE)
        None
    """
    return _SANDBOX_MAP.get(base_url.name)


class Endpoints:
    """Common endpoint paths."""

    PING = "/ping"


class StatisticsEndpoints:
    """Endpoint paths for Statistics API."""

    REPORT_DETAIL_BY_PERIOD = "/api/v5/supplier/reportDetailByPeriod"

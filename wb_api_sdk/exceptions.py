"""Exceptions for WB API SDK."""

from typing import Any


class WBAPIError(Exception):
    """Base exception for WB API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class WBAuthError(WBAPIError):
    """Authentication error.

    Raised when:
    - Token is invalid (401)
    - Token doesn't have access to this service (403)
    """

    pass


class WBRateLimitError(WBAPIError):
    """Rate limit exceeded error (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

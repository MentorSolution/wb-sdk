"""Tests for exception classes."""

from wb_api_sdk import WBAPIError, WBAuthError, WBRateLimitError


class TestWBAPIError:
    def test_str_with_status(self) -> None:
        err = WBAPIError("Not found", status_code=404)
        assert str(err) == "[404] Not found"

    def test_str_without_status(self) -> None:
        err = WBAPIError("Something went wrong")
        assert str(err) == "Something went wrong"

    def test_response_data_stored(self) -> None:
        data = {"title": "Error", "detail": "Invalid request"}
        err = WBAPIError("Error", status_code=400, response_data=data)
        assert err.response_data == data
        assert err.message == "Error"
        assert err.status_code == 400

    def test_response_data_defaults_to_empty_dict(self) -> None:
        err = WBAPIError("Error")
        assert err.response_data == {}


class TestWBAuthError:
    def test_is_wb_api_error(self) -> None:
        err = WBAuthError("Unauthorized", status_code=401)
        assert isinstance(err, WBAPIError)
        assert str(err) == "[401] Unauthorized"


class TestWBRateLimitError:
    def test_retry_after_stored(self) -> None:
        err = WBRateLimitError(
            "Rate limit exceeded",
            retry_after=30.0,
            status_code=429,
        )
        assert err.retry_after == 30.0
        assert err.status_code == 429

    def test_retry_after_none(self) -> None:
        err = WBRateLimitError("Rate limit exceeded")
        assert err.retry_after is None

    def test_is_wb_api_error(self) -> None:
        err = WBRateLimitError()
        assert isinstance(err, WBAPIError)

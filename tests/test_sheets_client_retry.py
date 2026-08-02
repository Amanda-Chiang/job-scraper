from unittest.mock import patch

import gspread
import pytest

from sheets_client import _retry_on_quota_error


def _make_429_error():
    response = type(
        "Resp",
        (),
        {"status_code": 429, "text": "429 quota exceeded", "json": lambda self: {}},
    )()
    return gspread.exceptions.APIError(response)


def test_retries_and_succeeds_after_transient_quota_errors():
    calls = {"count": 0}

    @_retry_on_quota_error
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise _make_429_error()
        return "ok"

    with patch("sheets_client.time.sleep") as mock_sleep:
        result = flaky()

    assert result == "ok"
    assert calls["count"] == 3
    assert mock_sleep.call_count == 2


def test_gives_up_after_max_retries():
    @_retry_on_quota_error
    def always_fails():
        raise _make_429_error()

    with patch("sheets_client.time.sleep"):
        with pytest.raises(gspread.exceptions.APIError):
            always_fails()


def test_non_quota_error_is_not_retried():
    calls = {"count": 0}

    @_retry_on_quota_error
    def raises_other_error():
        calls["count"] += 1
        response = type("Resp", (), {"status_code": 500, "text": "server error", "json": lambda self: {}})()
        raise gspread.exceptions.APIError(response)

    with patch("sheets_client.time.sleep") as mock_sleep:
        with pytest.raises(gspread.exceptions.APIError):
            raises_other_error()

    assert calls["count"] == 1
    mock_sleep.assert_not_called()

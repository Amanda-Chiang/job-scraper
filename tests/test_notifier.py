from unittest.mock import patch

import requests

from models import Posting
import notifier


def test_send_text_posts_message_to_topic_url(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    notifier.send_text("https://ntfy.sh/my-topic", "hello world")
    assert requests_mock.last_request.body == b"hello world"


def test_send_text_retries_and_succeeds_after_transient_connection_error():
    calls = {"count": 0}

    def flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.ConnectionError("Network is unreachable")
        response = requests.Response()
        response.status_code = 200
        return response

    with patch("notifier.requests.post", side_effect=flaky_post), patch("notifier.time.sleep") as mock_sleep:
        notifier.send_text("https://ntfy.sh/my-topic", "hello world")

    assert calls["count"] == 3
    assert mock_sleep.call_count == 2


def test_send_text_gives_up_after_max_retries():
    with patch("notifier.requests.post", side_effect=requests.exceptions.ConnectionError("still down")), \
         patch("notifier.time.sleep"):
        try:
            notifier.send_text("https://ntfy.sh/my-topic", "hello world")
            assert False, "expected ConnectionError to propagate"
        except requests.exceptions.ConnectionError:
            pass


def test_send_posting_formats_company_title_location_link(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    posting = Posting(
        company="Acme", title="Software Engineer Intern", location="NYC",
        link="https://acme.com/jobs/1", is_internship=True,
    )
    notifier.send_posting("https://ntfy.sh/my-topic", posting)
    body = requests_mock.last_request.body.decode("utf-8")
    assert "Acme: Software Engineer Intern (NYC)" in body
    assert "https://acme.com/jobs/1" in body

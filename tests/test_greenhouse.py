import json
from unittest.mock import patch

import requests

from sources import greenhouse


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/greenhouse_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/aquaticcapitalmanagement/jobs",
        json=fixture,
    )
    postings = greenhouse.fetch("Aquatic", "aquaticcapitalmanagement")
    assert len(postings) == 2
    assert postings[0].company == "Aquatic"
    assert postings[0].title == "Quantitative Researcher"
    assert postings[0].link == "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/7529282002"
    assert postings[0].location == "Chicago; New York; London"
    assert postings[0].is_internship is False
    assert postings[1].title == "Software Engineer, Intern (Summer 2027)"


def test_fetch_retries_once_after_a_timeout_and_succeeds(requests_mock):
    # Regression test: Greenhouse intermittently times out in production on
    # some boards even though the same request succeeds moments later - a
    # single retry should recover instead of the whole company failing.
    with open("tests/fixtures/greenhouse_sample.json") as f:
        fixture = json.load(f)
    call_count = {"n": 0}

    def responder(request, context):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise requests.exceptions.Timeout("Read timed out")
        context.status_code = 200
        return fixture

    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/aquaticcapitalmanagement/jobs",
        json=responder,
    )
    with patch("sources.greenhouse.time.sleep") as mock_sleep:
        postings = greenhouse.fetch("Aquatic", "aquaticcapitalmanagement")

    assert len(postings) == 2
    assert call_count["n"] == 2
    mock_sleep.assert_called_once()

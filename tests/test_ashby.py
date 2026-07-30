import json
from sources import ashby


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/ashby_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://api.ashbyhq.com/posting-api/job-board/netic",
        json=fixture,
    )
    postings = ashby.fetch("Netic", "netic")
    assert len(postings) == 2
    assert postings[1].company == "Netic"
    assert postings[1].title == "Software Engineer (Agent Platform) - Intern - 2026-2027"
    assert postings[1].link == "https://jobs.ashbyhq.com/netic/b0ea7aab-8eea-4d31-96f9-278364180ae7"
    assert postings[1].location == "San Francisco"
    assert postings[1].is_internship is False

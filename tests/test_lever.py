import json
from sources import lever


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/lever_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://api.lever.co/v0/postings/palantir?mode=json",
        json=fixture,
    )
    postings = lever.fetch("Palantir", "palantir")
    assert len(postings) == 2
    assert postings[1].company == "Palantir"
    assert postings[1].title == "Software Engineer, Internship - Production Infrastructure"
    assert postings[1].link == "https://jobs.lever.co/palantir/373367a9-3160-49d8-b7af-2efec062fad1"
    assert postings[1].location == "Seattle"
    assert postings[1].is_internship is False

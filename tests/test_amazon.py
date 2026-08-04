import json
from sources.custom import amazon


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/amazon_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.amazon.jobs/en/search.json", json=fixture)
    postings = amazon.fetch()
    assert len(postings) == 2
    assert all(p.company == "Amazon" for p in postings)
    assert all(p.is_internship is False for p in postings)


def test_fetch_builds_link_and_location(requests_mock):
    with open("tests/fixtures/amazon_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.amazon.jobs/en/search.json", json=fixture)
    postings = amazon.fetch()
    robotics = next(p for p in postings if "Robotics" in p.title)
    assert robotics.link == (
        "https://www.amazon.jobs/en/jobs/3136266/robotics-software-development-engineer-intern-co-op-2026"
    )
    assert robotics.location == "Westborough, Massachusetts, USA"

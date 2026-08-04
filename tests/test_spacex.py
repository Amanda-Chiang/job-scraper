import json
from sources.custom import spacex


def test_fetch_filters_to_true_intern_employment_type(requests_mock):
    with open("tests/fixtures/spacex_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/spacex/jobs?content=true", json=fixture
    )
    postings = spacex.fetch()
    assert len(postings) == 1
    assert postings[0].title == "Spring 2027 Software Engineering Internship/Co-op"
    assert postings[0].is_internship is True
    assert postings[0].company == "SpaceX"


def test_fetch_excludes_internal_systems_role_despite_intern_substring(requests_mock):
    with open("tests/fixtures/spacex_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/spacex/jobs?content=true", json=fixture
    )
    postings = spacex.fetch()
    assert not any("Internal Systems" in p.title for p in postings)


def test_fetch_builds_link_and_location(requests_mock):
    with open("tests/fixtures/spacex_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/spacex/jobs?content=true", json=fixture
    )
    postings = spacex.fetch()
    assert postings[0].link == "https://boards.greenhouse.io/spacex/jobs/8621756002?gh_jid=8621756002"
    assert postings[0].location == "Flexible - Any SpaceX Site"

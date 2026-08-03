import json
from sources.custom import jane_street


def test_fetch_filters_to_internships_only(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    assert len(postings) == 2
    assert all(p.is_internship for p in postings)
    assert all(p.company == "Jane Street" for p in postings)


def test_fetch_excludes_winter_internships(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    assert not any(p.title == "IT Operations Engineer" for p in postings)


def test_fetch_builds_link_from_id(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    data_engineer = next(p for p in postings if p.title == "Data Engineer")
    assert data_engineer.link == "https://www.janestreet.com/join-jane-street/position/8631973002/"
    assert data_engineer.location == "NYC"


def test_fetch_passes_through_obfuscated_title_without_decoding(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    obfuscated = next(p for p in postings if p.link.endswith("8596771002/"))
    assert obfuscated.is_internship is True
    assert "achine" in obfuscated.title  # not decoded to "Machine" — documented limitation

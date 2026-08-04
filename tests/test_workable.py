import json
from sources import workable


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/workable_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://apply.workable.com/api/v1/widget/accounts/huggingface", json=fixture
    )
    postings = workable.fetch("Hugging Face", "huggingface")
    assert len(postings) == 2
    assert all(p.company == "Hugging Face" for p in postings)
    assert all(p.is_internship is False for p in postings)


def test_fetch_builds_location_from_city_state_country(requests_mock):
    with open("tests/fixtures/workable_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://apply.workable.com/api/v1/widget/accounts/huggingface", json=fixture
    )
    postings = workable.fetch("Hugging Face", "huggingface")
    intern_posting = next(p for p in postings if "Intern" in p.title)
    assert intern_posting.location == "New York, NY, United States"
    assert intern_posting.link == "https://apply.workable.com/j/AB12CD34"

    full_time = next(p for p in postings if "Senior Python" in p.title)
    assert full_time.location == "Paris, France"

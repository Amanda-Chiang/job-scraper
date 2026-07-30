import json
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

from sources.custom import netflix

URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs"


def test_fetch_filters_to_intern_titles_and_builds_posting(requests_mock):
    requests_mock.get(
        URL,
        json={
            "count": 2,
            "positions": [
                {
                    "name": "Video Algorithms Intern, Fall 2026",
                    "location": "Los Gatos,California,United States of America",
                    "canonicalPositionUrl": "https://explore.jobs.netflix.net/careers/job/790315673635",
                },
                {
                    "name": "Senior Software Engineer",
                    "location": "Los Gatos,California,United States of America",
                    "canonicalPositionUrl": "https://explore.jobs.netflix.net/careers/job/790000000000",
                },
            ],
        },
    )
    postings = netflix.fetch()
    assert len(postings) == 1
    assert postings[0].company == "Netflix"
    assert postings[0].title == "Video Algorithms Intern, Fall 2026"
    assert postings[0].location == "Los Gatos,California,United States of America"
    assert postings[0].link == "https://explore.jobs.netflix.net/careers/job/790315673635"
    assert postings[0].is_internship is False


def test_fetch_paginates_until_count_is_reached(requests_mock):
    page_one = {
        "count": 150,
        "positions": [
            {
                "name": f"Intern Role {i}",
                "location": "US",
                "canonicalPositionUrl": f"https://explore.jobs.netflix.net/careers/job/{i}",
            }
            for i in range(100)
        ],
    }
    page_two = {
        "count": 150,
        "positions": [
            {
                "name": f"Intern Role {i}",
                "location": "US",
                "canonicalPositionUrl": f"https://explore.jobs.netflix.net/careers/job/{i}",
            }
            for i in range(100, 150)
        ],
    }
    requests_mock.get(URL, [{"json": page_one}, {"json": page_two}])
    postings = netflix.fetch()
    assert len(postings) == 150

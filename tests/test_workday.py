from sources import workday

URL = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"


def test_fetch_filters_to_intern_titles_and_builds_link(requests_mock):
    requests_mock.post(
        URL,
        json={
            "total": 2,
            "jobPostings": [
                {
                    "title": "Software Engineering Intern, Fall 2026",
                    "externalPath": "/job/US-CA-Santa-Clara/Software-Engineering-Intern_JR123",
                    "locationsText": "US, CA, Santa Clara",
                },
                {
                    "title": "Senior Software Engineer",
                    "externalPath": "/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR456",
                    "locationsText": "US, CA, Santa Clara",
                },
            ],
        },
    )
    postings = workday.fetch("NVIDIA", "nvidia.wd5|nvidia|NVIDIAExternalCareerSite")
    assert len(postings) == 1
    assert postings[0].company == "NVIDIA"
    assert postings[0].title == "Software Engineering Intern, Fall 2026"
    assert postings[0].location == "US, CA, Santa Clara"
    assert postings[0].link == (
        "https://nvidia.wd5.myworkdayjobs.com/job/US-CA-Santa-Clara/Software-Engineering-Intern_JR123"
    )
    assert postings[0].is_internship is False


def test_fetch_paginates_until_total_is_reached(requests_mock):
    # Workday's searchText match isn't a strict filter, so a fuzzy query for
    # "intern" can span many pages of mixed results - fetch must page through
    # all of them rather than stopping after the first response. Workday also
    # rejects any request with limit > 20, so a total larger than one page
    # size forces this through the real pagination loop.
    total = 45

    def page(start):
        return {
            "total": total,
            "jobPostings": [
                {
                    "title": f"Intern Role {i}",
                    "externalPath": f"/job/US/Intern-Role-{i}_JR{i}",
                    "locationsText": "US",
                }
                for i in range(start, min(start + workday.PAGE_SIZE, total))
            ],
        }

    responses = [
        {"json": page(start)} for start in range(0, total, workday.PAGE_SIZE)
    ]
    requests_mock.post(URL, responses)
    postings = workday.fetch("NVIDIA", "nvidia.wd5|nvidia|NVIDIAExternalCareerSite")
    assert len(postings) == total

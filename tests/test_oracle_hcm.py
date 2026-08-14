from sources.custom import oracle_hcm

URL = (
    "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
)


def test_fetch_filters_to_intern_titles_and_builds_link(requests_mock):
    requests_mock.get(
        URL,
        json={
            "items": [
                {
                    "TotalJobsCount": 2,
                    "requisitionList": [
                        {"Id": "334391", "Title": "DRC Customer Success Intern", "PrimaryLocation": "Colorado Springs, CO, United States"},
                        {"Id": "334999", "Title": "Senior Software Engineer", "PrimaryLocation": "Austin, TX, United States"},
                    ],
                }
            ]
        },
    )
    postings = oracle_hcm.fetch()
    assert len(postings) == 1
    assert postings[0].company == "Oracle"
    assert postings[0].title == "DRC Customer Success Intern"
    assert postings[0].location == "Colorado Springs, CO, United States"
    assert postings[0].link == (
        "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/334391"
    )
    assert postings[0].is_internship is False


def test_fetch_paginates_until_total_jobs_count_is_reached(requests_mock):
    # The "keyword" query param does fuzzy relevance matching (most results on
    # any page aren't intern roles), so fetch must page through the full
    # TotalJobsCount and filter client-side rather than trusting one page.
    page_one = {
        "items": [
            {
                "TotalJobsCount": 250,
                "requisitionList": [
                    {"Id": str(i), "Title": f"Intern Role {i}", "PrimaryLocation": "US"} for i in range(200)
                ],
            }
        ]
    }
    page_two = {
        "items": [
            {
                "TotalJobsCount": 250,
                "requisitionList": [
                    {"Id": str(i), "Title": f"Intern Role {i}", "PrimaryLocation": "US"} for i in range(200, 250)
                ],
            }
        ]
    }
    requests_mock.get(URL, [{"json": page_one}, {"json": page_two}])
    postings = oracle_hcm.fetch()
    assert len(postings) == 250

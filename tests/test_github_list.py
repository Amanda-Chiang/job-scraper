from sources import github_list


def test_fetch_parses_table_rows(requests_mock):
    with open("tests/fixtures/github_list_sample.md") as f:
        readme = f.read()
    requests_mock.get(
        "https://raw.githubusercontent.com/sndsh404/summer-2027-internships/main/README.md",
        text=readme,
    )
    postings = github_list.fetch("sndsh404/summer-2027-internships")
    assert len(postings) == 3
    assert postings[0].company == "Susquehanna"
    assert postings[0].title == "Quantitative Systematic Trading Intern (PhD, Summer 2027)"
    assert postings[0].location == "New York, NY"
    assert postings[0].link == "https://careers.sig.com/jobs/10822"
    assert postings[0].is_internship is True


def test_fetch_falls_back_to_master_branch(requests_mock):
    with open("tests/fixtures/github_list_sample.md") as f:
        readme = f.read()
    requests_mock.get(
        "https://raw.githubusercontent.com/someuser/somerepo/main/README.md",
        status_code=404,
    )
    requests_mock.get(
        "https://raw.githubusercontent.com/someuser/somerepo/master/README.md",
        text=readme,
    )
    postings = github_list.fetch("someuser/somerepo")
    assert len(postings) == 3

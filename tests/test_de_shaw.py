from sources.custom import de_shaw


def test_fetch_filters_to_interns_only(requests_mock):
    with open("tests/fixtures/de_shaw_sample.html") as f:
        html = f.read()
    requests_mock.get("https://www.deshaw.com/careers/internships", text=html)
    postings = de_shaw.fetch()
    assert len(postings) == 2
    assert all(p.is_internship for p in postings)
    assert all(p.company == "D. E. Shaw" for p in postings)


def test_fetch_builds_link_from_job_url(requests_mock):
    with open("tests/fixtures/de_shaw_sample.html") as f:
        html = f.read()
    requests_mock.get("https://www.deshaw.com/careers/internships", text=html)
    postings = de_shaw.fetch()
    software = next(p for p in postings if "Software Developer" in p.title)
    assert software.link == (
        "https://www.deshaw.com/careers/internships/"
        "Software-Developer-Intern-New-York-Summer-2027-5894"
    )
    assert software.location == "New York"

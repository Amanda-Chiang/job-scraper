import pytest

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


def test_fetch_tolerates_flat_structure_without_data_key(requests_mock):
    # Regression: the site used to put fields directly on each entry rather
    # than nested under "data". job.get("data", job) must still work if the
    # site ever reverts to (or another entry uses) the flat shape.
    flat_html = """<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"internships":[
  {"id":9999,"displayName":"Flat Shape Intern (New York) – Summer 2027","jobUrl":"Flat-Shape-Intern-9999","jobMetadata":{"workStatus":"Intern","jobLocations":[{"name":"New York"}]}}
]}}}
</script>
</body></html>"""
    requests_mock.get("https://www.deshaw.com/careers/internships", text=flat_html)
    postings = de_shaw.fetch()
    assert len(postings) == 1
    assert postings[0].title == "Flat Shape Intern (New York) – Summer 2027"


def test_fetch_raises_when_no_postings_have_intern_status_despite_nonempty_response(requests_mock):
    # Regression test for the real production bug: D.E. Shaw restructured
    # their page so jobMetadata moved under a "data" key. The old parser
    # read the wrong location, got workStatus=None for every entry, and
    # silently returned an empty list instead of erroring - main.py recorded
    # this as a clean success with zero postings, invisible on the Config
    # tab. A non-empty response yielding zero interns must raise instead.
    broken_shape_html = """<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"internships":[
  {"id":1,"displayName":"Some Intern Role","jobUrl":"some-role","somethingElse":{"workStatus":"Intern"}}
]}}}
</script>
</body></html>"""
    requests_mock.get("https://www.deshaw.com/careers/internships", text=broken_shape_html)
    with pytest.raises(ValueError, match="workStatus"):
        de_shaw.fetch()

from models import Posting
from dedup import filter_new_postings


def _posting(link):
    return Posting(company="Acme", title="Software Engineer Intern", location="NYC", link=link, is_internship=True)


def test_drops_postings_with_seen_links():
    postings = [_posting("https://x/1"), _posting("https://x/2")]
    result = filter_new_postings(postings, existing_links={"https://x/1"})
    assert result == [postings[1]]


def test_keeps_all_when_no_links_seen():
    postings = [_posting("https://x/1"), _posting("https://x/2")]
    assert filter_new_postings(postings, existing_links=set()) == postings


def test_dedup_is_per_posting_not_per_company():
    same_company = [_posting("https://x/1"), _posting("https://x/2")]
    result = filter_new_postings(same_company, existing_links={"https://x/1"})
    assert len(result) == 1
    assert result[0].link == "https://x/2"

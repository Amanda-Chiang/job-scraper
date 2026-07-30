from models import Posting, KeywordConfig
from matcher import filter_relevant

KEYWORDS = KeywordConfig(
    include=["software engineer", "hardware engineer", "quant", "ai engineer"],
    exclude=["senior", "staff", "principal"],
)


def _posting(title, is_internship=False):
    return Posting(company="Acme", title=title, location="NYC", link="https://x/1", is_internship=is_internship)


def test_matches_include_keyword_and_internship_title():
    postings = [_posting("Software Engineer Intern")]
    result = filter_relevant(postings, KEYWORDS)
    assert result == postings


def test_rejects_missing_include_keyword():
    postings = [_posting("Marketing Intern")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_rejects_exclude_keyword_even_with_include_match():
    postings = [_posting("Senior Software Engineer Intern")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_rejects_full_time_role_without_internship_signal():
    postings = [_posting("Software Engineer")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_trusts_is_internship_flag_even_without_title_keyword():
    postings = [_posting("Data Engineer", is_internship=True)]
    keywords = KeywordConfig(include=["data engineer"], exclude=[])
    assert filter_relevant(postings, keywords) == postings


def test_case_insensitive_matching():
    postings = [_posting("QUANT TRADING INTERN")]
    assert filter_relevant(postings, KEYWORDS) == postings

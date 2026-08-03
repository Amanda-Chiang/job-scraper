from models import Posting, KeywordConfig
from matcher import (
    filter_relevant,
    is_acceptable_analyst_role,
    is_acceptable_degree_level,
    is_acceptable_department,
    is_in_season,
    is_us_location,
)

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


def test_is_us_location_accepts_plain_us_cities():
    assert is_us_location("NYC") is True
    assert is_us_location("Mountain View, CA (multiple US)") is True
    assert is_us_location("Seattle, LA, Denver") is True


def test_is_us_location_rejects_known_non_us_cities():
    assert is_us_location("London, United Kingdom") is False
    assert is_us_location("Hong Kong") is False
    assert is_us_location("Toronto") is False
    assert is_us_location("Chicago; New York; London") is False


def test_is_us_location_case_insensitive():
    assert is_us_location("LONDON") is False
    assert is_us_location("nyc") is True


def test_is_acceptable_degree_level_rejects_phd_only_role():
    assert is_acceptable_degree_level("Quantitative Trading Intern (PhD, Summer 2027)") is False


def test_is_acceptable_degree_level_rejects_masters_only_role():
    assert is_acceptable_degree_level("Quantitative Trading Intern (Master's, Summer 2027)") is False


def test_is_acceptable_degree_level_rejects_ph_d_with_periods_variant():
    assert is_acceptable_degree_level("Quantitative Analyst, Ph.D. Intern") is False


def test_is_acceptable_degree_level_accepts_when_bachelors_also_listed():
    assert is_acceptable_degree_level("Software Engineering Intern, BS/MS, Summer 2027") is True


def test_is_acceptable_degree_level_accepts_plain_bachelors_role():
    assert is_acceptable_degree_level("Software Engineering Intern, BS, Summer 2027") is True


def test_is_acceptable_degree_level_accepts_role_with_no_degree_qualifier():
    assert is_acceptable_degree_level("Quantitative Analyst Intern") is True


def test_is_in_season_rejects_winter_without_summer():
    assert is_in_season("Winter Co-Op") is False
    assert is_in_season("Software Engineering Intern, Fall 2026") is False
    assert is_in_season("Spring 2027 Marketing Intern") is False


def test_is_in_season_accepts_summer():
    assert is_in_season("Software Engineering Intern, Summer 2027") is True


def test_is_in_season_accepts_when_no_season_mentioned():
    assert is_in_season("Quantitative Analyst Intern") is True


def test_is_in_season_accepts_summer_even_if_off_season_word_also_present():
    assert is_in_season("Summer Internship (December-February)") is True


def test_is_acceptable_analyst_role_rejects_generic_analyst_titles():
    assert is_acceptable_analyst_role("Global Technology Summer Analyst") is False
    assert is_acceptable_analyst_role("Business Analyst Intern") is False
    assert is_acceptable_analyst_role("Macro Analyst Intern") is False


def test_is_acceptable_analyst_role_keeps_quantitative_analyst():
    assert is_acceptable_analyst_role("Quantitative Analyst Intern") is True
    assert is_acceptable_analyst_role("Quant Research Analyst") is True


def test_is_acceptable_analyst_role_accepts_non_analyst_titles():
    assert is_acceptable_analyst_role("Software Engineer Intern") is True


def test_is_acceptable_department_rejects_it_roles():
    assert is_acceptable_department("IT Intern") is False
    assert is_acceptable_department("IT Operations Engineer") is False
    assert is_acceptable_department("Information Technology Intern") is False
    assert is_acceptable_department("Help Desk Support Intern") is False


def test_is_acceptable_department_does_not_handle_audit():
    # "audit" is filtered separately via the Keywords sheet's exclude list, not this function
    assert is_acceptable_department("Internal Audit Intern") is True


def test_is_acceptable_department_does_not_false_positive_on_substring_it():
    assert is_acceptable_department("Site Reliability Engineer Intern") is True
    assert is_acceptable_department("Written Communications Intern") is True
    assert is_acceptable_department("Digital Systems Engineer Intern") is True


def test_is_acceptable_department_accepts_normal_titles():
    assert is_acceptable_department("Software Engineer Intern") is True

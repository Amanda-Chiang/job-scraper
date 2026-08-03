import re

from models import Posting, KeywordConfig

LEVEL_KEYWORDS = ("intern", "internship", "co-op", "coop")

ADVANCED_DEGREE_PATTERN = re.compile(r"\bphd\b|ph\.?d\.?|\bmasters?\b|master's|\bmsc\b|\bms\b", re.IGNORECASE)
BACHELORS_PATTERN = re.compile(r"\bbs\b|\bb\.s\.?|bachelor|undergrad", re.IGNORECASE)

OFF_SEASON_MARKERS = ("spring", "winter", "fall", "autumn")

ANALYST_PATTERN = re.compile(r"\banalyst\b", re.IGNORECASE)
QUANT_PATTERN = re.compile(r"\bquant\b|quantitative", re.IGNORECASE)

NON_US_LOCATION_MARKERS = (
    "london", "united kingdom", " uk", "uk,", "ldn",
    "hong kong", "hkg",
    "singapore", "sgp",
    "toronto", "canada",
    "zurich", "switzerland",
    "paris", "france",
    "tokyo", "japan",
    "bangalore", "india",
    "dublin", "ireland",
    "sydney", "australia",
    "berlin", "germany",
    "amsterdam", "netherlands",
)


def is_us_location(location: str) -> bool:
    loc = location.lower()
    return not any(marker in loc for marker in NON_US_LOCATION_MARKERS)


def is_acceptable_degree_level(title: str) -> bool:
    requires_advanced_degree_only = bool(ADVANCED_DEGREE_PATTERN.search(title)) and not BACHELORS_PATTERN.search(title)
    return not requires_advanced_degree_only


def is_in_season(title: str) -> bool:
    lower = title.lower()
    has_off_season = any(marker in lower for marker in OFF_SEASON_MARKERS)
    has_summer = "summer" in lower
    return not (has_off_season and not has_summer)


def is_acceptable_analyst_role(title: str) -> bool:
    is_analyst_role = bool(ANALYST_PATTERN.search(title))
    is_quant_role = bool(QUANT_PATTERN.search(title))
    return not is_analyst_role or is_quant_role


def is_relevant(posting: Posting, keywords: KeywordConfig) -> bool:
    title = posting.title.lower()
    if not any(kw.lower() in title for kw in keywords.include):
        return False
    if any(kw.lower() in title for kw in keywords.exclude):
        return False
    if posting.is_internship:
        return True
    return any(kw in title for kw in LEVEL_KEYWORDS)


def filter_relevant(postings: list[Posting], keywords: KeywordConfig) -> list[Posting]:
    return [p for p in postings if is_relevant(p, keywords)]

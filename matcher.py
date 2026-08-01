from models import Posting, KeywordConfig

LEVEL_KEYWORDS = ("intern", "internship", "co-op", "coop")

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

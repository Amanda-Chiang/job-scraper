from models import Posting, KeywordConfig

LEVEL_KEYWORDS = ("intern", "internship", "co-op", "coop")


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

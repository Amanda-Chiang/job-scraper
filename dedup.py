from models import Posting


def filter_new_postings(postings: list[Posting], existing_links: set[str]) -> list[Posting]:
    return [p for p in postings if p.link not in existing_links]

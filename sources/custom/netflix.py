import requests

from models import Posting

URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs"
PAGE_SIZE = 100


def fetch() -> list[Posting]:
    postings = []
    start = 0
    while True:
        response = requests.get(
            URL,
            params={"domain": "netflix.com", "start": start, "num": PAGE_SIZE, "query": "intern"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        positions = data.get("positions", [])
        if not positions:
            break
        for position in positions:
            title = position.get("name", "")
            if "intern" not in title.lower():
                continue
            postings.append(
                Posting(
                    company="Netflix",
                    title=title,
                    location=position.get("location", ""),
                    link=position["canonicalPositionUrl"],
                    is_internship=False,
                )
            )
        start += PAGE_SIZE
        if start >= data.get("count", 0):
            break
    return postings

import requests

from models import Posting

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{account}"


def fetch(company: str, account: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(account=account), timeout=15)
    response.raise_for_status()
    data = response.json()
    postings = []
    for job in data.get("jobs", []):
        location_parts = [p for p in (job.get("city"), job.get("state"), job.get("country")) if p]
        postings.append(
            Posting(
                company=company,
                title=job["title"],
                location=", ".join(location_parts),
                link=job["url"],
                is_internship=False,
            )
        )
    return postings

import requests

from models import Posting

BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch(company: str, slug: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(slug=slug), timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company=company,
            title=job["text"],
            location=job.get("categories", {}).get("location", ""),
            link=job["hostedUrl"],
            is_internship=False,
        )
        for job in data
    ]

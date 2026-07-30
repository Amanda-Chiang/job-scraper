import requests

from models import Posting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch(company: str, board_token: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(token=board_token), timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company=company,
            title=job["title"],
            location=job.get("location", {}).get("name", ""),
            link=job["absolute_url"],
            is_internship=False,
        )
        for job in data.get("jobs", [])
    ]

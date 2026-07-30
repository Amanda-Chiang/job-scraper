import requests

from models import Posting

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


def fetch(company: str, board_name: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(board_name=board_name), timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company=company,
            title=job["title"],
            location=job.get("location", ""),
            link=job["jobUrl"],
            is_internship=False,
        )
        for job in data.get("jobs", [])
        if job.get("isListed", True)
    ]

import time

import requests

from models import Posting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 3


def fetch(company: str, board_token: str) -> list[Posting]:
    url = BASE_URL.format(token=board_token)
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        # Greenhouse intermittently times out on some boards in production
        # even though a fresh manual request succeeds instantly - a single
        # retry clears most of these transient hiccups.
        time.sleep(RETRY_DELAY_SECONDS)
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
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

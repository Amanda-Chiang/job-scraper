import requests

from models import Posting

URL = "https://www.janestreet.com/jobs/main.json"
INTERNSHIP_AVAILABILITY_MARKERS = ("internship", "co-op")


def fetch() -> list[Posting]:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    postings = []
    for job in data:
        availability = (job.get("availability") or "").lower()
        if not any(marker in availability for marker in INTERNSHIP_AVAILABILITY_MARKERS):
            continue
        if "summer" not in availability:
            continue
        postings.append(
            Posting(
                company="Jane Street",
                title=job["position"],
                location=job.get("city", ""),
                link=f"https://www.janestreet.com/join-jane-street/position/{job['id']}/",
                is_internship=True,
            )
        )
    return postings

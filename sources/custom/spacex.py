import requests

from models import Posting

URL = "https://boards-api.greenhouse.io/v1/boards/spacex/jobs?content=true"


def _is_intern_role(job: dict) -> bool:
    for field in job.get("metadata") or []:
        if field.get("name") == "Employment Type" and field.get("value") == "Intern":
            return True
    return False


def fetch() -> list[Posting]:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company="SpaceX",
            title=job["title"],
            location=job.get("location", {}).get("name", ""),
            link=job["absolute_url"],
            is_internship=True,
        )
        for job in data.get("jobs", [])
        if _is_intern_role(job)
    ]

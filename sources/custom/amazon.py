import requests

from models import Posting

URL = "https://www.amazon.jobs/en/search.json"


def fetch() -> list[Posting]:
    response = requests.get(
        URL,
        params={"base_query": "intern", "country": "USA", "result_limit": 100},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company="Amazon",
            title=job["title"],
            location=job.get("normalized_location", ""),
            link=f"https://www.amazon.jobs{job['job_path']}",
            is_internship=False,
        )
        for job in data.get("jobs", [])
    ]

import requests

from models import Posting

URL = "https://boards-api.greenhouse.io/v1/boards/coreweave/jobs?content=true"


def _is_wandb_role(job: dict) -> bool:
    for field in job.get("metadata") or []:
        if field.get("name") == "Acquisition Company" and field.get("value") == "Weights & Biases":
            return True
    return False


def fetch() -> list[Posting]:
    # Weights & Biases was acquired by CoreWeave and shares CoreWeave's
    # Greenhouse board (already scraped separately as its own company) -
    # W&B-specific roles are distinguished only by an "Acquisition Company"
    # metadata field, so this can't reuse the generic greenhouse connector.
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company="Weights & Biases",
            title=job["title"],
            location=job.get("location", {}).get("name", ""),
            link=job["absolute_url"],
            is_internship=False,
        )
        for job in data.get("jobs", [])
        if _is_wandb_role(job)
    ]

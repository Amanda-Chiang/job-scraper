import json
import re

import requests

from models import Posting

URL = "https://www.deshaw.com/careers/internships"
NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def fetch() -> list[Posting]:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    match = NEXT_DATA_PATTERN.search(response.text)
    data = json.loads(match.group(1))
    internships = data["props"]["pageProps"]["internships"]
    postings = []
    for job in internships:
        metadata = job.get("jobMetadata", {})
        if metadata.get("workStatus") != "Intern":
            continue
        locations = metadata.get("jobLocations") or []
        location = locations[0]["name"] if locations else ""
        postings.append(
            Posting(
                company="D. E. Shaw",
                title=job["displayName"],
                location=location,
                link=f"https://www.deshaw.com/careers/internships/{job['jobUrl']}",
                is_internship=True,
            )
        )
    return postings

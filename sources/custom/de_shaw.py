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
        # As of 2026-08, the site nests each entry's real fields under "data"
        # (job["data"]["jobMetadata"] etc.) rather than at the top level -
        # job.get("data", job) also tolerates a reversion to the flat shape.
        record = job.get("data", job)
        metadata = record.get("jobMetadata", {})
        if metadata.get("workStatus") != "Intern":
            continue
        locations = metadata.get("jobLocations") or []
        location = locations[0]["name"] if locations else ""
        postings.append(
            Posting(
                company="D. E. Shaw",
                title=record["displayName"],
                location=location,
                link=f"https://www.deshaw.com/careers/internships/{record['jobUrl']}",
                is_internship=True,
            )
        )

    if internships and not postings:
        # Zero matches out of a non-empty response almost always means the
        # site's data shape changed and this parser needs updating, not that
        # zero internships are genuinely open - raise so it shows up as a
        # real error in Config instead of silently reporting success with 0
        # postings (exactly how this broke before it was caught).
        raise ValueError(
            f"D.E. Shaw returned {len(internships)} internship entries but none had "
            "workStatus == 'Intern' - the site's data structure likely changed"
        )
    return postings

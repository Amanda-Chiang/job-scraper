import requests

from models import Posting

BASE_URL = "https://{subdomain}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
PAGE_SIZE = 20  # Workday's API rejects requests with limit > 20 with a 400


def fetch(company: str, identifier: str) -> list[Posting]:
    # identifier packs three Workday-specific pieces into one Config cell,
    # e.g. "nvidia.wd5|nvidia|NVIDIAExternalCareerSite" - the wd instance number
    # and site slug vary per tenant and aren't derivable from the company name.
    subdomain, tenant, site = identifier.split("|")
    url = BASE_URL.format(subdomain=subdomain, tenant=tenant, site=site)

    postings = []
    offset = 0
    while True:
        response = requests.post(
            url,
            json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": "intern"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobPostings", [])
        if not jobs:
            break
        for job in jobs:
            title = job.get("title", "")
            # Workday's searchText does fuzzy relevance matching, not a strict
            # filter, so results still need a client-side title check.
            if "intern" not in title.lower():
                continue
            postings.append(
                Posting(
                    company=company,
                    title=title,
                    location=job.get("locationsText", ""),
                    link=f"https://{subdomain}.myworkdayjobs.com{job['externalPath']}",
                    is_internship=False,
                )
            )
        offset += PAGE_SIZE
        if offset >= data.get("total", 0):
            break
    return postings

import requests

from models import Posting

URL = (
    "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    "?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_1001,limit={limit},offset={offset},keyword=intern"
)
PAGE_SIZE = 200  # server-enforced max page size


def fetch() -> list[Posting]:
    postings = []
    offset = 0
    while True:
        response = requests.get(URL.format(limit=PAGE_SIZE, offset=offset), timeout=15)
        response.raise_for_status()
        data = response.json()
        item = data["items"][0]
        requisitions = item.get("requisitionList") or []
        if not requisitions:
            break
        for req in requisitions:
            title = req.get("Title", "")
            # The "keyword" query param does fuzzy relevance matching, not a
            # strict filter (most results on any given page aren't intern
            # roles), so a client-side title check is still required.
            if "intern" not in title.lower():
                continue
            postings.append(
                Posting(
                    company="Oracle",
                    title=title,
                    location=req.get("PrimaryLocation", ""),
                    link=f"https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{req['Id']}",
                    is_internship=False,
                )
            )
        offset += PAGE_SIZE
        if offset >= item.get("TotalJobsCount", 0):
            break
    return postings

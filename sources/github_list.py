import re

import requests

from models import Posting

RAW_URL_TEMPLATE = "https://raw.githubusercontent.com/{repo}/{branch}/README.md"
LINK_PATTERN = re.compile(r"\[.*?\]\((.*?)\)")


def _fetch_readme(repo: str) -> str:
    last_response = None
    for branch in ("main", "master"):
        last_response = requests.get(RAW_URL_TEMPLATE.format(repo=repo, branch=branch), timeout=15)
        if last_response.status_code == 200:
            return last_response.text
    last_response.raise_for_status()
    return last_response.text


def _parse_table(readme: str) -> list[Posting]:
    postings = []
    in_table = False
    for line in readme.splitlines():
        stripped = line.strip()
        if stripped.startswith("| Company") and "Apply" in stripped:
            in_table = True
            continue
        if not in_table:
            continue
        if stripped.startswith("| ---"):
            continue
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        company, role, location, apply_cell = cells[0], cells[1], cells[2], cells[3]
        link_match = LINK_PATTERN.search(apply_cell)
        if not link_match:
            continue
        postings.append(
            Posting(
                company=company,
                title=role,
                location=location,
                link=link_match.group(1),
                is_internship=True,
            )
        )
    return postings


def fetch(repo: str) -> list[Posting]:
    readme = _fetch_readme(repo)
    return _parse_table(readme)

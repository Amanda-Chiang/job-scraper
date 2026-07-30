# Phase 1: Job Scraper, Matcher, Notifier & Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that runs every 30 minutes, scrapes a configurable set of company job boards and GitHub community internship lists, filters for internship-level tech/quant/hardware/AI roles, pushes an ntfy.sh notification and logs a row to the user's existing Google Sheets tracker for every new match — with per-source failure visibility written directly into the sheet.

**Architecture:** A single-process, stateless Python script (`main.py`) invoked on a schedule by Railway. All persistent state (company list, keywords, aggregator sources, dedup history, scraper health) lives in a Google Sheet with four tabs (`Tracker`, `Config`, `Aggregators`, `Keywords`) — no database. Connectors for Greenhouse/Lever/Ashby/custom-scraped companies/GitHub-list aggregators all return a shared `Posting` shape; a pure-function matcher filters company-source postings by keyword/level, aggregator-source postings skip the matcher entirely and are trusted as-is.

**Tech Stack:** Python 3.11+, `requests` (HTTP), `gspread` + `google-auth` (Google Sheets), `pytest` + `requests-mock` (testing), Railway (hosting + scheduling), ntfy.sh (push notifications).

## Global Constraints

- Internships only — no full-time/new-grad postings (Phase 1 non-goal).
- No LinkedIn/Indeed scraping, no Citadel scraping — both deferred to Phase 3 (Citadel is behind an active Cloudflare bot challenge; verified via direct `curl`, every path returns `403` with header `cf-mitigated: challenge`).
- No AI-based relevance scoring — matching is pure keyword/title filtering (Phase 1 non-goal).
- The Google Sheet is the only persistent store — no database, no local state file between runs.
- Dedup keys off the posting's `Link` URL, never the company name.
- Every fetch attempt (success or failure) must update that source's row in the `Config`/`Aggregators` tab (`Consecutive Failures`, `Last Error`, `Last Success At`) so failures are visible directly in the sheet, not only via the 5-failure ntfy alert.
- Auto-added tracker rows populate `Company | Link | Position | Location | Date Found` and leave `Date Applied | Status | Referral? | Notes` blank for the user.

Full rationale for all of the above lives in `docs/superpowers/specs/2026-07-30-phase1-scraper-notifier-tracker-design.md` — read it before starting if anything below is ambiguous.

---

## Task 1: Project scaffolding and shared data model

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `models.py`
- Create: `sources/__init__.py`
- Create: `sources/custom/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/` (empty dir, fixtures added by later tasks)

**Interfaces:**
- Produces: `Posting`, `CompanyConfig`, `AggregatorConfig`, `KeywordConfig` dataclasses in `models.py`, imported by every later task.

No test-first cycle for this task — these are scaffolding and pure data containers with no behavior to verify yet. Later tasks' tests exercise them indirectly.

- [ ] **Step 1: Create `requirements.txt`**

```
requests>=2.31
gspread>=6.0
google-auth>=2.28
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
requests-mock>=1.12
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
service-account.json
.pytest_cache/
```

- [ ] **Step 4: Create `.env.example`**

```
GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json
GOOGLE_SHEET_ID=
NTFY_TOPIC_URL=https://ntfy.sh/your-topic-name-here
```

- [ ] **Step 5: Create `models.py`**

```python
from dataclasses import dataclass


@dataclass
class Posting:
    company: str
    title: str
    location: str
    link: str
    is_internship: bool


@dataclass
class CompanyConfig:
    row_index: int
    company: str
    ats_type: str  # "greenhouse" | "lever" | "ashby" | "custom" | "unsupported"
    identifier: str
    consecutive_failures: int


@dataclass
class AggregatorConfig:
    row_index: int
    source_type: str  # "github_list"
    identifier: str
    consecutive_failures: int


@dataclass
class KeywordConfig:
    include: list[str]
    exclude: list[str]
```

- [ ] **Step 6: Create empty package files**

```bash
mkdir -p sources/custom tests/fixtures
touch sources/__init__.py sources/custom/__init__.py tests/__init__.py
```

- [ ] **Step 7: Install dependencies and verify import**

```bash
pip install -r requirements-dev.txt
python3 -c "from models import Posting, CompanyConfig, AggregatorConfig, KeywordConfig; print('ok')"
```

Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt requirements-dev.txt .gitignore .env.example models.py sources tests
git commit -m "Add project scaffolding and shared data model"
```

---

## Task 2: Matcher

**Files:**
- Create: `matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `Posting`, `KeywordConfig` from `models.py` (Task 1).
- Produces: `filter_relevant(postings: list[Posting], keywords: KeywordConfig) -> list[Posting]`, used by `main.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_matcher.py
from models import Posting, KeywordConfig
from matcher import filter_relevant

KEYWORDS = KeywordConfig(
    include=["software engineer", "hardware engineer", "quant", "ai engineer"],
    exclude=["senior", "staff", "principal"],
)


def _posting(title, is_internship=False):
    return Posting(company="Acme", title=title, location="NYC", link="https://x/1", is_internship=is_internship)


def test_matches_include_keyword_and_internship_title():
    postings = [_posting("Software Engineer Intern")]
    result = filter_relevant(postings, KEYWORDS)
    assert result == postings


def test_rejects_missing_include_keyword():
    postings = [_posting("Marketing Intern")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_rejects_exclude_keyword_even_with_include_match():
    postings = [_posting("Senior Software Engineer Intern")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_rejects_full_time_role_without_internship_signal():
    postings = [_posting("Software Engineer")]
    assert filter_relevant(postings, KEYWORDS) == []


def test_trusts_is_internship_flag_even_without_title_keyword():
    postings = [_posting("Data Engineer", is_internship=True)]
    keywords = KeywordConfig(include=["data engineer"], exclude=[])
    assert filter_relevant(postings, keywords) == postings


def test_case_insensitive_matching():
    postings = [_posting("QUANT TRADING INTERN")]
    assert filter_relevant(postings, KEYWORDS) == postings
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_matcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matcher'`

- [ ] **Step 3: Write the implementation**

```python
# matcher.py
from models import Posting, KeywordConfig

LEVEL_KEYWORDS = ("intern", "internship", "co-op", "coop")


def is_relevant(posting: Posting, keywords: KeywordConfig) -> bool:
    title = posting.title.lower()
    if not any(kw.lower() in title for kw in keywords.include):
        return False
    if any(kw.lower() in title for kw in keywords.exclude):
        return False
    if posting.is_internship:
        return True
    return any(kw in title for kw in LEVEL_KEYWORDS)


def filter_relevant(postings: list[Posting], keywords: KeywordConfig) -> list[Posting]:
    return [p for p in postings if is_relevant(p, keywords)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_matcher.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add matcher.py tests/test_matcher.py
git commit -m "Add keyword/level matcher"
```

---

## Task 3: Dedup

**Files:**
- Create: `dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `filter_new_postings(postings: list[Posting], existing_links: set[str]) -> list[Posting]`, used by `main.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dedup.py
from models import Posting
from dedup import filter_new_postings


def _posting(link):
    return Posting(company="Acme", title="Software Engineer Intern", location="NYC", link=link, is_internship=True)


def test_drops_postings_with_seen_links():
    postings = [_posting("https://x/1"), _posting("https://x/2")]
    result = filter_new_postings(postings, existing_links={"https://x/1"})
    assert result == [postings[1]]


def test_keeps_all_when_no_links_seen():
    postings = [_posting("https://x/1"), _posting("https://x/2")]
    assert filter_new_postings(postings, existing_links=set()) == postings


def test_dedup_is_per_posting_not_per_company():
    same_company = [_posting("https://x/1"), _posting("https://x/2")]
    result = filter_new_postings(same_company, existing_links={"https://x/1"})
    assert len(result) == 1
    assert result[0].link == "https://x/2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dedup'`

- [ ] **Step 3: Write the implementation**

```python
# dedup.py
from models import Posting


def filter_new_postings(postings: list[Posting], existing_links: set[str]) -> list[Posting]:
    return [p for p in postings if p.link not in existing_links]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dedup.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add dedup.py tests/test_dedup.py
git commit -m "Add link-based dedup"
```

---

## Task 4: Greenhouse connector

**Files:**
- Create: `sources/greenhouse.py`
- Create: `tests/fixtures/greenhouse_sample.json`
- Test: `tests/test_greenhouse.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch(company: str, board_token: str) -> list[Posting]`, used by `main.py` (Task 13).

Fixture captured from the real API during design (`https://boards-api.greenhouse.io/v1/boards/aquaticcapitalmanagement/jobs`), trimmed to 2 jobs.

- [ ] **Step 1: Create the fixture**

```json
// tests/fixtures/greenhouse_sample.json
{
  "jobs": [
    {
      "id": 7529282002,
      "title": "Quantitative Researcher",
      "absolute_url": "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/7529282002",
      "location": {"name": "Chicago; New York; London"},
      "updated_at": "2026-07-15T10:00:00-04:00"
    },
    {
      "id": 8489233002,
      "title": "Software Engineer, Intern (Summer 2027)",
      "absolute_url": "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/8489233002",
      "location": {"name": "Chicago, London"},
      "updated_at": "2026-06-01T09:00:00-04:00"
    }
  ],
  "meta": {"total": 2}
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_greenhouse.py
import json
from sources import greenhouse


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/greenhouse_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://boards-api.greenhouse.io/v1/boards/aquaticcapitalmanagement/jobs",
        json=fixture,
    )
    postings = greenhouse.fetch("Aquatic", "aquaticcapitalmanagement")
    assert len(postings) == 2
    assert postings[0].company == "Aquatic"
    assert postings[0].title == "Quantitative Researcher"
    assert postings[0].link == "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/7529282002"
    assert postings[0].location == "Chicago; New York; London"
    assert postings[0].is_internship is False
    assert postings[1].title == "Software Engineer, Intern (Summer 2027)"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_greenhouse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.greenhouse'`

- [ ] **Step 4: Write the implementation**

```python
# sources/greenhouse.py
import requests

from models import Posting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch(company: str, board_token: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(token=board_token), timeout=15)
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_greenhouse.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add sources/greenhouse.py tests/fixtures/greenhouse_sample.json tests/test_greenhouse.py
git commit -m "Add Greenhouse connector"
```

---

## Task 5: Lever connector

**Files:**
- Create: `sources/lever.py`
- Create: `tests/fixtures/lever_sample.json`
- Test: `tests/test_lever.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch(company: str, slug: str) -> list[Posting]`, used by `main.py` (Task 13).

Fixture captured from the real API during design (`https://api.lever.co/v0/postings/palantir?mode=json`), trimmed to 2 postings.

- [ ] **Step 1: Create the fixture**

```json
// tests/fixtures/lever_sample.json
[
  {
    "id": "ac978161-6f46-4f6b-ad9e-a258e642751c",
    "text": "Administrative Business Partner",
    "hostedUrl": "https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c",
    "categories": {"commitment": "Full-time", "location": "London, United Kingdom", "team": "Administrative"},
    "createdAt": 1720000000000
  },
  {
    "id": "373367a9-3160-49d8-b7af-2efec062fad1",
    "text": "Software Engineer, Internship - Production Infrastructure",
    "hostedUrl": "https://jobs.lever.co/palantir/373367a9-3160-49d8-b7af-2efec062fad1",
    "categories": {"commitment": "Internship", "location": "Seattle", "team": "Engineering"},
    "createdAt": 1721000000000
  }
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_lever.py
import json
from sources import lever


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/lever_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://api.lever.co/v0/postings/palantir?mode=json",
        json=fixture,
    )
    postings = lever.fetch("Palantir", "palantir")
    assert len(postings) == 2
    assert postings[1].company == "Palantir"
    assert postings[1].title == "Software Engineer, Internship - Production Infrastructure"
    assert postings[1].link == "https://jobs.lever.co/palantir/373367a9-3160-49d8-b7af-2efec062fad1"
    assert postings[1].location == "Seattle"
    assert postings[1].is_internship is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_lever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.lever'`

- [ ] **Step 4: Write the implementation**

```python
# sources/lever.py
import requests

from models import Posting

BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch(company: str, slug: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(slug=slug), timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company=company,
            title=job["text"],
            location=job.get("categories", {}).get("location", ""),
            link=job["hostedUrl"],
            is_internship=False,
        )
        for job in data
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_lever.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add sources/lever.py tests/fixtures/lever_sample.json tests/test_lever.py
git commit -m "Add Lever connector"
```

---

## Task 6: Ashby connector

**Files:**
- Create: `sources/ashby.py`
- Create: `tests/fixtures/ashby_sample.json`
- Test: `tests/test_ashby.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch(company: str, board_name: str) -> list[Posting]`, used by `main.py` (Task 13).

Fixture captured from the real API during design (`https://api.ashbyhq.com/posting-api/job-board/netic`), trimmed to 2 jobs.

- [ ] **Step 1: Create the fixture**

```json
// tests/fixtures/ashby_sample.json
{
  "jobs": [
    {
      "id": "61d96f6a-757f-47e1-91fd-be2289ef13d7",
      "title": "Software Engineer, Product Infrastructure",
      "location": "San Francisco",
      "jobUrl": "https://jobs.ashbyhq.com/netic/61d96f6a-757f-47e1-91fd-be2289ef13d7",
      "publishedAt": "2026-06-01T00:00:00.000Z",
      "isListed": true
    },
    {
      "id": "b0ea7aab-8eea-4d31-96f9-278364180ae7",
      "title": "Software Engineer (Agent Platform) - Intern - 2026-2027",
      "location": "San Francisco",
      "jobUrl": "https://jobs.ashbyhq.com/netic/b0ea7aab-8eea-4d31-96f9-278364180ae7",
      "publishedAt": "2026-06-10T00:00:00.000Z",
      "isListed": true
    }
  ],
  "apiVersion": "1"
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ashby.py
import json
from sources import ashby


def test_fetch_returns_normalized_postings(requests_mock):
    with open("tests/fixtures/ashby_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get(
        "https://api.ashbyhq.com/posting-api/job-board/netic",
        json=fixture,
    )
    postings = ashby.fetch("Netic", "netic")
    assert len(postings) == 2
    assert postings[1].company == "Netic"
    assert postings[1].title == "Software Engineer (Agent Platform) - Intern - 2026-2027"
    assert postings[1].link == "https://jobs.ashbyhq.com/netic/b0ea7aab-8eea-4d31-96f9-278364180ae7"
    assert postings[1].location == "San Francisco"
    assert postings[1].is_internship is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ashby.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.ashby'`

- [ ] **Step 4: Write the implementation**

```python
# sources/ashby.py
import requests

from models import Posting

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


def fetch(company: str, board_name: str) -> list[Posting]:
    response = requests.get(BASE_URL.format(board_name=board_name), timeout=15)
    response.raise_for_status()
    data = response.json()
    return [
        Posting(
            company=company,
            title=job["title"],
            location=job.get("location", ""),
            link=job["jobUrl"],
            is_internship=False,
        )
        for job in data.get("jobs", [])
        if job.get("isListed", True)
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ashby.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add sources/ashby.py tests/fixtures/ashby_sample.json tests/test_ashby.py
git commit -m "Add Ashby connector"
```

---

## Task 7: Jane Street custom scraper

**Files:**
- Create: `sources/custom/jane_street.py`
- Create: `tests/fixtures/jane_street_sample.json`
- Test: `tests/test_jane_street.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch() -> list[Posting]`, registered in `main.py`'s `CUSTOM_SCRAPERS` dict (Task 13) under key `"jane_street"`.

Fixture captured from the real endpoint during design (`https://www.janestreet.com/jobs/main.json`), trimmed to 3 entries: one full-time role (must be excluded), one plain-text internship title, and one internship whose title is genuinely rendered with obfuscated Unicode glyphs by Jane Street's own site (an anti-scraping/IP-protection measure specific to certain Machine Learning Research titles — verified live, not a hypothetical). The scraper doesn't attempt to decode this; it passes the title through as-is, which is a known, documented limitation (see spec's Data model section).

- [ ] **Step 1: Create the fixture**

```json
// tests/fixtures/jane_street_sample.json
[
  {
    "id": 8213653002,
    "position": "ASIC Engineer",
    "category": "Software Engineering",
    "availability": "Full-Time: Experienced",
    "city": "NYC",
    "team": "Software Engineering",
    "duration": null
  },
  {
    "id": 8631973002,
    "position": "Data Engineer",
    "category": "Software Engineering",
    "availability": "Summer Internship",
    "city": "NYC",
    "team": "Software Engineering",
    "duration": "May-August"
  },
  {
    "id": 8596771002,
    "position": "ਟachine ਡearning ਣesearcher",
    "category": "Machine Learning",
    "availability": "Summer Internship",
    "city": "HKG",
    "team": "Machine Learning",
    "duration": "May-August"
  }
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_jane_street.py
import json
from sources.custom import jane_street


def test_fetch_filters_to_internships_only(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    assert len(postings) == 2
    assert all(p.is_internship for p in postings)
    assert all(p.company == "Jane Street" for p in postings)


def test_fetch_builds_link_from_id(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    data_engineer = next(p for p in postings if p.title == "Data Engineer")
    assert data_engineer.link == "https://www.janestreet.com/join-jane-street/position/8631973002/"
    assert data_engineer.location == "NYC"


def test_fetch_passes_through_obfuscated_title_without_decoding(requests_mock):
    with open("tests/fixtures/jane_street_sample.json") as f:
        fixture = json.load(f)
    requests_mock.get("https://www.janestreet.com/jobs/main.json", json=fixture)
    postings = jane_street.fetch()
    obfuscated = next(p for p in postings if p.link.endswith("8596771002/"))
    assert obfuscated.is_internship is True
    assert "achine" in obfuscated.title  # not decoded to "Machine" — documented limitation
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_jane_street.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.custom.jane_street'`

- [ ] **Step 4: Write the implementation**

```python
# sources/custom/jane_street.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_jane_street.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add sources/custom/jane_street.py tests/fixtures/jane_street_sample.json tests/test_jane_street.py
git commit -m "Add Jane Street custom scraper"
```

---

## Task 8: D. E. Shaw custom scraper

**Files:**
- Create: `sources/custom/de_shaw.py`
- Create: `tests/fixtures/de_shaw_sample.html`
- Test: `tests/test_de_shaw.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch() -> list[Posting]`, registered in `main.py`'s `CUSTOM_SCRAPERS` dict (Task 13) under key `"de_shaw"`.

D. E. Shaw's `/careers/internships` page embeds job data as a Next.js `__NEXT_DATA__` JSON blob rather than static HTML — verified live during design. Fixture below is a trimmed but structurally real version of that blob (3 entries: 2 real internships and 1 without `workStatus`, to exercise the filter).

- [ ] **Step 1: Create the fixture**

```html
<!-- tests/fixtures/de_shaw_sample.html -->
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"internships":[
  {"id":5894,"displayName":"Software Developer Intern (New York) – Summer 2027","jobUrl":"Software-Developer-Intern-New-York-Summer-2027-5894","jobMetadata":{"workStatus":"Intern","jobLocations":[{"name":"New York"}]}},
  {"id":5709,"displayName":"Fundamental Research Analyst Intern (New York) – Summer 2027","jobUrl":"Fundamental-Research-Analyst-Intern-New-York-Summer-2027-5709","jobMetadata":{"workStatus":"Intern","jobLocations":[{"name":"New York"}]}},
  {"id":5874,"displayName":"Administrative Associate (6-Month LTA)","jobUrl":"Administrative-Associate-5874","jobMetadata":{"jobLocations":[]}}
]}}}
</script>
</body></html>
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_de_shaw.py
from sources.custom import de_shaw


def test_fetch_filters_to_interns_only(requests_mock):
    with open("tests/fixtures/de_shaw_sample.html") as f:
        html = f.read()
    requests_mock.get("https://www.deshaw.com/careers/internships", text=html)
    postings = de_shaw.fetch()
    assert len(postings) == 2
    assert all(p.is_internship for p in postings)
    assert all(p.company == "D. E. Shaw" for p in postings)


def test_fetch_builds_link_from_job_url(requests_mock):
    with open("tests/fixtures/de_shaw_sample.html") as f:
        html = f.read()
    requests_mock.get("https://www.deshaw.com/careers/internships", text=html)
    postings = de_shaw.fetch()
    software = next(p for p in postings if "Software Developer" in p.title)
    assert software.link == (
        "https://www.deshaw.com/careers/internships/"
        "Software-Developer-Intern-New-York-Summer-2027-5894"
    )
    assert software.location == "New York"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_de_shaw.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.custom.de_shaw'`

- [ ] **Step 4: Write the implementation**

```python
# sources/custom/de_shaw.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_de_shaw.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add sources/custom/de_shaw.py tests/fixtures/de_shaw_sample.html tests/test_de_shaw.py
git commit -m "Add D. E. Shaw custom scraper"
```

---

## Task 9: GitHub-list aggregator connector

**Files:**
- Create: `sources/github_list.py`
- Create: `tests/fixtures/github_list_sample.md`
- Test: `tests/test_github_list.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `fetch(repo: str) -> list[Posting]`, used by `main.py` (Task 13). Callers must NOT run these postings through `matcher.filter_relevant` — they're trusted as-is per the user's instruction (see spec's Non-goals/Architecture).

Fixture is a trimmed excerpt of the real table format from `github.com/sndsh404/summer-2027-internships`'s README, captured live during design.

- [ ] **Step 1: Create the fixture**

```markdown
<!-- tests/fixtures/github_list_sample.md -->
# Summer 2027 Tech Internships

Some intro text that should be ignored by the parser.

## the list

| Company | Role | Location | Apply | Added |
| --- | --- | --- | --- | --- |
| Susquehanna | Quantitative Systematic Trading Intern (PhD, Summer 2027) | New York, NY | [apply](https://careers.sig.com/jobs/10822) | 2026-07-21 |
| Google | Software Engineering Intern, BS (Summer 2027) | Mountain View, CA (multiple US) | [apply](https://www.google.com/about/careers/applications/jobs/results/85564713261245126) | 2026-07-21 |
| Closed Co | Some Closed Role 🔒 | Remote | [apply](https://example.com/closed) | 2026-07-01 |

Trailing text after the table should also be ignored.
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_github_list.py
from sources import github_list


def test_fetch_parses_table_rows(requests_mock):
    with open("tests/fixtures/github_list_sample.md") as f:
        readme = f.read()
    requests_mock.get(
        "https://raw.githubusercontent.com/sndsh404/summer-2027-internships/main/README.md",
        text=readme,
    )
    postings = github_list.fetch("sndsh404/summer-2027-internships")
    assert len(postings) == 3
    assert postings[0].company == "Susquehanna"
    assert postings[0].title == "Quantitative Systematic Trading Intern (PhD, Summer 2027)"
    assert postings[0].location == "New York, NY"
    assert postings[0].link == "https://careers.sig.com/jobs/10822"
    assert postings[0].is_internship is True


def test_fetch_falls_back_to_master_branch(requests_mock):
    with open("tests/fixtures/github_list_sample.md") as f:
        readme = f.read()
    requests_mock.get(
        "https://raw.githubusercontent.com/someuser/somerepo/main/README.md",
        status_code=404,
    )
    requests_mock.get(
        "https://raw.githubusercontent.com/someuser/somerepo/master/README.md",
        text=readme,
    )
    postings = github_list.fetch("someuser/somerepo")
    assert len(postings) == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_github_list.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.github_list'`

- [ ] **Step 4: Write the implementation**

```python
# sources/github_list.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_github_list.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add sources/github_list.py tests/fixtures/github_list_sample.md tests/test_github_list.py
git commit -m "Add GitHub-list aggregator connector"
```

---

## Task 10: Notifier

**Files:**
- Create: `notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: `Posting` from `models.py`.
- Produces: `send_text(topic_url: str, message: str) -> None` and `send_posting(topic_url: str, posting: Posting) -> None`, both used by `main.py` (Task 13) — `send_posting` for matches, `send_text` for scraper-failure alerts.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_notifier.py
from models import Posting
import notifier


def test_send_text_posts_message_to_topic_url(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    notifier.send_text("https://ntfy.sh/my-topic", "hello world")
    assert requests_mock.last_request.body == b"hello world"


def test_send_posting_formats_company_title_location_link(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    posting = Posting(
        company="Acme", title="Software Engineer Intern", location="NYC",
        link="https://acme.com/jobs/1", is_internship=True,
    )
    notifier.send_posting("https://ntfy.sh/my-topic", posting)
    body = requests_mock.last_request.body.decode("utf-8")
    assert "Acme: Software Engineer Intern (NYC)" in body
    assert "https://acme.com/jobs/1" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Write the implementation**

```python
# notifier.py
import requests

from models import Posting


def send_text(topic_url: str, message: str) -> None:
    response = requests.post(topic_url, data=message.encode("utf-8"), timeout=15)
    response.raise_for_status()


def send_posting(topic_url: str, posting: Posting) -> None:
    message = f"{posting.company}: {posting.title} ({posting.location})\n{posting.link}"
    send_text(topic_url, message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "Add ntfy.sh notifier"
```

---

## Task 11: Google Cloud service account and test Sheet setup

This task has no code — it produces the credentials and test fixture that Task 12's integration tests require. Do this before Task 12.

- [ ] **Step 1: Create a Google Cloud project and service account**

Go to https://console.cloud.google.com/ → create a new project (e.g. "job-scraper") → APIs & Services → Enable "Google Sheets API" → Credentials → Create Credentials → Service Account → give it any name (e.g. `job-scraper-bot`) → Create Key → JSON → download the file.

- [ ] **Step 2: Save the credentials locally (never commit this file)**

```bash
mv ~/Downloads/job-scraper-*.json "/Users/amandachiang/Downloads/School/Projects/job-scraper/service-account.json"
```

Verify `.gitignore` (Task 1) already excludes `service-account.json` — it does.

- [ ] **Step 3: Create a test Google Sheet for integration tests**

In Google Sheets, create a new spreadsheet named "job-scraper-test" with four tabs:
- `Tracker`, header row: `Company | Link | Position | Location | Date Applied | Status | Referral? | Notes | Date Found`
- `Config`, header row: `Company | ATS Type | Board Token or Slug | Consecutive Failures | Last Error | Last Success At | Notes`
- `Aggregators`, header row: `Type | Repo or URL | Consecutive Failures | Last Error | Last Success At | Notes`
- `Keywords`, header row: `Type | Keyword`, with two seed rows: `include | software engineer` and `exclude | senior`

Share this sheet with the service account's email address (found inside `service-account.json` as `client_email`), with Editor access.

- [ ] **Step 4: Export test credentials as environment variables**

```bash
export GOOGLE_SERVICE_ACCOUNT_PATH="/Users/amandachiang/Downloads/School/Projects/job-scraper/service-account.json"
export GOOGLE_TEST_SHEET_ID="<the spreadsheet ID from its URL>"
```

Add these two lines to your shell profile (`~/.zshrc`) so they persist across terminal sessions, since Task 12's integration tests read them and skip themselves when absent.

---

## Task 12: Sheets client

**Files:**
- Create: `sheets_client.py`
- Test: `tests/test_sheets_client.py`

**Interfaces:**
- Consumes: `Posting`, `CompanyConfig`, `AggregatorConfig`, `KeywordConfig` from `models.py`. Requires `GOOGLE_SERVICE_ACCOUNT_PATH` and `GOOGLE_TEST_SHEET_ID` env vars from Task 11 to run its integration tests (skipped otherwise).
- Produces: `SheetsClient` class with `read_company_list`, `read_aggregator_sources`, `read_keywords`, `get_existing_links`, `append_row`, `record_source_result`; and module-level constants `TRACKER_TAB`, `CONFIG_TAB`, `AGGREGATOR_TAB`, `KEYWORDS_TAB` — all used by `main.py` (Task 13).

These are integration tests against a real (test) Google Sheet, not fixtures — gspread's behavior (header lookup, `get_all_records`, cell updates) is exactly what needs verifying, and mocking it would only verify the mock. Tests are skipped via `pytest.mark.skipif` when credentials aren't configured, so the suite still runs (skipping these) in any environment without them.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sheets_client.py
import datetime
import os

import pytest

from models import Posting
from sheets_client import SheetsClient, TRACKER_TAB, CONFIG_TAB, AGGREGATOR_TAB, KEYWORDS_TAB

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_TEST_SHEET_ID"),
    reason="GOOGLE_TEST_SHEET_ID not set — skipping live Google Sheets integration tests",
)


@pytest.fixture
def client():
    return SheetsClient(
        service_account_path=os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"],
        sheet_id=os.environ["GOOGLE_TEST_SHEET_ID"],
    )


def test_read_company_list_reads_config_tab(client):
    ws = client._tab(CONFIG_TAB)
    ws.append_row(["Read Test Co", "lever", "readtestco", 2, "", "", "seeded by test"])
    row_index = len(ws.get_all_values())
    companies = client.read_company_list()
    match = next(c for c in companies if c.company == "Read Test Co")
    assert match.ats_type == "lever"
    assert match.identifier == "readtestco"
    assert match.consecutive_failures == 2
    assert match.row_index == row_index


def test_read_aggregator_sources_reads_aggregators_tab(client):
    ws = client._tab(AGGREGATOR_TAB)
    ws.append_row(["github_list", "someuser/somerepo", 0, "", "", "seeded by test"])
    row_index = len(ws.get_all_values())
    aggregators = client.read_aggregator_sources()
    match = next(a for a in aggregators if a.identifier == "someuser/somerepo")
    assert match.source_type == "github_list"
    assert match.row_index == row_index


def test_read_keywords_splits_include_and_exclude(client):
    keywords = client.read_keywords()
    assert "software engineer" in keywords.include
    assert "senior" in keywords.exclude


def test_append_row_writes_named_columns_and_date_found(client):
    posting = Posting(
        company="Test Co", title="Test Intern Role", location="Remote",
        link=f"https://example.com/test-{datetime.datetime.utcnow().timestamp()}",
        is_internship=True,
    )
    client.append_row(posting)
    ws = client._tab(TRACKER_TAB)
    header = ws.row_values(1)
    last_row = ws.get_all_values()[-1]
    row = dict(zip(header, last_row))
    assert row["Company"] == "Test Co"
    assert row["Link"] == posting.link
    assert row["Position"] == "Test Intern Role"
    assert row["Location"] == "Remote"
    assert row["Date Found"] == datetime.date.today().isoformat()
    assert row["Date Applied"] == ""


def test_get_existing_links_includes_appended_link(client):
    posting = Posting(
        company="Test Co", title="Another Test Role", location="Remote",
        link=f"https://example.com/test2-{datetime.datetime.utcnow().timestamp()}",
        is_internship=True,
    )
    client.append_row(posting)
    links = client.get_existing_links()
    assert posting.link in links


def test_record_source_result_success_resets_failures(client):
    ws = client._tab(CONFIG_TAB)
    ws.append_row(["Test Company", "greenhouse", "testtoken", 3, "some old error", "", "test row"])
    row_index = len(ws.get_all_values())
    client.record_source_result(CONFIG_TAB, row_index, success=True, error=None)
    header = ws.row_values(1)
    updated = ws.row_values(row_index)
    row = dict(zip(header, updated))
    assert row["Consecutive Failures"] == "0"
    assert row["Last Success At"] != ""


def test_record_source_result_failure_increments_and_records_error(client):
    ws = client._tab(CONFIG_TAB)
    ws.append_row(["Test Company 2", "greenhouse", "testtoken2", 1, "", "", "test row"])
    row_index = len(ws.get_all_values())
    client.record_source_result(CONFIG_TAB, row_index, success=False, error="boom: connection refused")
    header = ws.row_values(1)
    updated = ws.row_values(row_index)
    row = dict(zip(header, updated))
    assert row["Consecutive Failures"] == "2"
    assert "boom" in row["Last Error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sheets_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sheets_client'`

- [ ] **Step 3: Write the implementation**

```python
# sheets_client.py
import datetime

import gspread

from models import AggregatorConfig, CompanyConfig, KeywordConfig, Posting

TRACKER_TAB = "Tracker"
CONFIG_TAB = "Config"
AGGREGATOR_TAB = "Aggregators"
KEYWORDS_TAB = "Keywords"


class SheetsClient:
    def __init__(self, service_account_path: str, sheet_id: str):
        gc = gspread.service_account(filename=service_account_path)
        self._spreadsheet = gc.open_by_key(sheet_id)

    def _tab(self, name: str):
        return self._spreadsheet.worksheet(name)

    def read_company_list(self) -> list[CompanyConfig]:
        ws = self._tab(CONFIG_TAB)
        rows = ws.get_all_records()
        return [
            CompanyConfig(
                row_index=i + 2,
                company=row["Company"],
                ats_type=row["ATS Type"],
                identifier=row["Board Token or Slug"],
                consecutive_failures=int(row.get("Consecutive Failures") or 0),
            )
            for i, row in enumerate(rows)
        ]

    def read_aggregator_sources(self) -> list[AggregatorConfig]:
        ws = self._tab(AGGREGATOR_TAB)
        rows = ws.get_all_records()
        return [
            AggregatorConfig(
                row_index=i + 2,
                source_type=row["Type"],
                identifier=row["Repo or URL"],
                consecutive_failures=int(row.get("Consecutive Failures") or 0),
            )
            for i, row in enumerate(rows)
        ]

    def read_keywords(self) -> KeywordConfig:
        ws = self._tab(KEYWORDS_TAB)
        rows = ws.get_all_records()
        include = [r["Keyword"] for r in rows if r["Type"].strip().lower() == "include"]
        exclude = [r["Keyword"] for r in rows if r["Type"].strip().lower() == "exclude"]
        return KeywordConfig(include=include, exclude=exclude)

    def get_existing_links(self) -> set[str]:
        ws = self._tab(TRACKER_TAB)
        header = ws.row_values(1)
        link_col = header.index("Link") + 1
        values = ws.col_values(link_col)[1:]
        return {v for v in values if v}

    def append_row(self, posting: Posting) -> None:
        ws = self._tab(TRACKER_TAB)
        header = ws.row_values(1)
        row = [""] * len(header)
        field_map = {
            "Company": posting.company,
            "Link": posting.link,
            "Position": posting.title,
            "Location": posting.location,
            "Date Found": datetime.date.today().isoformat(),
        }
        for name, value in field_map.items():
            if name in header:
                row[header.index(name)] = value
        ws.append_row(row, value_input_option="RAW")

    def record_source_result(
        self, tab_name: str, row_index: int, success: bool, error: str | None
    ) -> None:
        ws = self._tab(tab_name)
        header = ws.row_values(1)
        if success:
            updates = {
                "Consecutive Failures": 0,
                "Last Success At": datetime.datetime.utcnow().isoformat(timespec="seconds"),
            }
        else:
            current = ws.cell(row_index, header.index("Consecutive Failures") + 1).value
            updates = {
                "Consecutive Failures": int(current or 0) + 1,
                "Last Error": (error or "")[:300],
            }
        for name, value in updates.items():
            if name in header:
                ws.update_cell(row_index, header.index(name) + 1, value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sheets_client.py -v`
Expected: 7 passed (or 7 skipped, if `GOOGLE_TEST_SHEET_ID` isn't set in this environment)

- [ ] **Step 5: Commit**

```bash
git add sheets_client.py tests/test_sheets_client.py
git commit -m "Add Google Sheets client"
```

---

## Task 13: Main orchestration

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `matcher.filter_relevant` (Task 2), `dedup.filter_new_postings` (Task 3), `notifier.send_text`/`send_posting` (Task 10), `SheetsClient` + tab constants (Task 12), `sources.greenhouse/lever/ashby/github_list`, `sources.custom.jane_street/de_shaw`.
- Produces: `run(sheets: SheetsClient, topic_url: str) -> None`, the single entry point Railway's scheduler invokes via `python main.py`.

This task tests `run()` against fully mocked collaborators (fake `SheetsClient`-shaped object, monkeypatched connector functions) rather than real Sheets/HTTP calls — by this point every collaborator already has its own passing tests, so `test_main.py` only needs to verify the orchestration logic (ordering, error isolation, alert threshold) is correct.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
from unittest.mock import MagicMock, patch

from models import AggregatorConfig, CompanyConfig, KeywordConfig, Posting
import main


def _company(ats_type="greenhouse", failures=0, row_index=2):
    return CompanyConfig(
        row_index=row_index, company="Acme", ats_type=ats_type,
        identifier="acme", consecutive_failures=failures,
    )


def _fake_sheets(companies=None, aggregators=None, existing_links=None):
    sheets = MagicMock()
    sheets.read_keywords.return_value = KeywordConfig(include=["software engineer"], exclude=["senior"])
    sheets.read_company_list.return_value = companies or []
    sheets.read_aggregator_sources.return_value = aggregators or []
    sheets.get_existing_links.return_value = existing_links or set()
    return sheets


def test_new_match_is_logged_and_notified():
    posting = Posting(
        company="Acme", title="Software Engineer Intern", location="NYC",
        link="https://acme.com/1", is_internship=True,
    )
    sheets = _fake_sheets(companies=[_company()])
    with patch("main.greenhouse.fetch", return_value=[posting]), \
         patch("main.notifier.send_posting") as mock_notify:
        main.run(sheets, topic_url="https://ntfy.sh/test")
    sheets.append_row.assert_called_once_with(posting)
    mock_notify.assert_called_once_with("https://ntfy.sh/test", posting)


def test_already_seen_link_is_not_renotified():
    posting = Posting(
        company="Acme", title="Software Engineer Intern", location="NYC",
        link="https://acme.com/1", is_internship=True,
    )
    sheets = _fake_sheets(companies=[_company()], existing_links={"https://acme.com/1"})
    with patch("main.greenhouse.fetch", return_value=[posting]), \
         patch("main.notifier.send_posting") as mock_notify:
        main.run(sheets, topic_url="https://ntfy.sh/test")
    sheets.append_row.assert_not_called()
    mock_notify.assert_not_called()


def test_company_fetch_failure_does_not_abort_run():
    company_a = _company(row_index=2)
    posting_b = Posting(
        company="Beta", title="Software Engineer Intern", location="SF",
        link="https://beta.com/1", is_internship=True,
    )
    sheets = _fake_sheets(companies=[company_a])
    with patch("main.greenhouse.fetch", side_effect=[Exception("network error"), [posting_b]]), \
         patch("main.notifier.send_posting"), patch("main.notifier.send_text"):
        main.run(sheets, topic_url="https://ntfy.sh/test")
    sheets.record_source_result.assert_any_call(
        main.CONFIG_TAB, company_a.row_index, success=False, error="network error"
    )


def test_fifth_consecutive_failure_sends_alert():
    company_a = _company(failures=4, row_index=2)
    sheets = _fake_sheets(companies=[company_a])
    with patch("main.greenhouse.fetch", side_effect=Exception("still broken")), \
         patch("main.notifier.send_text") as mock_alert:
        main.run(sheets, topic_url="https://ntfy.sh/test")
    mock_alert.assert_called_once()
    assert "Acme" in mock_alert.call_args[0][1]


def test_aggregator_postings_skip_matcher_entirely():
    posting = Posting(
        company="Random Startup", title="Marketing Coordinator", location="Remote",
        link="https://randomstartup.com/1", is_internship=True,
    )
    aggregator = AggregatorConfig(row_index=2, source_type="github_list", identifier="a/b", consecutive_failures=0)
    sheets = _fake_sheets(aggregators=[aggregator])
    with patch("main.github_list.fetch", return_value=[posting]), \
         patch("main.notifier.send_posting") as mock_notify:
        main.run(sheets, topic_url="https://ntfy.sh/test")
    sheets.append_row.assert_called_once_with(posting)
    mock_notify.assert_called_once_with("https://ntfy.sh/test", posting)


def test_unsupported_ats_type_is_skipped_without_fetch():
    sheets = _fake_sheets(companies=[_company(ats_type="unsupported")])
    with patch("main.greenhouse.fetch") as mock_fetch:
        main.run(sheets, topic_url="https://ntfy.sh/test")
    mock_fetch.assert_not_called()
    sheets.record_source_result.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write the implementation**

```python
# main.py
import os

import notifier
from dedup import filter_new_postings
from matcher import filter_relevant
from sheets_client import AGGREGATOR_TAB, CONFIG_TAB, SheetsClient
from sources import ashby, github_list, greenhouse, lever
from sources.custom import de_shaw, jane_street

FAILURE_ALERT_THRESHOLD = 5

CUSTOM_SCRAPERS = {
    "jane_street": jane_street.fetch,
    "de_shaw": de_shaw.fetch,
}


def _fetch_company_postings(company_config):
    if company_config.ats_type == "greenhouse":
        return greenhouse.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "lever":
        return lever.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "ashby":
        return ashby.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "custom":
        return CUSTOM_SCRAPERS[company_config.identifier]()
    return []


def _handle_source_result(sheets, tab_name, source_config, topic_url, error):
    if error is None:
        sheets.record_source_result(tab_name, source_config.row_index, success=True, error=None)
        return
    sheets.record_source_result(tab_name, source_config.row_index, success=False, error=str(error))
    failures = source_config.consecutive_failures + 1
    if failures == FAILURE_ALERT_THRESHOLD:
        name = getattr(source_config, "company", None) or source_config.identifier
        notifier.send_text(
            topic_url,
            f"⚠️ {name} has failed {FAILURE_ALERT_THRESHOLD} scrape attempts in a row. "
            f"Last error: {error}",
        )


def run(sheets: SheetsClient, topic_url: str) -> None:
    keywords = sheets.read_keywords()
    existing_links = sheets.get_existing_links()
    new_matches = []

    for company_config in sheets.read_company_list():
        if company_config.ats_type == "unsupported":
            continue
        try:
            postings = _fetch_company_postings(company_config)
        except Exception as exc:
            _handle_source_result(sheets, CONFIG_TAB, company_config, topic_url, exc)
            continue
        _handle_source_result(sheets, CONFIG_TAB, company_config, topic_url, None)
        new_matches.extend(filter_relevant(postings, keywords))

    for aggregator_config in sheets.read_aggregator_sources():
        try:
            postings = github_list.fetch(aggregator_config.identifier)
        except Exception as exc:
            _handle_source_result(sheets, AGGREGATOR_TAB, aggregator_config, topic_url, exc)
            continue
        _handle_source_result(sheets, AGGREGATOR_TAB, aggregator_config, topic_url, None)
        new_matches.extend(postings)  # trusted as-is — no matcher call

    for posting in filter_new_postings(new_matches, existing_links):
        sheets.append_row(posting)
        notifier.send_posting(topic_url, posting)


if __name__ == "__main__":
    sheets_client = SheetsClient(
        service_account_path=os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"],
        sheet_id=os.environ["GOOGLE_SHEET_ID"],
    )
    run(sheets_client, topic_url=os.environ["NTFY_TOPIC_URL"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (Sheets integration tests from Task 12 pass or skip depending on env)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "Add main orchestration run loop"
```

---

## Task 14: Seed data and sheet-seeding script

**Files:**
- Create: `data/companies.csv`
- Create: `data/aggregators.csv`
- Create: `data/keywords.csv`
- Create: `scripts/seed_sheets.py`

**Interfaces:**
- Consumes: `SheetsClient`'s underlying `_spreadsheet` access pattern is not reused here — this script talks to `gspread` directly since seeding is a one-time admin operation, not part of the run-time data flow.
- Produces: a populated `Config`, `Aggregators`, and `Keywords` tab in the user's real Google Sheet, and adds `Date Found` to the real `Tracker` tab if missing. Run once, manually, before Phase 1's first scheduled run.

`ats_type` values: `greenhouse`, `lever`, `ashby`, `custom` (identifier is a `CUSTOM_SCRAPERS` key from Task 13 — currently `jane_street` or `de_shaw`), or `unsupported` (no automated fetch yet; kept in the sheet so the user can see it's tracked-but-not-automated and add a scraper later). Rows tagged `unsupported` with note "verify ATS token" are startups likely on Greenhouse/Lever/Ashby but not confirmed live during design — the user should spot-check and correct these in the sheet as time allows; this is expected follow-up data entry, not a defect.

- [ ] **Step 1: Create `data/companies.csv`**

```csv
company,ats_type,identifier,notes
Jane Street,custom,jane_street,verified live during design
D. E. Shaw,custom,de_shaw,verified live during design
Hudson River Trading,greenhouse,hrttalentcommunity,verified live during design - runs on Greenhouse
Aquatic Capital Management,greenhouse,aquaticcapitalmanagement,verified from user's tracker
Schonfeld,greenhouse,schonfeld,verified from user's tracker
Tower Research Capital,greenhouse,towerresearchcapital,verified from user's tracker
Flow Traders,greenhouse,flowtraders,verified from user's tracker
Akuna Capital,greenhouse,akunacapital,verified from user's tracker (gh_jid embed)
Old Mission Capital,greenhouse,oldmissioncapital,verified from user's tracker (gh_jid embed)
Five Rings,greenhouse,fiveringsllc,verified from user's tracker
Databricks,greenhouse,databricks,verified from user's tracker (gh_jid embed)
The Trade Desk,greenhouse,thetradedesk,verified from user's tracker
Axon,greenhouse,axontalentcommunity,verified from user's tracker
Voloridge Investment Management,greenhouse,voloridgeinvestmentmanagement,verified from user's tracker
Chicago Trading Company,greenhouse,ctccampusboard,verified from user's tracker
PDT Partners,greenhouse,pdtpartners,verified from user's tracker
Virtu,greenhouse,virtu,verified from user's tracker
IMC,greenhouse,imc,verified from user's tracker (eu board)
Palantir,lever,palantir,verified from user's tracker
Ellipsis Labs,ashby,ellipsislabs,verified from user's tracker
Netic,ashby,netic,verified from user's tracker
Monogram,ashby,monogram,verified from user's tracker
Anthelion,ashby,anthelioncap,verified from user's tracker
Together AI,greenhouse,togetherai,verified live during design
Scale AI,greenhouse,scaleai,verified live during design
Cohere,ashby,cohere,verified live during design
ElevenLabs,ashby,elevenlabs,verified live during design
Modal,unsupported,,verify ATS token
Fireworks AI,unsupported,,verify ATS token
Baseten,unsupported,,verify ATS token
Anyscale,unsupported,,verify ATS token
Groq,unsupported,,verify ATS token
Cerebras,unsupported,,verify ATS token
SambaNova,unsupported,,verify ATS token
Lambda,unsupported,,verify ATS token
Replicate,unsupported,,verify ATS token
RunPod,unsupported,,verify ATS token
CoreWeave,unsupported,,verify ATS token
Crusoe Energy,unsupported,,verify ATS token
Tenstorrent,unsupported,,verify ATS token
Modular,unsupported,,verify ATS token
Weights & Biases,unsupported,,verify ATS token
LangChain,unsupported,,verify ATS token
LlamaIndex,unsupported,,verify ATS token
Pinecone,unsupported,,verify ATS token
Weaviate,unsupported,,verify ATS token
Qdrant,unsupported,,verify ATS token
Hugging Face,unsupported,,verify ATS token
Snorkel AI,unsupported,,verify ATS token
Labelbox,unsupported,,verify ATS token
Mistral AI,unsupported,,verify ATS token - "mistral" lever slug returned empty
Anthropic,unsupported,,verify ATS token
Perplexity AI,unsupported,,verify ATS token - greenhouse "perplexityai" returned 404
xAI,unsupported,,verify ATS token
Stability AI,unsupported,,verify ATS token
Character.AI,unsupported,,verify ATS token
Inflection AI,unsupported,,verify ATS token
Adept AI,unsupported,,verify ATS token
Imbue,unsupported,,verify ATS token
Reka AI,unsupported,,verify ATS token
Runway,unsupported,,verify ATS token
Luma AI,unsupported,,verify ATS token
Suno,unsupported,,verify ATS token
Synthesia,unsupported,,verify ATS token
Writer,unsupported,,verify ATS token
Sierra,unsupported,,verify ATS token
Cresta,unsupported,,verify ATS token
Glean,unsupported,,verify ATS token
Harvey AI,unsupported,,verify ATS token
Abridge,unsupported,,verify ATS token
Hippocratic AI,unsupported,,verify ATS token
Cognition Labs,unsupported,,verify ATS token
Anysphere,unsupported,,Cursor - verify ATS token
Codeium,unsupported,,Windsurf - verify ATS token
Applied Intuition,unsupported,,verify ATS token
Waabi,unsupported,,verify ATS token
Skild AI,unsupported,,verify ATS token
Physical Intelligence,unsupported,,verify ATS token
Optiver,unsupported,,custom career site - candidate for future custom scraper
Two Sigma,unsupported,,custom career site - candidate for future custom scraper
Point72,unsupported,,custom career site - candidate for future custom scraper
Susquehanna (SIG),unsupported,,custom career site - candidate for future custom scraper
Google,unsupported,,internal ATS - candidate for future custom scraper
Meta,unsupported,,internal ATS - candidate for future custom scraper
Amazon,unsupported,,internal ATS - candidate for future custom scraper
Microsoft,unsupported,,internal ATS (Workday) - candidate for future custom scraper
Apple,unsupported,,internal ATS - candidate for future custom scraper
Netflix,unsupported,,internal ATS - candidate for future custom scraper
NVIDIA,unsupported,,internal ATS (Workday) - candidate for future custom scraper
Tesla,unsupported,,internal ATS - candidate for future custom scraper
Oracle,unsupported,,internal ATS - candidate for future custom scraper
IBM,unsupported,,internal ATS - candidate for future custom scraper
Salesforce,unsupported,,Workday - candidate for future custom scraper
Adobe,unsupported,,internal ATS - candidate for future custom scraper
TikTok,unsupported,,internal ATS - candidate for future custom scraper
Uber,unsupported,,internal ATS - candidate for future custom scraper
Qualcomm,unsupported,,internal ATS - candidate for future custom scraper
Citadel,unsupported,,blocked by Cloudflare bot challenge - deferred to Phase 3
```

- [ ] **Step 2: Create `data/aggregators.csv`**

```csv
source_type,identifier,notes
github_list,sndsh404/summer-2027-internships,referenced in user's existing tracker
```

- [ ] **Step 3: Create `data/keywords.csv`**

```csv
type,keyword
include,software engineer
include,systems engineer
include,platform engineer
include,infrastructure engineer
include,backend engineer
include,frontend engineer
include,full stack
include,devops
include,site reliability
include,sre
include,security engineer
include,network engineer
include,database engineer
include,embedded software
include,embedded systems
include,firmware
include,silicon
include,asic
include,fpga
include,rtl
include,verification engineer
include,hardware engineer
include,cpu
include,computer engineer
include,electrical engineer
include,robotics engineer
include,quant
include,trading
include,quantitative
include,machine learning
include,ml engineer
include,ai engineer
include,ai engineering
include,artificial intelligence
include,ai infrastructure
include,applied scientist
include,research engineer
include,data engineer
include,forward deployed engineer
include,product manager
include,product engineer
include,technical program manager
exclude,senior
exclude,staff
exclude,principal
exclude,sr.
exclude,lead
```

- [ ] **Step 4: Write `scripts/seed_sheets.py`**

```python
# scripts/seed_sheets.py
import csv
import os
import sys

import gspread

CONFIG_HEADER = [
    "Company", "ATS Type", "Board Token or Slug",
    "Consecutive Failures", "Last Error", "Last Success At", "Notes",
]
AGGREGATOR_HEADER = [
    "Type", "Repo or URL", "Consecutive Failures", "Last Error", "Last Success At", "Notes",
]
KEYWORDS_HEADER = ["Type", "Keyword"]


def _get_or_create_tab(spreadsheet, name, header):
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(header))
        ws.append_row(header)
    return ws


def _seed_companies(spreadsheet):
    ws = _get_or_create_tab(spreadsheet, "Config", CONFIG_HEADER)
    with open("data/companies.csv") as f:
        for row in csv.DictReader(f):
            ws.append_row([row["company"], row["ats_type"], row["identifier"], 0, "", "", row["notes"]])


def _seed_aggregators(spreadsheet):
    ws = _get_or_create_tab(spreadsheet, "Aggregators", AGGREGATOR_HEADER)
    with open("data/aggregators.csv") as f:
        for row in csv.DictReader(f):
            ws.append_row([row["source_type"], row["identifier"], 0, "", "", row["notes"]])


def _seed_keywords(spreadsheet):
    ws = _get_or_create_tab(spreadsheet, "Keywords", KEYWORDS_HEADER)
    with open("data/keywords.csv") as f:
        for row in csv.DictReader(f):
            ws.append_row([row["type"], row["keyword"]])


def _ensure_date_found_column(spreadsheet):
    ws = spreadsheet.worksheet("Tracker")
    header = ws.row_values(1)
    if "Date Found" not in header:
        ws.update_cell(1, len(header) + 1, "Date Found")


def main():
    service_account_path = os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    gc = gspread.service_account(filename=service_account_path)
    spreadsheet = gc.open_by_key(sheet_id)

    _ensure_date_found_column(spreadsheet)
    _seed_companies(spreadsheet)
    _seed_aggregators(spreadsheet)
    _seed_keywords(spreadsheet)
    print("Seeding complete.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run against the real Sheet once**

Share your real tracker spreadsheet with the service account's `client_email` (Editor access), then:

```bash
export GOOGLE_SERVICE_ACCOUNT_PATH="/Users/amandachiang/Downloads/School/Projects/job-scraper/service-account.json"
export GOOGLE_SHEET_ID="<your real tracker spreadsheet ID>"
python3 scripts/seed_sheets.py
```

Expected: `Seeding complete.` printed, and `Config`/`Aggregators`/`Keywords` tabs now visible in the real sheet, `Tracker` tab has a `Date Found` header.

- [ ] **Step 6: Commit**

```bash
git add data/ scripts/seed_sheets.py
git commit -m "Add seed data and sheet-seeding script"
```

---

## Task 15: Railway deployment

**Files:**
- Create: `railway.json`
- Create: `Procfile`

**Interfaces:**
- Consumes: `main.py`'s `if __name__ == "__main__"` entry point (Task 13).
- Produces: a running scheduled deployment on Railway.

- [ ] **Step 1: Create `Procfile`**

```
worker: python main.py
```

- [ ] **Step 2: Create `railway.json`**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "restartPolicyType": "NEVER"
  }
}
```

- [ ] **Step 3: Push the repo to GitHub if not already done, then create a Railway project**

```bash
git push origin main
```

In Railway's dashboard: New Project → Deploy from GitHub repo → select `job-scraper`.

- [ ] **Step 4: Set environment variables in Railway**

In the Railway project's Variables tab, add:
- `GOOGLE_SERVICE_ACCOUNT_PATH` — set to a path Railway will have the file at (see Step 5)
- `GOOGLE_SHEET_ID` — your real tracker spreadsheet ID
- `NTFY_TOPIC_URL` — your ntfy.sh topic URL

- [ ] **Step 5: Provide the service account JSON to Railway**

Railway doesn't accept file uploads as env vars directly. Add a `GOOGLE_SERVICE_ACCOUNT_JSON` env var containing the full JSON contents (not a path), and add a small startup shim so `main.py` writes it to disk before running:

```python
# Add to the top of main.py's __main__ block, before constructing SheetsClient:
if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") and not os.path.exists("/tmp/service-account.json"):
    with open("/tmp/service-account.json", "w") as f:
        f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"] = "/tmp/service-account.json"
```

- [ ] **Step 6: Configure the 30-minute schedule**

In Railway's project Settings → Cron Schedule, set `*/30 * * * *` and ensure the service's restart policy is `NEVER` (each cron invocation runs `main.py` to completion once and exits — it is not a long-running always-on process).

- [ ] **Step 7: Trigger one manual run and verify**

Use Railway's "Trigger" button (or wait for the next scheduled tick), then check:
- Railway's deploy logs show the run completed without unhandled exceptions.
- The `Config`/`Aggregators` tabs show updated `Last Success At` timestamps.
- If any postings matched, the `Tracker` tab has new rows and a push notification arrived via ntfy.sh.

- [ ] **Step 8: Commit**

```bash
git add railway.json Procfile main.py
git commit -m "Add Railway deployment configuration"
```

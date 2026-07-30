# Phase 1: Job Scraper, Matcher, Notifier & Tracker — Design

## Goal

Continuously monitor a configurable list of companies' job boards for new internship postings matching the user's target roles (software engineering, systems engineering, quantitative trading, hardware engineering, CPU, AI infrastructure), push a phone notification the moment a match is found, and log it to the user's existing Google Sheets application tracker — with no duplicate notifications or duplicate rows for the same posting.

This is Phase 1 of a three-phase project. Phase 2 (not covered by this spec) will add on-demand AI resume tailoring, triggered from a small web page, with output delivered via Google Drive. Phase 3 (also not covered by this spec) will add scraping of aggregator sites like LinkedIn, which carry meaningfully higher engineering and ToS risk (anti-scraping defenses, likely need for a headless browser + proxies, account-ban risk) and are deferred until Phase 1 + 2 are proven out.

## Context

The user is a rising junior Computer Engineering major targeting Summer 2027 internships. They already maintain a Google Sheets tracker (see column layout below) with ~100+ manually-entered rows spanning big tech, quant trading firms, hardware companies, and AI startups. They want this list preserved and appended to, not replaced.

## Non-goals (Phase 1)

- No AI-based relevance scoring — matching is pure keyword/title filtering.
- No resume tailoring, no Google Drive integration — that's Phase 2.
- No full-time/new-grad postings — internships only.
- No scraping of login-walled/anti-scraping aggregator sites (LinkedIn, Indeed) — that's Phase 3. GitHub-hosted community internship lists ARE in scope for Phase 1 (see Aggregator Sources below) since they carry none of that risk.

## Architecture

A Python service deployed on Railway, invoked on a 30-minute schedule via Railway's built-in cron/scheduled job feature. Each run is a single stateless script execution, pulling postings from two categories of source:

- **Company sources** — one specific company's job board (Greenhouse, Lever, Ashby, or a custom scraper). These postings go through the keyword/level matcher before being considered a match.
- **Aggregator sources** — community-maintained GitHub repos that already curate internship-only listings across many companies (e.g. `github.com/sndsh404/summer-2027-internships`). Per the user's instruction, these are trusted as-is: every posting an aggregator source returns is treated as a match without running it through the keyword/level matcher or checking it against the company config tab. They still go through the same dedup step as everything else.

Run sequence:

1. Read the company list (and each company's ATS type + identifier) from the config tab, and the aggregator source list from the aggregator tab, both in the user's Google Sheet.
2. For each company, fetch current open postings via the appropriate connector (Greenhouse/Lever/Ashby generic API connector, or a custom scraper module for companies without a public ATS API). For each aggregator source, fetch its current listed postings directly.
3. Filter company-source postings through the keyword + level matcher. Aggregator-source postings skip this step entirely and pass through unfiltered.
4. Fetch the full `Link` column from the tracker tab once, build an in-memory set of already-seen posting URLs, and drop any posting (from either category) whose link is already in that set.
5. For each new match: append a row to the tracker tab, then send an ntfy.sh push notification. The Sheet write always happens before the notification, so a mid-run crash never results in a notification for a posting that wasn't actually logged.

State is not held in memory between runs — each run is a fresh process, and the Google Sheet itself (company list + tracker) is the only persistent store. This keeps Phase 1 simple: no database to provision or migrate.

## Components

### `sources/greenhouse.py`
Generic connector. Given a Greenhouse board token, calls Greenhouse's public job board API (`https://boards-api.greenhouse.io/v1/boards/{token}/jobs`) and returns a list of normalized postings: `{title, location, link, posted_date, company}`.

### `sources/lever.py`
Generic connector. Given a Lever company slug, calls Lever's public postings API (`https://api.lever.co/v0/postings/{slug}`) and returns the same normalized posting shape.

### `sources/ashby.py`
Generic connector. Given an Ashby job board name, calls Ashby's public job board API (`https://api.ashbyhq.com/posting-api/job-board/{boardName}`) and returns the same normalized posting shape. Added because several companies already in the user's tracker (Ellipsis Labs, Netic) use Ashby, and it's common among newer AI startups.

### `sources/custom/<company_slug>.py`
One module per company that has no public ATS API and needs direct HTML scraping (e.g. Jane Street, Citadel, Hudson River Trading, D.E. Shaw). Each module exposes a single `fetch() -> list[Posting]` function returning the same normalized shape as the generic connectors. Isolating each company in its own file means one site's HTML changing only breaks that one file, not the whole run.

### `sources/github_list.py`
Generic aggregator connector. Given a GitHub repo (owner/repo), fetches the repo's README via GitHub's raw content API, parses its markdown table of postings (these community lists consistently use a `Company | Role | Location | Link | Date Posted` style table), and returns the same normalized `Posting` shape as company sources. Since these lists are re-fetched in full each run (not diffed against prior commits), "new" detection for aggregator postings relies entirely on the same dedup step as everything else — no special diffing logic needed. No keyword/level filtering is applied to what this returns; every posting it yields is treated as a trusted match per the user's instruction.

### `matcher.py`
Pure function(s), no I/O. Applied only to company-source postings (aggregator-source postings bypass this entirely). Takes a list of normalized postings and the keyword config, returns the subset that:
- Contains at least one include-keyword in the title (case-insensitive). Keyword list (lives in the Google Sheet config tab, editable without a code change) covers a broad "generally interested in tech" scope: `software engineer`, `systems engineer`, `platform engineer`, `infrastructure engineer`, `backend engineer`, `frontend engineer`, `full stack`, `devops`, `site reliability`, `sre`, `security engineer`, `network engineer`, `database engineer`, `embedded software`, `embedded systems`, `firmware`, `silicon`, `asic`, `fpga`, `rtl`, `verification engineer`, `hardware engineer`, `cpu`, `computer engineer`, `electrical engineer`, `robotics engineer`, `quant`, `trading`, `quantitative`, `machine learning`, `ml engineer`, `ai engineer`, `ai engineering`, `artificial intelligence`, `ai infrastructure`, `applied scientist`, `research engineer`, `data engineer`, `forward deployed engineer`, `product manager`, `product engineer`, `technical program manager`.
- Does NOT contain an exclude-keyword: `senior`, `staff`, `principal`, `sr.`, `lead`.
- DOES contain an internship-level indicator: `intern`, `internship`, `co-op`, `coop`.

### `sheets_client.py`
Wraps the Google Sheets API (via `gspread`, using a service account for auth). Responsibilities:
- `read_company_list() -> list[CompanyConfig]` — reads the config tab (Company, ATS Type, Board Token/Slug/Custom).
- `read_aggregator_sources() -> list[AggregatorConfig]` — reads the aggregator tab (Type, URL/Repo, Notes).
- `get_existing_links() -> set[str]` — reads the entire `Link` column of the tracker tab into a Python set.
- `append_row(posting: Posting)` — appends one row to the tracker tab: `Company | Link | Position | Location | (blank Date Applied) | (blank Status) | (blank Referral?) | (blank Notes)`. Column mapping is done by matching the sheet's actual header row by name (not fixed position), so reordering columns in the sheet later doesn't break the writer.

### `notifier.py`
`send(posting: Posting)` — POSTs a plaintext message (`"{company}: {title} ({location})\n{link}"`) to the user's configured ntfy.sh topic URL.

### `main.py`
Orchestrates one full run in the order described in Architecture above. Wraps each company's fetch step in its own try/except: a single company's failure is logged and skipped, not fatal to the run. Tracks consecutive failure counts per company in a `Consecutive Failures` column on the config tab (incremented on failure, reset to 0 on success), and sends one ntfy.sh alert if a company's count reaches 5, so a broken scraper gets noticed without spamming on every run thereafter. This keeps the Google Sheet as the only persistent store, consistent with the rest of Phase 1 — no separate database or local file needed.

## Data flow

```
Google Sheet (config tab: companies + keywords)      Google Sheet (aggregator tab: GitHub lists)
        │                                                       │
        ▼                                                       ▼
  per-company fetch                                    per-aggregator fetch
  (Greenhouse / Lever / Ashby / custom scraper)         (github_list.py)
        │                                                       │
        ▼                                                       │
     matcher (keyword + level filter)                           │  (no filtering — trusted as-is)
        │                                                       │
        └───────────────────┬───────────────────────────────────┘
                             ▼
        dedupe against tracker Sheet's Link column
        (in-memory set, built from one bulk read per run)
                             │
                             ▼
                  for each new match:
                     1. append row to tracker Sheet
                     2. send ntfy.sh notification
```

Dedup keys off the posting's unique `Link` URL, not the company name — a single company can have many concurrent open postings, and each is tracked independently.

## Google Sheet layout

**Tracker tab** (existing, matches the user's current sheet exactly — no columns added or renamed):
`Company | Link | Position | Location | Date Applied | Status | Referral? | Notes`

Auto-added rows populate Company/Link/Position/Location and leave Date Applied/Status/Referral?/Notes blank for the user to fill in as they apply.

**Config tab** (new, added by this project):
`Company | ATS Type (greenhouse / lever / ashby / custom) | Board Token or Slug | Consecutive Failures | Notes`

**Aggregator tab** (new, added by this project):
`Type (github_list) | Repo or URL | Consecutive Failures | Notes`

The aggregator tab is seeded at launch with `sndsh404/summer-2027-internships` (the repo already referenced in the user's existing tracker). The user can add more community internship-list repos to this tab later (e.g. the popular `SimplifyJobs`/`vanshb03`-style "Summer20XX-Internships" repos) without any code change — exact current repo names should be verified at seed-data implementation time rather than assumed here.

The config tab is seeded at launch with:
- The user's existing company list (deduped from their historical tracker), tagged with ATS type where knowable — most map cleanly to Greenhouse, Lever, or Ashby (e.g. Notion, Figma, Robinhood, Datadog, Snowflake, Databricks, Pinterest, Rippling, Astronomer, Mintlify, Aquatic, Schonfeld, Virtu, Flow Traders, Voloridge, PDT Partners, Akuna Capital, Old Mission Capital, Five Rings, Axon, Ellipsis Labs, Netic). This also includes all the "name brand" tech companies already in the user's historical list (Google, Meta, Amazon, Microsoft, Apple, Netflix, NVIDIA, Tesla, Salesforce, Adobe, Oracle, IBM, TikTok, Uber) — most of these use internal/Workday-based ATSs (see below) rather than Greenhouse/Lever/Ashby.
- A handful of custom-scraper targets among the quant firms without public APIs: Jane Street, Citadel, Hudson River Trading, D.E. Shaw.
- A starter set of ~50 additional fast-growing, AI-specialized companies not currently in the user's list, spanning foundation model labs, AI infrastructure/tooling, and applied AI:
  - **Foundation model / applied AI**: Anthropic, Mistral AI, Cohere, Perplexity AI, xAI, Stability AI, Character.AI, Inflection AI, Adept AI, Imbue, Reka AI, ElevenLabs, Runway, Luma AI, Suno, Synthesia, Writer, Sierra, Cresta, Glean, Harvey AI, Abridge, Hippocratic AI.
  - **AI infrastructure / compute / tooling**: Modal, Together AI, Fireworks AI, Baseten, Anyscale, Groq, Cerebras, SambaNova, Lambda (Lambda Labs), Replicate, RunPod, CoreWeave, Crusoe Energy, Tenstorrent, Modular, Weights & Biases, LangChain, LlamaIndex, Pinecone, Weaviate, Qdrant, Hugging Face, Scale AI, Snorkel AI, Labelbox.
  - **AI agents / dev tools / robotics**: Cognition Labs, Anysphere (Cursor), Codeium (Windsurf), Applied Intuition, Waabi, Skild AI, Physical Intelligence.
  - Each is tagged with ATS type (greenhouse/lever/ashby/custom/unsupported) at seed-data implementation time — most fast-growing startups use Greenhouse, Lever, or Ashby, so this list should need very few custom scrapers.
- Large companies with internal/Workday-based ATSs that aren't Greenhouse/Lever/Ashby/custom-scraped in v1 (Google, Meta, Amazon, Microsoft, Apple, Tesla, NVIDIA) are noted in the config tab with ATS Type left blank/`unsupported`, so the user can see they're tracked-but-not-yet-automated, and add custom scrapers for them later without any spec changes.

## Error handling

- Per-company and per-aggregator fetch failures are caught, logged, and skipped — the run continues with remaining companies/aggregators.
- 5 consecutive failed runs for the same company or aggregator source triggers one ntfy.sh alert naming it, so the user knows a scraper needs attention, without repeating the alert every run after that (only re-alerts if it fails 5 more times after a successful run resets the counter). Aggregator sources track their own `Consecutive Failures` column on the aggregator tab, same mechanism as companies.
- Google Sheets API errors (rate limit, auth failure) abort the current run entirely (can't safely dedupe or log without the Sheet) and send one ntfy.sh alert distinguishing this from a per-company scraper failure.

## Testing

- **Connector unit tests** (`sources/greenhouse.py`, `sources/lever.py`, `sources/ashby.py`): run against saved fixture JSON responses (not live network calls), asserting correct normalization into the common `Posting` shape.
- **Custom scraper unit tests**: one fixture HTML file per custom-scraped company, asserting correct extraction.
- **Aggregator unit test** (`sources/github_list.py`): run against a saved fixture README markdown file, asserting correct table parsing into the common `Posting` shape, and asserting the output is passed through to dedup without any matcher call.
- **Matcher unit tests**: a table of sample `(title, expected_match: bool)` pairs covering include-keyword matches across the expanded keyword set (software/systems/platform/hardware/quant/AI/product/FDE roles), exclude-keyword rejections (e.g. "Senior Software Engineer" excluded), and level filtering (e.g. "Software Engineer, Internship" included, "Software Engineer" full-time excluded).
- **Dedup unit test**: given a fake existing `Link` set and a list of postings, asserts only unseen links pass through.
- **Integration test for `sheets_client.append_row`**: against a real test Google Sheet (not the user's actual tracker), asserting the row lands in the correct named columns regardless of column order.

## Deployment

- Railway project with a scheduled job running `main.py` every 30 minutes.
- Secrets (Google service account JSON, ntfy.sh topic, Greenhouse/Lever tokens if any are private) stored as Railway environment variables, never committed to git.
- `requirements.txt`: `gspread`, `google-auth`, `requests`.

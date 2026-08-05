import base64
import os

import notifier
from dedup import filter_new_postings
from matcher import (
    filter_relevant,
    is_acceptable_analyst_role,
    is_acceptable_degree_level,
    is_acceptable_department,
    is_in_season,
    is_us_location,
)
from sheets_client import AGGREGATOR_TAB, CONFIG_TAB, SheetsClient
from sources import ashby, github_list, greenhouse, lever, workable
from sources.custom import amazon, de_shaw, jane_street, spacex

FAILURE_ALERT_THRESHOLD = 5

CUSTOM_SCRAPERS = {
    "jane_street": jane_street.fetch,
    "de_shaw": de_shaw.fetch,
    "amazon": amazon.fetch,
    "spacex": spacex.fetch,
}


def _fetch_company_postings(company_config):
    if company_config.ats_type == "greenhouse":
        return greenhouse.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "lever":
        return lever.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "ashby":
        return ashby.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "workable":
        return workable.fetch(company_config.company, company_config.identifier)
    if company_config.ats_type == "custom":
        return CUSTOM_SCRAPERS[company_config.identifier]()
    return []


def _handle_source_result(sheets, tab_name, source_config, topic_url, error):
    if error is None:
        sheets.record_source_result(tab_name, source_config.row_index, success=True, error=None)
        return
    sheets.record_source_result(
        tab_name,
        source_config.row_index,
        success=False,
        error=str(error),
        current_failures=source_config.consecutive_failures,
    )
    failures = source_config.consecutive_failures + 1
    if failures == FAILURE_ALERT_THRESHOLD:
        name = getattr(source_config, "company", None) or source_config.identifier
        try:
            notifier.send_text(
                topic_url,
                f"⚠️ {name} has failed {FAILURE_ALERT_THRESHOLD} scrape attempts in a row. "
                f"Last error: {error}",
            )
        except Exception as exc:
            print(f"Failed to send failure alert for {name}: {exc}")


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

    eligible_matches = [
        p for p in new_matches
        if is_us_location(p.location)
        and is_acceptable_degree_level(p.title)
        and is_in_season(p.title)
        and is_acceptable_analyst_role(p.title)
        and is_acceptable_department(p.title)
    ]
    for posting in filter_new_postings(eligible_matches, existing_links):
        sheets.append_row(posting)
        try:
            notifier.send_posting(topic_url, posting)
        except Exception as exc:
            print(f"Failed to send notification for {posting.link}: {exc}")


def ensure_service_account_path(env: dict, service_account_path: str = "/tmp/service-account.json") -> None:
    """If GOOGLE_SERVICE_ACCOUNT_JSON_B64 is set, decode it to a file (once) and
    always set GOOGLE_SERVICE_ACCOUNT_PATH to point at it - regardless of whether
    the file already existed from a prior process run in a reused container.
    A container can outlive a single `python main.py` invocation (e.g. Railway
    reusing it across cron ticks), so GOOGLE_SERVICE_ACCOUNT_PATH must be set on
    every run even if the file itself doesn't need to be rewritten.
    """
    b64_value = env.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    if not b64_value:
        return
    if not os.path.exists(service_account_path):
        cleaned = "".join(b64_value.split())
        cleaned += "=" * (-len(cleaned) % 4)
        decoded = base64.b64decode(cleaned)
        with open(service_account_path, "wb") as f:
            f.write(decoded)
    env["GOOGLE_SERVICE_ACCOUNT_PATH"] = service_account_path


if __name__ == "__main__":
    try:
        ensure_service_account_path(os.environ)
        sheets_client = SheetsClient(
            service_account_path=os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"],
            sheet_id=os.environ["GOOGLE_SHEET_ID"],
            tracker_tab=os.environ.get("TRACKER_TAB_NAME", "Tracker"),
        )
        run(sheets_client, topic_url=os.environ["NTFY_TOPIC_URL"])
    except Exception as exc:
        print(f"Unhandled error during run: {exc}")

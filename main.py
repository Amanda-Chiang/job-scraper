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
        tracker_tab=os.environ.get("TRACKER_TAB_NAME", "Tracker"),
    )
    run(sheets_client, topic_url=os.environ["NTFY_TOPIC_URL"])

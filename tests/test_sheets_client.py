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

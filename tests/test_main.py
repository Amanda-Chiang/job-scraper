from unittest.mock import MagicMock, patch

from models import AggregatorConfig, CompanyConfig, KeywordConfig, Posting
import main


def _company(ats_type="greenhouse", failures=0, row_index=2, company="Acme", identifier="acme"):
    return CompanyConfig(
        row_index=row_index, company=company, ats_type=ats_type,
        identifier=identifier, consecutive_failures=failures,
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
    company_a = _company(row_index=2, company="Acme", identifier="acme")
    company_b = _company(row_index=3, company="Beta", identifier="beta")
    posting_b = Posting(
        company="Beta", title="Software Engineer Intern", location="SF",
        link="https://beta.com/1", is_internship=True,
    )
    sheets = _fake_sheets(companies=[company_a, company_b])
    with patch("main.greenhouse.fetch", side_effect=[Exception("network error"), [posting_b]]), \
         patch("main.notifier.send_posting") as mock_notify, patch("main.notifier.send_text"):
        main.run(sheets, topic_url="https://ntfy.sh/test")
    # company_a's failure is recorded...
    sheets.record_source_result.assert_any_call(
        main.CONFIG_TAB, company_a.row_index, success=False, error="network error"
    )
    # ...but company_b is still fetched and its match still gets through, proving the run continued
    sheets.record_source_result.assert_any_call(
        main.CONFIG_TAB, company_b.row_index, success=True, error=None
    )
    mock_notify.assert_called_once_with("https://ntfy.sh/test", posting_b)


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

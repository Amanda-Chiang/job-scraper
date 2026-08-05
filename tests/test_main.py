import os
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
    # both results are batched into one call, covering the failure and the continuation
    sheets.record_source_results.assert_called_once_with(
        main.CONFIG_TAB,
        [
            {"row_index": company_a.row_index, "success": False, "error": "network error", "current_failures": 0},
            {"row_index": company_b.row_index, "success": True, "error": None, "current_failures": 0},
        ],
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
    sheets.record_source_results.assert_not_called()


def test_ensure_service_account_path_sets_path_on_first_run(tmp_path):
    target = str(tmp_path / "service-account.json")
    env = {"GOOGLE_SERVICE_ACCOUNT_JSON_B64": "eyJhIjogMX0="}  # base64 of {"a": 1}
    main.ensure_service_account_path(env, service_account_path=target)
    assert env["GOOGLE_SERVICE_ACCOUNT_PATH"] == target
    assert os.path.exists(target)


def test_ensure_service_account_path_sets_path_even_if_file_already_exists(tmp_path):
    # Regression test: a container reused across process runs (e.g. Railway's
    # cron restarting the same container) can already have the file on disk
    # from a prior run, but GOOGLE_SERVICE_ACCOUNT_PATH must still be set on
    # THIS run's environment, since env vars don't persist across process starts.
    target = str(tmp_path / "service-account.json")
    with open(target, "wb") as f:
        f.write(b'{"a": 1}')
    env = {"GOOGLE_SERVICE_ACCOUNT_JSON_B64": "eyJhIjogMX0="}
    main.ensure_service_account_path(env, service_account_path=target)
    assert env["GOOGLE_SERVICE_ACCOUNT_PATH"] == target


def test_ensure_service_account_path_does_nothing_without_b64_var(tmp_path):
    target = str(tmp_path / "service-account.json")
    env = {}
    main.ensure_service_account_path(env, service_account_path=target)
    assert "GOOGLE_SERVICE_ACCOUNT_PATH" not in env
    assert not os.path.exists(target)

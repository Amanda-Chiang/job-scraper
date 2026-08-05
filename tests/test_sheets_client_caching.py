from unittest.mock import MagicMock, patch

from sheets_client import SheetsClient, CONFIG_TAB


def _client_with_mocked_spreadsheet():
    with patch("sheets_client.gspread.service_account") as mock_service_account:
        mock_gc = MagicMock()
        mock_service_account.return_value = mock_gc
        mock_spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = mock_spreadsheet
        client = SheetsClient(service_account_path="fake.json", sheet_id="fake-id")
        return client, mock_spreadsheet


def test_tab_only_calls_worksheet_once_per_name():
    client, mock_spreadsheet = _client_with_mocked_spreadsheet()
    mock_ws = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_ws

    client._tab(CONFIG_TAB)
    client._tab(CONFIG_TAB)
    client._tab(CONFIG_TAB)

    mock_spreadsheet.worksheet.assert_called_once_with(CONFIG_TAB)


def test_header_only_calls_row_values_once_per_tab():
    client, mock_spreadsheet = _client_with_mocked_spreadsheet()
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = ["Company", "ATS Type"]
    mock_spreadsheet.worksheet.return_value = mock_ws

    client._header(CONFIG_TAB)
    client._header(CONFIG_TAB)
    client._header(CONFIG_TAB)

    mock_ws.row_values.assert_called_once_with(1)


def test_record_source_result_across_many_companies_reuses_cached_tab_and_header():
    # Regression test: this exact pattern (68 companies, each calling
    # record_source_result) was making 2 extra API calls per company
    # (fetch_sheet_metadata + row_values) before caching was added -
    # enough on its own to exceed the Sheets API per-minute quota on
    # every run.
    client, mock_spreadsheet = _client_with_mocked_spreadsheet()
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = [
        "Company", "ATS Type", "Board Token or Slug",
        "Consecutive Failures", "Last Error", "Last Success At", "Notes",
    ]
    mock_spreadsheet.worksheet.return_value = mock_ws

    for row_index in range(2, 70):  # simulate 68 companies
        client.record_source_result(CONFIG_TAB, row_index, success=True, error=None)

    mock_spreadsheet.worksheet.assert_called_once_with(CONFIG_TAB)
    mock_ws.row_values.assert_called_once_with(1)
    assert mock_ws.batch_update.call_count == 68


def test_record_source_results_writes_many_companies_in_a_single_api_call():
    # This is the further optimization beyond per-call caching: instead of
    # one batch_update call per company (68 calls), collapse all of them
    # into ONE batch_update call covering every company's updates at once.
    client, mock_spreadsheet = _client_with_mocked_spreadsheet()
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = [
        "Company", "ATS Type", "Board Token or Slug",
        "Consecutive Failures", "Last Error", "Last Success At", "Notes",
    ]
    mock_spreadsheet.worksheet.return_value = mock_ws

    results = [
        {"row_index": i, "success": True, "error": None, "current_failures": 0}
        for i in range(2, 70)  # 68 companies
    ]
    client.record_source_results(CONFIG_TAB, results)

    mock_spreadsheet.worksheet.assert_called_once_with(CONFIG_TAB)
    mock_ws.row_values.assert_called_once_with(1)
    mock_ws.batch_update.assert_called_once()
    # 2 fields updated (Consecutive Failures + Last Success At) per company
    assert len(mock_ws.batch_update.call_args[0][0]) == 68 * 2


def test_record_source_results_handles_mixed_success_and_failure():
    client, mock_spreadsheet = _client_with_mocked_spreadsheet()
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = [
        "Company", "ATS Type", "Board Token or Slug",
        "Consecutive Failures", "Last Error", "Last Success At", "Notes",
    ]
    mock_spreadsheet.worksheet.return_value = mock_ws

    results = [
        {"row_index": 2, "success": True, "error": None, "current_failures": 0},
        {"row_index": 3, "success": False, "error": "boom", "current_failures": 2},
    ]
    client.record_source_results(CONFIG_TAB, results)

    mock_ws.batch_update.assert_called_once()
    batch = mock_ws.batch_update.call_args[0][0]
    assert len(batch) == 4  # 2 fields each for the success and failure entries

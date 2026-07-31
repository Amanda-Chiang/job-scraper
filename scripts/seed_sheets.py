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
        rows = [
            [row["company"], row["ats_type"], row["identifier"], 0, "", "", row["notes"]]
            for row in csv.DictReader(f)
        ]
    ws.append_rows(rows, value_input_option="RAW")


def _seed_aggregators(spreadsheet):
    ws = _get_or_create_tab(spreadsheet, "Aggregators", AGGREGATOR_HEADER)
    with open("data/aggregators.csv") as f:
        rows = [
            [row["source_type"], row["identifier"], 0, "", "", row["notes"]]
            for row in csv.DictReader(f)
        ]
    ws.append_rows(rows, value_input_option="RAW")


def _seed_keywords(spreadsheet):
    ws = _get_or_create_tab(spreadsheet, "Keywords", KEYWORDS_HEADER)
    with open("data/keywords.csv") as f:
        rows = [[row["type"], row["keyword"]] for row in csv.DictReader(f)]
    ws.append_rows(rows, value_input_option="RAW")


def _ensure_date_found_column(spreadsheet, tracker_tab):
    ws = spreadsheet.worksheet(tracker_tab)
    header = ws.row_values(1)
    if "Date Found" not in header:
        ws.update_cell(1, len(header) + 1, "Date Found")


def main():
    service_account_path = os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    tracker_tab = os.environ.get("TRACKER_TAB_NAME", "Tracker")
    gc = gspread.service_account(filename=service_account_path)
    spreadsheet = gc.open_by_key(sheet_id)

    _ensure_date_found_column(spreadsheet, tracker_tab)
    _seed_companies(spreadsheet)
    _seed_aggregators(spreadsheet)
    _seed_keywords(spreadsheet)
    print("Seeding complete.")


if __name__ == "__main__":
    sys.exit(main())

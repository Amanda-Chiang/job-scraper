from __future__ import annotations

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

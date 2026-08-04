from __future__ import annotations

import datetime
import functools
import time

import gspread

from models import AggregatorConfig, CompanyConfig, KeywordConfig, Posting

TRACKER_TAB = "Tracker"
CONFIG_TAB = "Config"
AGGREGATOR_TAB = "Aggregators"
KEYWORDS_TAB = "Keywords"

QUOTA_RETRY_DELAYS = (5, 15, 30)


def _retry_on_quota_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt, delay in enumerate((0, *QUOTA_RETRY_DELAYS)):
            if delay:
                time.sleep(delay)
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as exc:
                if "429" not in str(exc) or attempt == len(QUOTA_RETRY_DELAYS):
                    raise
    return wrapper


class SheetsClient:
    def __init__(self, service_account_path: str, sheet_id: str, tracker_tab: str = TRACKER_TAB):
        gc = gspread.service_account(filename=service_account_path)
        self._spreadsheet = gc.open_by_key(sheet_id)
        self._tracker_tab = tracker_tab

    def _tab(self, name: str):
        return self._spreadsheet.worksheet(name)

    @_retry_on_quota_error
    def read_company_list(self) -> list[CompanyConfig]:
        ws = self._tab(CONFIG_TAB)
        rows = ws.get_all_records()
        return [
            CompanyConfig(
                row_index=i + 2,
                company=row.get("Company", ""),
                ats_type=row.get("ATS Type", ""),
                identifier=row.get("Board Token or Slug", ""),
                consecutive_failures=int(row.get("Consecutive Failures") or 0),
            )
            for i, row in enumerate(rows)
        ]

    @_retry_on_quota_error
    def read_aggregator_sources(self) -> list[AggregatorConfig]:
        ws = self._tab(AGGREGATOR_TAB)
        rows = ws.get_all_records()
        return [
            AggregatorConfig(
                row_index=i + 2,
                source_type=row.get("Type", ""),
                identifier=row.get("Repo or URL", ""),
                consecutive_failures=int(row.get("Consecutive Failures") or 0),
            )
            for i, row in enumerate(rows)
        ]

    @_retry_on_quota_error
    def read_keywords(self) -> KeywordConfig:
        ws = self._tab(KEYWORDS_TAB)
        rows = ws.get_all_records()
        keyword_rows = [
            (str(r.get("Type", "")).strip().lower(), str(r.get("Keyword", "")).strip())
            for r in rows
        ]
        include = [kw for kw_type, kw in keyword_rows if kw_type == "include" and kw]
        exclude = [kw for kw_type, kw in keyword_rows if kw_type == "exclude" and kw]
        return KeywordConfig(include=include, exclude=exclude)

    @_retry_on_quota_error
    def get_existing_links(self) -> set[str]:
        ws = self._tab(self._tracker_tab)
        header = ws.row_values(1)
        link_col = header.index("Link") + 1
        values = ws.col_values(link_col)[1:]
        return {v for v in values if v}

    @_retry_on_quota_error
    def append_row(self, posting: Posting) -> None:
        ws = self._tab(self._tracker_tab)
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

    @_retry_on_quota_error
    def record_source_result(
        self,
        tab_name: str,
        row_index: int,
        success: bool,
        error: str | None,
        current_failures: int = 0,
    ) -> None:
        ws = self._tab(tab_name)
        header = ws.row_values(1)
        if success:
            updates = {
                "Consecutive Failures": 0,
                "Last Success At": datetime.datetime.utcnow().isoformat(timespec="seconds"),
            }
        else:
            updates = {
                "Consecutive Failures": current_failures + 1,
                "Last Error": (error or "")[:300],
            }
        batch = [
            {"range": gspread.utils.rowcol_to_a1(row_index, header.index(name) + 1), "values": [[value]]}
            for name, value in updates.items()
            if name in header
        ]
        if batch:
            ws.batch_update(batch)

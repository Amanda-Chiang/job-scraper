from dataclasses import dataclass


@dataclass
class Posting:
    company: str
    title: str
    location: str
    link: str
    is_internship: bool


@dataclass
class CompanyConfig:
    row_index: int
    company: str
    ats_type: str  # "greenhouse" | "lever" | "ashby" | "custom" | "unsupported"
    identifier: str
    consecutive_failures: int


@dataclass
class AggregatorConfig:
    row_index: int
    source_type: str  # "github_list"
    identifier: str
    consecutive_failures: int


@dataclass
class KeywordConfig:
    include: list[str]
    exclude: list[str]

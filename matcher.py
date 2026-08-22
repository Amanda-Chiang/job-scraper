import re

from models import Posting, KeywordConfig

LEVEL_PATTERN = re.compile(r"\bintern(ship)?\b|\bco-op\b|\bcoop\b", re.IGNORECASE)

ADVANCED_DEGREE_PATTERN = re.compile(r"\bphd\b|ph\.?d\.?|\bmasters?\b|master's|\bmsc\b|\bms\b", re.IGNORECASE)
BACHELORS_PATTERN = re.compile(r"\bbs\b|\bb\.s\.?|bachelor|undergrad", re.IGNORECASE)

OFF_SEASON_MARKERS = ("spring", "winter", "fall", "autumn")

ANALYST_PATTERN = re.compile(r"\banalyst\b", re.IGNORECASE)
QUANT_PATTERN = re.compile(r"\bquant\b|quantitative", re.IGNORECASE)

IT_ROLE_PATTERN = re.compile(r"\bit\b|information technology|help ?desk|desktop support", re.IGNORECASE)

# Location filtering is deliberately permissive: a posting is dropped only when it
# carries a positive non-US signal. Blank locations, bare "Remote" and "Multiple
# Locations" are kept, since dropping them would silently lose real US roles.

NON_US_COUNTRIES = (
    "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru", "uruguay",
    "costa rica", "panama",
    "united kingdom", "uk", "u.k.", "england", "scotland", "wales", "northern ireland",
    "ireland", "france", "germany", "spain", "portugal", "italy", "netherlands",
    "belgium", "luxembourg", "switzerland", "austria", "denmark", "norway", "sweden",
    "finland", "iceland", "poland", "czech republic", "czechia", "slovakia", "hungary",
    "romania", "bulgaria", "greece", "croatia", "serbia", "ukraine", "estonia",
    "latvia", "lithuania", "russia", "turkey", "cyprus", "malta",
    "israel", "united arab emirates", "uae", "saudi arabia", "qatar", "jordan",
    "egypt", "morocco", "nigeria", "kenya", "ghana", "south africa",
    "india", "pakistan", "bangladesh", "sri lanka", "nepal",
    "china", "hong kong", "macau", "taiwan", "japan", "south korea", "north korea",
    "korea", "singapore", "malaysia", "indonesia", "thailand", "vietnam",
    "philippines", "australia", "new zealand",
)

NON_US_REGIONS = (
    "emea", "emeia", "apac", "apj", "anz", "mena", "latam", "latin america",
    "europe", "european union", "asia", "asia pacific", "middle east", "africa",
    "oceania",
)

# Cities with no notable US namesake - a bare mention is enough to reject.
NON_US_CITIES = (
    "london", "toronto", "vancouver", "montreal", "ottawa", "mississauga",
    "hong kong", "singapore", "tokyo", "osaka", "kyoto", "yokohama", "seoul",
    "beijing", "shanghai", "shenzhen", "guangzhou", "taipei",
    "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "chennai", "kolkata",
    "gurgaon", "gurugram", "noida",
    "tel aviv", "herzliya", "haifa", "dubai", "abu dhabi", "riyadh", "doha",
    "zurich", "munich", "frankfurt", "dusseldorf", "düsseldorf", "stuttgart",
    "cologne", "amsterdam", "rotterdam", "utrecht", "brussels", "copenhagen",
    "stockholm", "oslo", "helsinki", "warsaw", "wroclaw", "krakow", "kraków",
    "prague", "budapest", "bucharest", "sofia", "vilnius", "tallinn", "riga",
    "barcelona", "lisbon", "porto", "turin", "zagreb", "istanbul",
    "cairo", "nairobi", "lagos", "johannesburg", "cape town",
    "kuala lumpur", "jakarta", "manila", "bangkok", "ho chi minh", "hanoi",
    "sao paulo", "são paulo", "rio de janeiro", "buenos aires", "bogota", "bogotá",
    "santiago", "guadalajara", "monterrey", "mexico city",
    "auckland", "brisbane", "perth", "edinburgh", "glasgow", "leeds", "sheffield",
    "cork", "galway",
)

# Cities that also name a US city or town. These reject only when the same segment
# carries no US signal, so "Paris, TX" and "Cambridge, MA" stay.
AMBIGUOUS_NON_US_CITIES = (
    "paris", "berlin", "cambridge", "oxford", "dublin", "manchester", "birmingham",
    "bristol", "belfast", "hamburg", "vienna", "geneva", "milan", "rome", "florence",
    "naples", "madrid", "athens", "moscow", "odessa", "lima", "sydney", "melbourne",
    "wellington", "waterloo", "delhi", "toledo", "versailles",
)

US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho", "illinois",
    "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah",
    "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia", "puerto rico", "united states",
)

US_STATE_ABBREVIATIONS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR",
)

SEGMENT_SPLIT_PATTERN = re.compile(r"[;|/\n]|\band\b|\bor\b", re.IGNORECASE)


def _marker_pattern(markers):
    return re.compile(r"(?<![a-z])(?:%s)(?![a-z])" % "|".join(re.escape(m) for m in sorted(markers, key=len, reverse=True)))


NON_US_PATTERN = _marker_pattern(NON_US_COUNTRIES + NON_US_REGIONS + NON_US_CITIES)
AMBIGUOUS_NON_US_PATTERN = _marker_pattern(AMBIGUOUS_NON_US_CITIES)
US_NAME_PATTERN = _marker_pattern(US_STATE_NAMES + ("usa", "u.s.", "u.s.a."))
# Abbreviations are matched case-sensitively so English words ("in", "or", "me")
# are not mistaken for state codes.
US_ABBREVIATION_PATTERN = re.compile(r"\b(?:%s|US)\b" % "|".join(US_STATE_ABBREVIATIONS))


def _has_us_signal(segment: str) -> bool:
    return bool(US_NAME_PATTERN.search(segment.lower())) or bool(US_ABBREVIATION_PATTERN.search(segment))


def _is_non_us_segment(segment: str) -> bool:
    lowered = segment.lower()
    if NON_US_PATTERN.search(lowered):
        return True
    return bool(AMBIGUOUS_NON_US_PATTERN.search(lowered)) and not _has_us_signal(segment)


def is_us_location(location: str) -> bool:
    """True unless the location carries a positive non-US signal.

    Ambiguous values (blank, "Remote", "Multiple Locations") are treated as US so
    that US roles from sources with sparse location data are not dropped.
    """
    segments = [s for s in SEGMENT_SPLIT_PATTERN.split(location) if s.strip()]
    return not any(_is_non_us_segment(segment) for segment in segments)


def is_acceptable_degree_level(title: str) -> bool:
    requires_advanced_degree_only = bool(ADVANCED_DEGREE_PATTERN.search(title)) and not BACHELORS_PATTERN.search(title)
    return not requires_advanced_degree_only


def is_in_season(title: str) -> bool:
    lower = title.lower()
    has_off_season = any(marker in lower for marker in OFF_SEASON_MARKERS)
    has_summer = "summer" in lower
    return not (has_off_season and not has_summer)


def is_acceptable_analyst_role(title: str) -> bool:
    is_analyst_role = bool(ANALYST_PATTERN.search(title))
    is_quant_role = bool(QUANT_PATTERN.search(title))
    return not is_analyst_role or is_quant_role


def is_acceptable_department(title: str) -> bool:
    return not IT_ROLE_PATTERN.search(title)


def is_acceptable_company(company: str, excluded_companies: list[str]) -> bool:
    return company.strip().lower() not in {c.strip().lower() for c in excluded_companies}


def is_relevant(posting: Posting, keywords: KeywordConfig) -> bool:
    title = posting.title.lower()
    if not any(kw.lower() in title for kw in keywords.include):
        return False
    if any(kw.lower() in title for kw in keywords.exclude):
        return False
    if posting.is_internship:
        return True
    return bool(LEVEL_PATTERN.search(posting.title))


def filter_relevant(postings: list[Posting], keywords: KeywordConfig) -> list[Posting]:
    return [p for p in postings if is_relevant(p, keywords)]

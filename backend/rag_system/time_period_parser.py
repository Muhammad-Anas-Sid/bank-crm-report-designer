"""
Time Period Parser — converts natural language time expressions to date ranges.

This module is the single source of truth for interpreting temporal expressions
in the banking report system. It handles quarters, years, months, relative
periods ("last 30 days"), and compound expressions ("Q3 2025").

Used by:
- RAG Orchestrator (to normalize time_range from intent agent)
- SQL Connector (as a safety net when time_range is missing)
- File Connector (to filter file-based data by date)
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Month mappings for natural language parsing
MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Quarter-to-month mapping
QUARTER_MONTHS = {
    1: (1, 3),   # Q1: Jan 1 – Mar 31
    2: (4, 6),   # Q2: Apr 1 – Jun 30
    3: (7, 9),   # Q3: Jul 1 – Sep 30
    4: (10, 12), # Q4: Oct 1 – Dec 31
}

# Number of days in each month (non-leap year fallback)
MONTH_LAST_DAY = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


def _last_day_of_month(year: int, month: int) -> int:
    """Get the last day of a given month/year (handles leap years)."""
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        return 28
    return MONTH_LAST_DAY.get(month, 30)


def parse_time_period(text: str, reference_date: Optional[datetime] = None) -> Optional[Dict[str, str]]:
    """
    Convert a natural language time period to a date range.

    Args:
        text: Natural language time period (e.g., "Q3 2025", "last month", "January 2026")
        reference_date: Reference datetime for relative calculations (defaults to now)

    Returns:
        {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or None if not parseable
    """
    if not text or not isinstance(text, str):
        return None

    ref = reference_date or datetime.now()
    text_clean = text.strip().lower()

    # Try each parser in order of specificity
    result = (
        _parse_quarter(text_clean, ref)
        or _parse_half_year(text_clean, ref)
        or _parse_full_year(text_clean, ref)
        or _parse_month_year(text_clean, ref)
        or _parse_relative_period(text_clean, ref)
        or _parse_ytd_mtd(text_clean, ref)
        or _parse_date_range(text_clean)
    )

    if result:
        logger.info(f"Parsed time period '{text}' → {result['start']} to {result['end']}")
    return result


def _parse_quarter(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse quarter expressions: 'Q3 2025', 'q1', 'first quarter 2026', 'last quarter'."""
    # "last quarter" / "previous quarter"
    if re.search(r"\b(last|previous|prior)\s+quarter\b", text):
        current_q = (ref.month - 1) // 3 + 1
        if current_q == 1:
            year = ref.year - 1
            quarter = 4
        else:
            year = ref.year
            quarter = current_q - 1
        return _quarter_range(quarter, year)

    # "this quarter" / "current quarter"
    if re.search(r"\b(this|current)\s+quarter\b", text):
        quarter = (ref.month - 1) // 3 + 1
        return _quarter_range(quarter, ref.year)

    # "next quarter"
    if re.search(r"\bnext\s+quarter\b", text):
        current_q = (ref.month - 1) // 3 + 1
        if current_q == 4:
            return _quarter_range(1, ref.year + 1)
        return _quarter_range(current_q + 1, ref.year)

    # "Q3 2025", "Q1", "q2 2026"
    match = re.search(r"\bq([1-4])\s*(\d{4})?\b", text)
    if match:
        quarter = int(match.group(1))
        year = int(match.group(2)) if match.group(2) else ref.year
        return _quarter_range(quarter, year)

    # "first/second/third/fourth quarter [2025]"
    ordinal_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
    for word, q in ordinal_map.items():
        match = re.search(rf"\b{word}\s+quarter\s*(\d{{4}})?\b", text)
        if match:
            year = int(match.group(1)) if match.group(1) else ref.year
            return _quarter_range(q, year)

    return None


def _quarter_range(quarter: int, year: int) -> Dict[str, str]:
    """Convert a quarter number and year to a date range."""
    start_month, end_month = QUARTER_MONTHS[quarter]
    end_day = _last_day_of_month(year, end_month)
    return {
        "start": f"{year}-{start_month:02d}-01",
        "end": f"{year}-{end_month:02d}-{end_day:02d}",
    }


def _parse_half_year(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse half-year expressions: 'H1 2025', 'first half 2026'."""
    match = re.search(r"\bh([12])\s*(\d{4})?\b", text)
    if match:
        half = int(match.group(1))
        year = int(match.group(2)) if match.group(2) else ref.year
        if half == 1:
            return {"start": f"{year}-01-01", "end": f"{year}-06-30"}
        else:
            return {"start": f"{year}-07-01", "end": f"{year}-12-31"}

    for pattern, half_num in [("first half", 1), ("second half", 2)]:
        match = re.search(rf"\b{pattern}\s*(\d{{4}})?\b", text)
        if match:
            year = int(match.group(1)) if match.group(1) else ref.year
            if half_num == 1:
                return {"start": f"{year}-01-01", "end": f"{year}-06-30"}
            else:
                return {"start": f"{year}-07-01", "end": f"{year}-12-31"}

    return None


def _parse_full_year(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse standalone year: '2025', 'year 2025'."""
    # Must be a standalone 4-digit year (not part of a date like 2025-01-01)
    match = re.match(r"^(?:year\s+)?(\d{4})$", text.strip())
    if match:
        year = int(match.group(1))
        if 2000 <= year <= 2100:
            return {"start": f"{year}-01-01", "end": f"{year}-12-31"}
    return None


def _parse_month_year(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse month expressions: 'January 2025', 'Feb', 'March'."""
    for month_name, month_num in MONTH_NAMES.items():
        # "January 2025", "Jan 2025"
        match = re.search(rf"\b{month_name}\s+(\d{{4}})\b", text)
        if match:
            year = int(match.group(1))
            last_day = _last_day_of_month(year, month_num)
            return {
                "start": f"{year}-{month_num:02d}-01",
                "end": f"{year}-{month_num:02d}-{last_day:02d}",
            }

        # Standalone month name ("January", "Feb") — assume current or recent year
        if re.search(rf"\b{month_name}\b", text) and not re.search(r"\d{4}", text):
            year = ref.year
            # If the month is in the future, use previous year
            if month_num > ref.month:
                year -= 1
            last_day = _last_day_of_month(year, month_num)
            return {
                "start": f"{year}-{month_num:02d}-01",
                "end": f"{year}-{month_num:02d}-{last_day:02d}",
            }

    return None


def _parse_relative_period(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse relative periods: 'last 30 days', 'past 3 months', 'last week'."""
    # "last X days/weeks/months/years"
    match = re.search(r"\b(?:last|past|previous)\s+(\d+)\s+(day|week|month|year)s?\b", text)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        return _relative_delta(ref, count, unit)

    # "last day/week/month/year" (singular, implying 1)
    match = re.search(r"\b(?:last|past|previous)\s+(day|week|month|year)\b", text)
    if match:
        unit = match.group(1)
        return _relative_delta(ref, 1, unit)

    # "this week/month/year"
    if re.search(r"\bthis\s+week\b", text):
        start = ref - timedelta(days=ref.weekday())  # Monday
        return {"start": start.strftime("%Y-%m-%d"), "end": ref.strftime("%Y-%m-%d")}
    if re.search(r"\bthis\s+month\b", text):
        return {"start": f"{ref.year}-{ref.month:02d}-01", "end": ref.strftime("%Y-%m-%d")}
    if re.search(r"\bthis\s+year\b", text):
        return {"start": f"{ref.year}-01-01", "end": ref.strftime("%Y-%m-%d")}

    # "today"
    if re.search(r"\btoday\b", text):
        return {"start": ref.strftime("%Y-%m-%d"), "end": ref.strftime("%Y-%m-%d")}

    # "yesterday"
    if re.search(r"\byesterday\b", text):
        yesterday = ref - timedelta(days=1)
        return {"start": yesterday.strftime("%Y-%m-%d"), "end": yesterday.strftime("%Y-%m-%d")}

    return None


def _relative_delta(ref: datetime, count: int, unit: str) -> Dict[str, str]:
    """Calculate a date range going back from ref by count units."""
    if unit == "day":
        start = ref - timedelta(days=count)
    elif unit == "week":
        start = ref - timedelta(weeks=count)
    elif unit == "month":
        # Approximate: go back count months
        month = ref.month - count
        year = ref.year
        while month <= 0:
            month += 12
            year -= 1
        day = min(ref.day, _last_day_of_month(year, month))
        start = ref.replace(year=year, month=month, day=day)
    elif unit == "year":
        start = ref.replace(year=ref.year - count)
    else:
        start = ref - timedelta(days=30 * count)

    return {"start": start.strftime("%Y-%m-%d"), "end": ref.strftime("%Y-%m-%d")}


def _parse_ytd_mtd(text: str, ref: datetime) -> Optional[Dict[str, str]]:
    """Parse YTD (Year-to-Date) and MTD (Month-to-Date)."""
    if re.search(r"\b(ytd|year[\s-]to[\s-]date)\b", text):
        return {"start": f"{ref.year}-01-01", "end": ref.strftime("%Y-%m-%d")}
    if re.search(r"\b(mtd|month[\s-]to[\s-]date)\b", text):
        return {"start": f"{ref.year}-{ref.month:02d}-01", "end": ref.strftime("%Y-%m-%d")}
    return None


def _parse_date_range(text: str) -> Optional[Dict[str, str]]:
    """Parse explicit date ranges: '2025-01-01 to 2025-03-31'."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|through|until|-)\s*(\d{4}-\d{2}-\d{2})", text)
    if match:
        return {"start": match.group(1), "end": match.group(2)}
    return None


def extract_time_keywords(text: str) -> list:
    """
    Extract time-related keywords from text for file search enhancement.

    Returns a list of keywords like ["Q3", "2025", "July", "September"]
    that can be used to improve file connector search relevance.
    """
    keywords = []

    # Extract quarters
    q_match = re.findall(r"\bq[1-4]\b", text.lower())
    keywords.extend([q.upper() for q in q_match])

    # Extract years
    year_matches = re.findall(r"\b(20\d{2})\b", text)
    keywords.extend(year_matches)

    # Extract month names
    for month_name in MONTH_NAMES:
        if re.search(rf"\b{month_name}\b", text.lower()):
            keywords.append(month_name.capitalize())

    # Extract relative terms
    for term in ["last", "previous", "recent", "current", "this", "ytd"]:
        if term in text.lower():
            keywords.append(term)

    return list(dict.fromkeys(keywords))  # Deduplicate while preserving order


def describe_time_range(time_range: Dict[str, str]) -> str:
    """
    Generate a human-readable description of a time range for report metadata.

    Example: "Q3 2025 (July 1 – September 30, 2025)"
    """
    if not time_range or not time_range.get("start") or not time_range.get("end"):
        return "All available dates"

    try:
        start = datetime.strptime(time_range["start"], "%Y-%m-%d")
        end = datetime.strptime(time_range["end"], "%Y-%m-%d")
    except (ValueError, TypeError):
        return f"{time_range.get('start', '?')} to {time_range.get('end', '?')}"

    # Check if it's a full quarter
    if start.day == 1:
        q_start = (start.month - 1) // 3 + 1
        q_end_month = QUARTER_MONTHS.get(q_start, (0, 0))[1]
        if q_end_month == end.month and end.day == _last_day_of_month(end.year, end.month):
            if start.year == end.year:
                return f"Q{q_start} {start.year} ({start.strftime('%B %d')} – {end.strftime('%B %d, %Y')})"

    # Check if it's a full year
    if start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31 and start.year == end.year:
        return f"Year {start.year} (January 1 – December 31, {start.year})"

    # Check if it's a full month
    if start.day == 1 and end.day == _last_day_of_month(end.year, end.month) and start.month == end.month:
        return f"{start.strftime('%B %Y')} ({start.strftime('%B %d')} – {end.strftime('%B %d, %Y')})"

    # Generic range
    return f"{start.strftime('%B %d, %Y')} to {end.strftime('%B %d, %Y')}"

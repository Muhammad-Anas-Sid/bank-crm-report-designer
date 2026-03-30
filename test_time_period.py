import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.rag_system.time_period_parser import parse_time_period, describe_time_range
from datetime import datetime

test_cases = [
    "Q3 2025",
    "q1",
    "full year 2024",
    "last 30 days",
    "past 3 months",
    "this month",
    "last quarter",
    "January 2025",
    "Jan 2025",
    "ytd"
]

ref_date = datetime(2026, 3, 5)

for tc in test_cases:
    res = parse_time_period(tc, reference_date=ref_date)
    desc = describe_time_range(res)
    print(f"'{tc}' -> {res} | description: {desc}")

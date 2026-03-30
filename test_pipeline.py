"""
Test Pipeline — verifies the full RAG-based report generation pipeline.

Tests the flow: IntentAgent → RAG Orchestrator → AnalyticsAgent → Output
"""

import os
import sys
import json
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.report_planner import ReportPlanner

# Configure logging
logging.getLogger('backend.agents.report_planner').setLevel(logging.INFO)
logging.getLogger('backend.rag_system').setLevel(logging.INFO)


def run_test(prompt):
    print(f"\n{'='*60}")
    print(f"TESTING PROMPT: {prompt}")
    print(f"{'='*60}")

    planner = ReportPlanner()
    context = {"username": "test_user", "user_id": 1}

    try:
        result = planner.generate_report(prompt, context)

        status = result.get("status", "unknown")
        print(f"\nSTATUS: {status}")

        if status == "success":
            plan = result.get("report_plan", {})
            meta = result.get("execution_metadata", {})

            print(f"REPORT TITLE: {plan.get('report_title')}")
            print(f"INTENT TYPE: {plan.get('intent_type')}")
            print(f"DOMAIN: {plan.get('domain')}")
            print(f"ENTITIES: {plan.get('entities')}")
            print(f"DATA REQUIREMENTS: {json.dumps(plan.get('data_requirements', {}), indent=2)}")
            print(f"EXECUTION SOURCE: {meta.get('source')}")
            print(f"SOURCES USED: {meta.get('sources_used')}")
            print(f"SOURCE BREAKDOWN: {meta.get('source_breakdown')}")
            print(f"DATA ROWS: {result.get('total_rows')}")
            print(f"PIPELINE TIME: {meta.get('time', 0):.2f}s")
            print(f"PIPELINE LOG: {meta.get('pipeline_log')}")

            preview = result.get("data_preview", [])
            if preview:
                print(f"\nDATA PREVIEW (first row):")
                print(json.dumps(preview[0], indent=2, default=str))

            insights = result.get("insights", "")
            if insights:
                print(f"\nINSIGHTS (first 300 chars):")
                print(insights[:300] + "..." if len(insights) > 300 else insights)

            if result.get("download_link"):
                print(f"\nDOWNLOAD LINK: {result['download_link']}")

        elif status in ("clarify", "chat"):
            print(f"MESSAGE: {result.get('message')}")

        elif status == "error":
            print(f"ERROR: {result.get('message') or result.get('reason')}")

        else:
            print(f"REASON: {result.get('reason') or result.get('message')}")

    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import time

    prompts = [
        "Show me total balance by account type",
        # "how many customers do we have?",
        # "show me top 10 card transactions",
        # "Q1 credit card transactions by merchant category",
    ]

    for p in prompts:
        run_test(p)
        time.sleep(10)  # Rate limit safety

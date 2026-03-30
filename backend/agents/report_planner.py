"""
Report Planner — orchestrates the full AI processing pipeline.

The pipeline is PURELY RAG-based:
  IntentAgent → RAG Orchestrator → PDF

The RAG system handles ALL data-fetching, query-building, 
and now generates both the data-only report and the analysis insights.
"""

import time
import logging
from backend.agents.intent_agent import IntentAgent
from backend.rag_system.rag_orchestrator import RAGOrchestrator
from backend.reports.document_service import DocumentService
from backend.audit.audit_service import AuditService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportPlanner:
    """Orchestrates the full report generation pipeline using RAG exclusively."""

    def __init__(self):
        self.intent_agent = IntentAgent()
        self.rag_orchestrator = RAGOrchestrator()
        self.document_service = DocumentService()

    def generate_report(self, user_prompt: str, user_context: dict, history: list = None) -> dict:
        """
        Executes the report pipeline:
        1. IntentAgent extracts structured data requirements
        2. RAG Orchestrator retrieves real data AND generates dual outputs:
           - data_only_report (for PDF)
           - analysis_response (for Chat)
        3. DocumentService generates PDF using the data-only report
        """
        start_time = time.time()
        pipeline_log = []

        try:
            # ── Step 1: LLM Intent Extraction ──────────────────────────
            logger.info(f"[ReportPlanner] Step 1 — Extracting intent for: {user_prompt}")
            report_plan = self.intent_agent.generate_report_plan(user_prompt, history=history)

            if not report_plan or "error" in report_plan:
                return {
                    "status": "error",
                    "message": report_plan.get("error", "Intent extraction failed."),
                }

            # Intent Routing (Clarify / Chat)
            if report_plan.get("intent_type") in ("clarify", "chat"):
                return {
                    "status": report_plan["intent_type"],
                    "message": report_plan.get("intent", "Please clarify your request."),
                    "suggested_questions": report_plan.get("suggested_questions", []),
                    "report_plan": report_plan,
                }

            pipeline_log.append(f"Intent resolved: {report_plan.get('report_title')}")

            # ── Step 2: RAG Orchestrator — retrieval & generation ──────
            logger.info("[ReportPlanner] Step 2 — RAG Orchestrator processing...")
            rag_result = self.rag_orchestrator.orchestrate(report_plan)

            if rag_result.get("error"):
                return {
                    "status": "error",
                    "message": f"Data retrieval failed: {rag_result['error']}",
                    "report_plan": report_plan,
                }

            df = rag_result.get("dataframe")
            if df is None or df.empty:
                return {
                    "status": "error",
                    "message": "No data found matching your report criteria. Try a different query.",
                    "report_plan": report_plan,
                }

            # Extract dual outputs
            data_only_report = rag_result.get("data_only_report", "")
            analysis_response = rag_result.get("analysis_response", "Report generated successfully.")
            
            pipeline_log.append(f"Retrieved {len(df)} rows and generated analysis.")

            # ── Step 3: Document generation — PDF ──────────────────────
            # We pass the data_only_report here so the PDF has NO AI analysis
            logger.info("[ReportPlanner] Step 3 — Generating PDF report...")
            filename = self.document_service.generate_pdf(
                report_plan, df, data_only_report, user_context
            )

            total_time = time.time() - start_time
            logger.info(f"[ReportPlanner] Pipeline finished in {total_time:.2f}s")

            # Audit logging
            AuditService.log_report_generation(
                user_context, user_prompt, len(df), filename
            )

            return {
                "status": "success",
                "report_plan": report_plan,
                "data_preview": df.head(5).to_dict(orient="records") if not df.empty else [],
                "total_rows": len(df),
                "insights": analysis_response, # To be shown in chat
                "download_link": f"/api/reports/download/{filename}",
                "sources_used": rag_result.get("sources_used", []),
                "source_breakdown": rag_result.get("source_breakdown", {}),
                "execution_metadata": {
                    "source": "RAG",
                    "time": total_time,
                    "pipeline_log": pipeline_log,
                },
            }

        except Exception as e:
            logger.error(f"[ReportPlanner] Pipeline Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": "Internal error during report generation.",
                "reason": str(e),
            }

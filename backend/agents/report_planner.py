"""
Report Planner — orchestrates the full AI processing pipeline.

User Chat → Intent Agent → Report Plan Generator → LLM JSON Structured Output
→ Query Builder Validation → SQL Generator → Data Engine → Analytics Agent
→ Document Generator → Generated Document Preview
"""

from backend.agents.intent_agent import IntentAgent
from backend.agents.analytics_agent import AnalyticsAgent
from backend.query_builder.query_builder import QueryBuilder
from backend.services.data_engine import DataEngine
from backend.reports.document_service import DocumentService
from backend.audit.audit_service import AuditService
from backend.chat.chat_service import ChatService


class ReportPlanner:
    """Orchestrates the full report generation pipeline."""

    def __init__(self):
        self.intent_agent = IntentAgent()
        self.query_builder = QueryBuilder()
        self.data_engine = DataEngine()
        self.analytics_agent = AnalyticsAgent()
        self.document_service = DocumentService()

    def generate_report(self, user_prompt: str, user_context: dict) -> dict:
        """
        Full pipeline execution:
        1. Intent Agent → Report Plan (JSON)
        2. Query Builder → Validated SQL
        3. Data Engine → Pandas DataFrame
        4. Analytics Agent → Insights
        5. Document Generator → PDF

        Returns dict with report_plan, data_preview, insights, download_link.
        Raises ValueError on failure.
        """
        # Step 1: Generate report plan
        report_plan = self.intent_agent.generate_report_plan(user_prompt)

        if not report_plan:
            raise ValueError("Failed to generate report plan from LLM.")

        if isinstance(report_plan, dict) and "error" in report_plan:
            return {"status": "error", "message": report_plan["error"]}

        # Step 2: Generate and validate SQL
        schema = ChatService.get_schema_entities()
        
        # Priority 1: LLM-generated SQL
        sql_query = report_plan.get("generated_sql")
        
        if sql_query:
            print("Using LLM-generated SQL.")
            # Still validate for safety
            from backend.query_builder.sql_validator import SqlValidator
            validator = SqlValidator()
            is_valid, error = validator.validate(sql_query)
            if not is_valid:
                print(f"LLM SQL validation failed: {error}. Falling back to Query Builder.")
                sql_query = self.query_builder.generate_sql(report_plan)
        else:
            # Priority 2: Query Builder fallback
            print("No LLM SQL provided. Using Query Builder fallback.")
            sql_query = self.query_builder.generate_sql(report_plan)

        # Audit the SQL
        AuditService.log_sql_execution(user_context, sql_query)

        # Step 3: Execute SQL → DataFrame
        df = self.data_engine.execute_query(sql_query, schema=schema)

        # Step 4: Generate analytics insights
        analytics_prompt = report_plan.get("analytics_prompt", "Provide general insights on this data.")
        insights = self.analytics_agent.generate_insights(df, analytics_prompt)

        # Step 5: Generate PDF document
        username = user_context.get("username", "unknown")
        filename = self.document_service.generate_pdf(
            report_plan, df, insights, user_context
        )

        # Audit the report generation
        AuditService.log_report_generation(user_context, user_prompt, len(df))

        # Build response
        data_preview = []
        if not df.empty:
            # Safe NaN handling
            safe_df = df.where(df.notna(), None)
            data_preview = safe_df.head(5).to_dict(orient="records")

        return {
            "status": "success",
            "report_plan": report_plan,
            "data_preview": data_preview,
            "total_rows": len(df),
            "insights": insights,
            "download_link": f"/api/reports/download/{filename}",
        }

"""
RAG Orchestrator — the heart of the retrieval-augmented generation system.

This replaces the old query_builder approach entirely. Instead of having the LLM
generate SQL queries, the orchestrator:
1. Takes the report plan from the intent agent
2. Performs semantic understanding of what data is needed
3. Routes to appropriate data sources using vector search
4. Calls connectors to retrieve actual data
5. Aggregates results from multiple sources
6. Calls the LLM twice: 
   - Once for a clean, data-only report (tables/numbers)
   - Once for a conversational analysis (insights for chat)
7. Returns both outputs, data, and metadata
"""

import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from groq import Groq

from backend.config.settings import Config
from backend.rag_system.knowledge_base import KnowledgeBase
from backend.rag_system.embeddings_manager import EmbeddingsManager
from backend.rag_system.connectors.sql_connector import SQLConnector
from backend.rag_system.connectors.file_connector import FileConnector
from backend.rag_system.data_aggregator import DataAggregator
from backend.rag_system.time_period_parser import (
    parse_time_period,
    extract_time_keywords,
    describe_time_range,
)

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """Main orchestration engine for RAG-based report generation."""

    def __init__(self):
        logger.info("Initializing RAG Orchestrator...")
        self.knowledge_base = KnowledgeBase()
        self.embeddings = EmbeddingsManager(self.knowledge_base)
        self.sql_connector = SQLConnector(self.knowledge_base)
        self.file_connector = FileConnector()
        self.aggregator = DataAggregator()

        groq_key = Config.GROQ_API_KEY
        if groq_key:
            self.llm_client = Groq(api_key=groq_key)
            self.llm_model = "llama-3.3-70b-versatile"
        else:
            self.llm_client = None
            logger.warning("No LLM API key — narrative generation will be skipped.")

    def orchestrate(self, report_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point: execute the full RAG pipeline."""
        start_time = time.time()
        pipeline_log = []

        try:
            # Step 1: Understand what data the report needs
            logger.info("Step 1: Understanding data requirements...")
            requirements = self._understand_requirements(report_plan)
            pipeline_log.append(f"Requirements: {requirements.get('tables', [])}")

            # Step 2: Route to data sources
            logger.info("Step 2: Routing to data sources...")
            routing = self._route_to_sources(report_plan, requirements)

            # Step 3: Retrieve data
            logger.info("Step 3: Retrieving data...")
            sql_data, file_data = self._retrieve_data(routing, requirements)

            # Step 3.5: Safety-net post-filter by time range
            time_range = requirements.get("time_range", {})
            time_description = describe_time_range(time_range) if time_range else "All available dates"

            if time_range:
                pipeline_log.append(f"Time filter: {time_description}")
                if not sql_data.empty:
                    sql_data = SQLConnector.post_filter_by_time(sql_data, time_range)
                if not file_data.empty:
                    file_data = SQLConnector.post_filter_by_time(file_data, time_range)

            # Step 4: Aggregate results
            logger.info("Step 4: Aggregating results...")
            aggregated = self.aggregator.aggregate(
                sql_data, file_data, time_period=time_description
            )
            combined_df = aggregated["combined_data"]

            # Step 5: Generate data-only report and analysis
            logger.info("Step 5: Generating outputs...")
            data_report = self._generate_data_only_report(report_plan, aggregated["context_for_llm"])
            analysis = self._generate_analysis(report_plan, aggregated["context_for_llm"])

            elapsed = time.time() - start_time

            return {
                "dataframe": combined_df,
                "data_only_report": data_report,
                "analysis_response": analysis,
                "sources_used": aggregated["sources_used"],
                "source_breakdown": aggregated["source_breakdown"],
                "total_rows": aggregated["total_rows"],
                "time_period": time_description,
                "time_range": time_range,
                "metadata": {
                    "pipeline_time": elapsed,
                    "pipeline_log": pipeline_log,
                    "routing": routing,
                    "requirements": requirements,
                },
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"RAG orchestration failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "dataframe": pd.DataFrame(),
                "data_only_report": "",
                "analysis_response": f"Data retrieval failed: {str(e)}",
                "sources_used": [],
                "source_breakdown": {},
                "total_rows": 0,
                "error": str(e),
                "metadata": {"pipeline_time": elapsed, "pipeline_log": pipeline_log},
            }

    def _generate_data_only_report(self, report_plan: Dict[str, Any], context: str) -> str:
        """First LLM call: Generate a clean, data-only report (tables and metrics)."""
        if not self.llm_client:
            return "Narrative generation skipped (no API key)."

        prompt = f"""
You are a data presentation expert for a top-tier bank. 
Your task is to take the retrieved data below and format it into a clean, professional report.

STRICT RULES:
1. ONLY use the retrieved data.
2. DO NOT add any analysis, trends, interpretations, or recommendations.
3. Use markdown tables to organize the data.
4. Include a section for 'Key Figures' (numbers only, no narrative).
5. DO NOT invent or hallucinate any numbers.
6. If data is missing for a requested field, simply state 'Data not available in retrieved set'.
7. NO subjectiveness or forecasting.

REPORT TITLE: {report_plan.get('report_title', 'Data Report')}
INTENT: {report_plan.get('query_intent', 'N/A')}

DATA:
{context}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a data presentation expert. Format retrieved data into clean tables. Do not add analysis."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Data-only report generation failed: {e}")
            return "Failed to generate structured data report."

    def _generate_analysis(self, report_plan: Dict[str, Any], context: str) -> str:
        """Second LLM call: Generate a conversational analysis for the chat window."""
        if not self.llm_client:
            return "Analysis generation skipped (no API key)."

        prompt = f"""
You are a senior banking analyst. 
Based on the retrieved data below, provide a conversational analysis for the user.

YOUR RESPONSE MUST INCLUDE:
- A brief greeting/intro regarding the generated report.
- KEY INSIGHTS: Bullet points explaining what the data means (trends, comparisons).
- A final summary or recommendation if applicable.

Guidelines:
- Professional but conversational tone.
- Be concise (max 200 words).
- ONLY interpret the real data provided below.

REPORT: {report_plan.get('report_title', 'Report')}
DATA:
{context}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a senior banking analyst providing conversational insights."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=600,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Analysis generation failed: {e}")
            return "I encountered an error while trying to analyze the insights."

    def _understand_requirements(self, report_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Step 1: Extract structured data requirements from the report plan."""
        data_reqs = report_plan.get("data_requirements", {})
        tables = data_reqs.get("tables", [])
        columns = data_reqs.get("columns", [])

        if not tables:
            tables = report_plan.get("entities", [])
        
        filters = []
        raw_filters = report_plan.get("filters", [])
        for f in raw_filters:
            if isinstance(f, str):
                parts = f.split()
                if len(parts) >= 3:
                    filters.append({
                        "column": parts[0].split(".")[-1],
                        "operator": parts[1],
                        "value": " ".join(parts[2:]).strip("'\""),
                    })
            elif isinstance(f, dict):
                filters.append(f)

        filter_str = data_reqs.get("filters", "")
        if isinstance(filter_str, str) and filter_str and not filters:
            for clause in filter_str.split(" AND "):
                clause = clause.strip()
                if not clause: continue
                for op in [">=", "<=", "!=", "=", ">", "<", "LIKE", "ILIKE"]:
                    if f" {op} " in clause or f" {op.lower()} " in clause:
                        parts = clause.split(f" {op} ", 1)
                        if len(parts) == 2:
                            col = parts[0].strip().split(".")[-1]
                            val = parts[1].strip().strip("'\"")
                            filters.append({"column": col, "operator": op, "value": val})
                            break

        aggregations = []
        for agg_str in report_plan.get("aggregates", []):
            if "(" in agg_str and ")" in agg_str:
                func = agg_str.split("(")[0].strip().upper()
                col = agg_str.split("(")[1].split(")")[0].strip()
                aggregations.append({
                    "function": func,
                    "column": col,
                    "alias": f"{func.lower()}_{col.replace('*', 'all')}",
                })

        group_by = report_plan.get("grouping", [])
        if isinstance(group_by, str):
            group_by = [g.strip().split(".")[-1] for g in group_by.split(",")]

        clean_columns = []
        for col in columns:
            if isinstance(col, str):
                clean_columns.append(col.split(".")[-1] if "." in col else col)

        # ── Time Range: Multi-layered extraction ──────────────────────
        # Layer 1: Use the intent agent's explicit time_range
        time_range = report_plan.get("time_range", {})
        tr = {}
        if time_range:
            if time_range.get("start_date"): tr["start"] = time_range["start_date"]
            if time_range.get("end_date"): tr["end"] = time_range["end_date"]

        # Layer 2: Safety net — parse time period from text fields if LLM missed it
        if not tr or not tr.get("start"):
            for text_field in ["report_title", "intent", "query_intent"]:
                text = report_plan.get(text_field, "")
                if text:
                    parsed = parse_time_period(text)
                    if parsed:
                        tr = parsed
                        logger.info(f"Time period extracted from '{text_field}': {tr}")
                        break

        if tr:
            logger.info(f"Final time range for query: {tr}")
        else:
            logger.info("No time period detected — querying all available data.")

        order_by = []
        raw_order = data_reqs.get("order_by") or ""
        if isinstance(raw_order, str) and raw_order:
            col_part = raw_order.strip()
            direction = "ASC"
            if col_part.upper().endswith(" DESC"):
                direction = "DESC"
                col_part = col_part[:-5].strip()
            order_by.append({"column": col_part.split(".")[-1], "direction": direction})

        limit = data_reqs.get("limit")
        if limit is None or str(limit).lower() == "none": limit = 500

        return {
            "tables": tables,
            "columns": clean_columns,
            "filters": filters,
            "aggregations": aggregations,
            "group_by": group_by,
            "order_by": order_by,
            "time_range": tr,
            "limit": int(limit),
            "report_title": report_plan.get("report_title", ""),
            "analytics_prompt": report_plan.get("analytics_prompt", ""),
        }

    def _route_to_sources(self, report_plan: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: Use semantic search to determine which data sources to query."""
        search_query = self._build_search_query(report_plan)
        routing = self.embeddings.get_routing_context(search_query)

        explicit_tables = [t.lower() for t in requirements.get("tables", [])]
        semantic_tables = routing.get("relevant_tables", [])
        all_tables = list(dict.fromkeys(explicit_tables + semantic_tables))

        reportable = set(t.lower() for t in self.knowledge_base.get_reportable_tables())
        valid_tables = [t for t in all_tables if t in reportable]

        if not valid_tables and explicit_tables:
            valid_tables = [t for t in explicit_tables if t in reportable]
        
        routing["relevant_tables"] = valid_tables
        routing["search_query"] = search_query
        return routing

    def _build_search_query(self, report_plan: Dict[str, Any]) -> str:
        """Build a natural language query for semantic search."""
        parts = []
        for key in ["report_title", "domain", "intent", "query_intent"]:
            if report_plan.get(key): parts.append(str(report_plan[key]))
        for entity in report_plan.get("entities", []): parts.append(entity)
        return " ".join(parts) if parts else "banking data report"

    def _retrieve_data(self, routing: Dict[str, Any], requirements: Dict[str, Any]) -> tuple:
        """Step 3: Call connectors to retrieve actual data."""
        sql_data = pd.DataFrame()
        file_data = pd.DataFrame()

        tables = routing.get("relevant_tables", [])
        if tables:
            try:
                sql_requirements = {
                    "tables": tables,
                    "columns": requirements.get("columns", []),
                    "filters": requirements.get("filters", []),
                    "aggregations": requirements.get("aggregations", []),
                    "group_by": requirements.get("group_by", []),
                    "order_by": requirements.get("order_by", []),
                    "time_range": requirements.get("time_range", {}),
                    "limit": requirements.get("limit", 500),
                }
                sql_data = self.sql_connector.retrieve(sql_requirements)
            except Exception as e:
                logger.error(f"SQL retrieval failed: {e}")

        # ── File retrieval with time-aware search ──────────────────
        search_query = routing.get("search_query", "")
        search_terms = list(dict.fromkeys([t for t in [requirements.get("report_title", ""), search_query] + routing.get("relevant_tables", []) if t and len(t) > 2]))

        # Add time-related keywords to boost file search relevance
        time_keywords = extract_time_keywords(requirements.get("report_title", ""))
        if time_keywords:
            search_terms = [f"{term} {' '.join(time_keywords)}" for term in search_terms] + search_terms

        time_range = requirements.get("time_range", {})

        for term in search_terms[:3]:
            try:
                file_req = {
                    "search_term": term,
                    "file_types": [".csv", ".json", ".txt"],
                }
                if time_range:
                    file_req["time_range"] = time_range
                new_file_data = self.file_connector.retrieve(file_req)
                if not new_file_data.empty:
                    file_data = pd.concat([file_data, new_file_data], ignore_index=True).drop_duplicates() if not file_data.empty else new_file_data
                    if len(file_data) > 50: break
            except Exception as e:
                logger.warning(f"File retrieval for term '{term}' failed: {e}")

        return sql_data, file_data

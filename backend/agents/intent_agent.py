"""
Intent Agent — understands user prompts and generates structured report plans.
Uses Groq LLM for natural language understanding.

IMPORTANT: This agent NO LONGER generates SQL queries. It extracts structured
data requirements (tables, columns, filters, aggregations) that the RAG
orchestrator uses to retrieve data safely from connectors.
"""

import os
import json
from groq import Groq
from backend.config.settings import Config
from backend.chat.chat_service import ChatService


class IntentAgent:
    """Parses user prompts into structured report plans (no SQL generation)."""

    # Structured output format — data requirements instead of SQL
    REQUIRED_OUTPUT_FORMAT = {
        "intent_type": "report",
        "intent": "",
        "domain": "",
        "entities": [],
        "fields": [],
        "filters": [],
        "time_range": {"start_date": None, "end_date": None},
        "grouping": [],
        "aggregates": [],
        "report_title": "",
        "query_intent": "",
        "data_requirements": {
            "tables": [],
            "columns": [],
            "filters": "",
            "group_by": None,
            "order_by": None,
            "limit": None,
        },
        "analytics_prompt": "",
    }

    def __init__(self):
        groq_key = Config.GROQ_API_KEY

        if groq_key:
            self.client = Groq(
                api_key=groq_key,
            )
            self.model = "llama-3.3-70b-versatile"
        else:
            self.client = None
            print("WARNING: No LLM API key configured (GROQ_API_KEY)")

    def generate_report_plan(self, user_prompt: str, history: list = None) -> dict:
        """
        Generate a structured report plan from a natural language prompt.
        Returns JSON dict or {"error": "..."} on failure.

        The plan describes WHAT data is needed, not HOW to query it.
        """
        # Pre-filter greetings and very short messages
        simple_greetings = [
            "hi", "hello", "hey", "yo", "sup", "good morning",
            "good day", "assalamoalaikum", "generate any report",
        ]
        # Only check greetings if no history (first message)
        if (not history) and (user_prompt.lower().strip() in simple_greetings):
            return {
                "error": "Hey! I'm your AI Report Designer. Tell me what report you'd like "
                         "(e.g. 'top transactions in the last quarter of 2026' or "
                         "'total transactions done by expired cards') and I'll generate it for you."
            }

        if not self.client:
            return self._mock_response(user_prompt)

        import time
        current_date_str = time.strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = self._get_system_prompt()
        system_prompt += f"\n\nCURRENT DATE AND TIME: {current_date_str}\n"

        # Build messages with history
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            recent_history = history[-10:]
            for msg in recent_history:
                content = msg.get("content", "")
                if isinstance(content, str):
                    messages.append({"role": msg["role"], "content": content})

        messages.append({"role": "user", "content": user_prompt})

        # Retry up to 2 times if JSON parsing fails
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content

                # Clean markdown fences if present
                if "```json" in content:
                    content = content.rsplit("```json", 1)[1].rsplit("```", 1)[0].strip()
                elif "```" in content:
                    content = content.replace("```", "").strip()

                result = json.loads(content)

                # Ensure default values for all required fields
                for key, val in self.REQUIRED_OUTPUT_FORMAT.items():
                    if key not in result:
                        result[key] = val

                return result

            except json.JSONDecodeError:
                if attempt == 0:
                    continue
                return {"error": "JSON parse failed."}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"error": f"LLM error: {str(e)}"}

        return {"error": "Failed."}

    def _get_system_prompt(self) -> str:
        """Build the system prompt with schema metadata for intent extraction."""
        schema = ChatService.get_schema_entities()
        schema_str = json.dumps(schema, indent=2)

        return f"""
You are an intelligent banking report request analyzer for an enterprise Bank CRM system.

YOUR ROLE: Understand the user's report request and identify WHAT DATA is needed.
You do NOT generate SQL. You do NOT write queries. You describe data requirements.

CRITICAL RULES:
1. Return ONLY valid JSON. No preamble.
2. Identify which tables and columns are needed.
3. Extract filters, time ranges, groupings, and aggregations.
4. TEMPORAL LOGIC: Use the CURRENT DATE provided to resolve relative terms (e.g., 'Q3 2025' or 'last quarter').
5. SUPPLEMENTARY SOURCES: If the query involves "risk", "security", or "intelligence", suggest searching "File-based supplementary documents" by adding "file_system" to entities.
6. If the request is a greeting, set intent_type to "chat".
7. If unclear, set intent_type to "clarify".

AVAILABLE DATABASE TABLES AND COLUMNS:
{schema_str}

TABLE DOMAIN MAPPING:
- Customer Management: customers
- Account Management: accounts
- Branch Management: branches
- Transaction Management: transactions, external_accounts
- Card Management: cards, card_transactions, merchants
- Card Risk & Security Intelligence: card_risk_intelligence (file), merchant_security_scores (file)

REQUIRED JSON OUTPUT FORMAT:
{{
  "intent_type": "report | clarify | chat",
  "intent": "Brief description of what the user wants",
  "domain": "transaction_analysis | card_management | customer_analysis | ...",
  "entities": ["table_name_1", "table_name_2"],
  "fields": ["column_1", "column_2"],
  "filters": ["status = 'Active'", "amount > 1000"],
  "time_range": {{"start_date": "2026-01-01", "end_date": "2026-03-31"}},
  "grouping": ["column_to_group_by"],
  "aggregates": ["SUM(amount)", "COUNT(*)"],
  "report_title": "Descriptive Report Title",
  "query_intent": "What analysis the user wants",
  "data_requirements": {{
    "tables": ["transactions", "accounts"],
    "columns": ["amount", "transaction_date", "account_type"],
    "filters": "status = 'COMPLETED' AND amount > 0",
    "group_by": "account_type",
    "order_by": "SUM(amount) DESC",
    "limit": null
  }},
  "analytics_prompt": "Analyze spending patterns by account type, highlight top performers."
}}

EXAMPLES:

Example 1: "Show total balance by account type"
{{
  "intent_type": "report",
  "intent": "Total balance aggregated by account type",
  "domain": "account_analysis",
  "entities": ["accounts"],
  "fields": ["balance", "account_type"],
  "filters": [],
  "time_range": {{"start_date": null, "end_date": null}},
  "grouping": ["account_type"],
  "aggregates": ["SUM(balance)"],
  "report_title": "Total Balance by Account Type",
  "query_intent": "Aggregate account balances grouped by type",
  "data_requirements": {{
    "tables": ["accounts"],
    "columns": ["account_type", "balance"],
    "filters": "",
    "group_by": "account_type",
    "order_by": "SUM(balance) DESC",
    "limit": null
  }},
  "analytics_prompt": "Analyze the distribution of account balances across different account types."
}}

Example 2: "Q1 credit card transactions by merchant category"
{{
  "intent_type": "report",
  "intent": "Card transactions in Q1 grouped by merchant category",
  "domain": "card_management",
  "entities": ["card_transactions", "merchants"],
  "fields": ["amount", "category_code", "transaction_date"],
  "filters": [],
  "time_range": {{"start_date": "2026-01-01", "end_date": "2026-03-31"}},
  "grouping": ["category_code"],
  "aggregates": ["SUM(amount)", "COUNT(*)"],
  "report_title": "Q1 Card Transactions by Merchant Category",
  "query_intent": "Analyze card spending by merchant category in Q1",
  "data_requirements": {{
    "tables": ["card_transactions", "merchants"],
    "columns": ["amount", "category_code", "transaction_date"],
    "filters": "",
    "group_by": "category_code",
    "order_by": "SUM(amount) DESC",
    "limit": null
  }},
  "analytics_prompt": "Analyze card transaction volumes and amounts across merchant categories for Q1. Identify top spending categories."
}}

Example 3: "hello" (greeting)
{{
  "intent_type": "chat",
  "intent": "User is greeting, not requesting a report",
  "domain": "",
  "entities": [],
  "fields": [],
  "filters": [],
  "time_range": {{"start_date": null, "end_date": null}},
  "grouping": [],
  "aggregates": [],
  "report_title": "",
  "query_intent": "",
  "data_requirements": {{"tables": [], "columns": [], "filters": "", "group_by": null, "order_by": null, "limit": null}},
  "analytics_prompt": ""
}}
"""

    def _mock_response(self, user_prompt: str) -> dict:
        """Fallback mock response when no LLM is available."""
        return {
            "intent_type": "report",
            "intent": "Mock intent from user prompt",
            "domain": "transaction_analysis",
            "entities": ["transactions"],
            "fields": ["amount", "transaction_date"],
            "filters": [],
            "time_range": {"start_date": None, "end_date": None},
            "grouping": [],
            "aggregates": [],
            "report_title": "Transaction Report",
            "query_intent": "Retrieve transaction data",
            "data_requirements": {
                "tables": ["transactions"],
                "columns": ["*"],
                "filters": "",
                "group_by": None,
                "order_by": None,
                "limit": 100,
            },
            "analytics_prompt": "Analyze the transaction data.",
        }

"""
Intent Agent — understands user prompts and generates structured report plans.
Uses Groq or OpenAI LLM for natural language understanding.
"""

import os
import json
from openai import OpenAI
from backend.config.settings import Config
from backend.chat.chat_service import ChatService


class IntentAgent:
    """Parses user prompts into structured JSON report plans."""

    # Strict JSON output format required by the system
    REQUIRED_OUTPUT_FORMAT = {
        "intent": "",
        "domain": "",
        "entities": [],
        "fields": [],
        "filters": [],
        "time_range": "",
        "grouping": [],
    }

    def __init__(self):
        groq_key = Config.GROQ_API_KEY
        openai_key = Config.OPENAI_API_KEY

        if groq_key:
            self.client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self.model = "llama-3.3-70b-versatile"
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = "gpt-3.5-turbo"
        else:
            self.client = None
            print("WARNING: No LLM API key configured (GROQ_API_KEY or OPENAI_API_KEY)")

    def generate_report_plan(self, user_prompt: str) -> dict:
        """
        Generate a structured report plan from a natural language prompt.
        Returns JSON dict or {"error": "..."} on failure.
        """
        # Pre-filter greetings and very short messages
        simple_greetings = [
            "hi", "hello", "hey", "yo", "sup", "good morning",
            "good day", "assalamoalaikum", "generate any report",
        ]
        if user_prompt.lower().strip() in simple_greetings or len(user_prompt.strip().split()) < 3:
            return {
                "error": "Hey! I'm your AI Report Designer. Tell me what report you'd like "
                         "(e.g. 'top transactions in the last quarter of 2026' or 'total transactions done by expired cards') and I'll generate it for you."
            }

        if not self.client:
            return self._mock_response(user_prompt)

        system_prompt = self._get_system_prompt()

        # Retry up to 2 times if JSON parsing fails
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
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

                # If LLM returned an error response, pass through
                if "error" in result:
                    return result

                # Validate the output has required keys
                if not isinstance(result, dict):
                    raise ValueError("LLM response is not a JSON object")

                return result

            except json.JSONDecodeError:
                if attempt == 0:
                    print(f"JSON parse failed (attempt {attempt + 1}), retrying...")
                    continue
                return {"error": "Sorry, I couldn't understand that request. Please ask for a banking report."}
            except Exception as e:
                print(f"Error during LLM call: {e}")
                return {"error": "I'm having trouble processing that. Try a more specific report request."}

        return {"error": "Failed to generate report plan after retries."}

    def _get_system_prompt(self) -> str:
        """Build the system prompt with schema metadata."""
        schema = ChatService.get_schema_entities()
        schema_str = json.dumps(schema, indent=2)

        return f"""
You are a STRICT report planning engine for a Bank CRM system.

AVAILABLE DOMAINS:
1. Card Management System (tables: cards, card_transactions, merchants, card_lifecycle)
2. Transaction Management System (tables: transactions, external_accounts, employees)

SHARED ENTITIES (used by both domains):
- customers, accounts, branches, roles, users, user_roles, user_sessions, audit_logs

Rules - you MUST follow ALL of these:
- ONLY generate a report plan if the user message is clearly asking for a banking report, data analysis, or transaction/card related summary.
- If the message is a greeting, casual chat, or anything NOT a report request → return:
  {{"error": "Hey! I'm your AI Report Designer. Tell me what report you'd like (e.g. 'top transactions') and I'll generate it for you."}}
- Do NOT hallucinate or force a report when no request is made.

CRITICAL RULES:
    - You MUST output ONLY valid JSON.
    - Do NOT write explanations or markdown.
    - The output MUST start with {{ and end with }}.
    - Use the EXACT table and column names provided.
    - For dates, use PostgreSQL compatible format (YYYY-MM-DD).
    - Do not add arbitrary limits unless user asks.
    - YOU ARE THE PRIMARY SQL GENERATOR. You must provide a valid PostgreSQL query in the "generated_sql" field.

Database schema (from metadata.json):
{schema_str}

JSON output format (you MUST follow this exactly):
{{
    "intent": "string describing what the user wants",
    "domain": "Card Management System OR Transaction Management System",
    "entities": ["list of tables to query"],
    "fields": ["list of table.column to select"],
    "filters": ["list of SQL WHERE conditions"],
    "time_range": "string or empty",
    "grouping": ["list of GROUP BY columns"],
    "report_title": "string",
    "query_intent": "string describing the data need",
    "generated_sql": "COMPLETE AND VALID POSTGRESQL QUERY",
    "data_requirements": {{
        "tables": ["string"],
        "columns": ["string"],
        "filters": "string (SQL WHERE clause fragment)",
        "group_by": "string or null",
        "order_by": "string or null",
        "limit": null
    }},
    "analytics_prompt": "string instruction for the analytics agent"
}}
"""

    def _mock_response(self, user_prompt: str) -> dict:
        """Fallback mock response when no LLM key is configured."""
        return {
            "intent": "Mock intent for testing",
            "domain": "Transaction Management System",
            "entities": ["transactions", "customers"],
            "fields": ["transactions.amount", "customers.first_name"],
            "filters": ["transactions.amount > 100"],
            "time_range": "",
            "grouping": [],
            "report_title": "Mock Report — Transaction Summary",
            "query_intent": "Mock intent for testing",
            "generated_sql": "SELECT t.amount, c.first_name, c.last_name FROM transactions t JOIN accounts a ON t.sender_account_id = a.account_id JOIN customers c ON a.customer_id = c.customer_id WHERE t.amount > 100 ORDER BY t.amount DESC LIMIT 10",
            "data_requirements": {
                "tables": ["transactions", "accounts", "customers"],
                "columns": ["transactions.amount", "customers.first_name", "customers.last_name"],
                "filters": "transactions.amount > 100",
                "group_by": None,
                "order_by": "transactions.amount DESC",
                "limit": 10,
            },
            "analytics_prompt": "Analyze this mock data.",
        }

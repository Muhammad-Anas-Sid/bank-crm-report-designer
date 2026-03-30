"""
Data Engine — executes validated SQL and returns Pandas DataFrames.

NOTE: This module is a legacy utility kept for any direct SQL needs.
The primary data pipeline now uses the RAG Orchestrator (rag_system/)
which retrieves data via the SQLConnector without LLM-generated SQL.
"""

import re
import math
import pandas as pd
import numpy as np
from sqlalchemy import text
from backend.models.base import get_db_engine


class _InlineValidator:
    """
    Minimal inline SQL safety guard.
    Only SELECT statements (and WITH … SELECT CTEs) are permitted.
    This replaces the removed backend.query_builder.SqlValidator.
    """

    # Statements that are never allowed regardless of context
    _BLOCKED_KEYWORDS = (
        r"\bDROP\b", r"\bDELETE\b", r"\bTRUNCATE\b",
        r"\bINSERT\b", r"\bUPDATE\b", r"\bALTER\b",
        r"\bCREATE\b", r"\bGRANT\b", r"\bREVOKE\b",
        r"\bEXEC\b", r"\bEXECUTE\b",
    )

    def validate(self, sql: str):
        """Return (is_valid: bool, error_message: str | None)."""
        stripped = sql.strip().upper()
        if not stripped:
            return False, "Empty query"
        # Only SELECT or WITH … SELECT is allowed
        if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
            return False, "Only SELECT queries are permitted"
        # Block dangerous DML/DDL keywords anywhere in the query
        for pattern in self._BLOCKED_KEYWORDS:
            if re.search(pattern, stripped):
                return False, f"Blocked keyword detected: {pattern}"
        return True, None


class DataEngine:
    """Executes validated SQL queries and returns clean DataFrames."""

    def __init__(self):
        self.engine = get_db_engine()
        self.validator = _InlineValidator()

    def execute_query(self, sql_query: str, schema: dict = None, params: dict = None) -> pd.DataFrame:
        """
        Validate and execute a SQL SELECT query.
        Returns a clean Pandas DataFrame.

        Args:
            sql_query: The SQL query string (may contain %(name)s placeholders).
            schema: Optional schema dict (currently unused but kept for interface).
            params: Optional dict of parameter values to bind to the query.

        Rules:
        - Execute validated SQL only
        - Return Pandas DataFrame
        - Convert safely to JSON (handle NaN)
        - Never return raw cursor objects
        """
        if not sql_query or not sql_query.strip():
            print("Execute Error: Empty SQL query.")
            return pd.DataFrame()

        # Validate through safety layer
        # Note: ReportPlanner already calls validate_sql, but double check is safe.
        is_valid, error = self.validator.validate(sql_query)
        if not is_valid:
            print(f"Execute Blocked: {error}")
            raise ValueError(f"Query blocked: {error}")

        try:
            with self.engine.connect() as conn:
                # Convert %(name)s to :name for SQLAlchemy text()
                # We assume the params dict keys match 'name'
                query_text = sql_query
                
                if params:
                    # Replace %(param_name)s with :param_name
                    # This regex matches the pyformat style used in our prompt logic
                    query_text = re.sub(r'%\((\w+)\)s', r':\1', query_text)
                    stmt = text(query_text)
                    # Pandas read_sql_query passes params to execute()
                    df = pd.read_sql_query(stmt, con=conn, params=params)
                else:
                    df = pd.read_sql_query(text(query_text), con=conn)
                    
        except Exception as e:
            print(f"DataEngine Execution Failed: {e}")
            raise ValueError(f"Query execution failed: {str(e)}")

        # Clean the DataFrame
        df = self._sanitize_dataframe(df)

        return df

    def _sanitize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Safely clean a DataFrame for JSON serialization.
        Handles NaN, NaT, Infinity values.
        """
        if df.empty:
            return df

        # Replace NaN with None
        df = df.where(df.notna(), None)

        # Handle Infinity values in numeric columns
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].apply(
                lambda x: None if x is not None and isinstance(x, float) and (math.isinf(x) or math.isnan(x)) else x
            )

        # Convert datetime columns to ISO format strings
        for col in df.select_dtypes(include=["datetime64", "datetimetz"]).columns:
            df[col] = df[col].apply(
                lambda x: x.isoformat() if pd.notna(x) else None
            )

        # Convert Decimal to float
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(
                    lambda x: float(x) if hasattr(x, 'as_tuple') else x  # Decimal check
                )

        return df

    def to_safe_json(self, df: pd.DataFrame) -> list:
        """Convert DataFrame to JSON-safe list of dicts."""
        if df.empty:
            return []
        sanitized = self._sanitize_dataframe(df.copy())
        return sanitized.to_dict(orient="records")

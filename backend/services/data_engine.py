"""
Data Engine — executes validated SQL and returns Pandas DataFrames.
"""

import re
import math
import pandas as pd
import numpy as np
from sqlalchemy import text
from backend.models.base import get_db_engine
from backend.query_builder.sql_validator import SqlValidator


class DataEngine:
    """Executes validated SQL queries and returns clean DataFrames."""

    def __init__(self):
        self.engine = get_db_engine()
        self.validator = SqlValidator()

    def execute_query(self, sql_query: str, schema: dict = None) -> pd.DataFrame:
        """
        Validate and execute a SQL SELECT query.
        Returns a clean Pandas DataFrame.

        Rules:
        - Execute validated SQL only
        - Return Pandas DataFrame
        - Convert safely to JSON (handle NaN)
        - Never return raw cursor objects
        """
        if not sql_query or not sql_query.strip():
            raise ValueError("Empty SQL query provided.")

        # Validate through safety layer
        is_valid, error = self.validator.validate(sql_query)
        if not is_valid:
            raise ValueError(f"Query blocked: {error}")

        # Execute safely
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(sql_query), con=conn)
        except Exception as e:
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

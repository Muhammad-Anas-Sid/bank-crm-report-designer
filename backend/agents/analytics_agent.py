"""
Analytics Agent — generates business insights from query results.
"""

import os
import pandas as pd
from groq import Groq
from backend.config.settings import Config


class AnalyticsAgent:
    """Generates business summary, trends, metrics, and recommendations from data."""

    def __init__(self):
        groq_key = Config.GROQ_API_KEY

        if groq_key:
            self.client = Groq(
                api_key=groq_key,
            )
            self.model = "llama-3.3-70b-versatile"
        else:
            self.client = None
            print("WARNING: AnalyticsAgent has no LLM API key configured")

    def generate_insights(self, dataframe: pd.DataFrame, analytics_instruction: str) -> str:
        """
        Generate business insights from a DataFrame.

        Must include:
        - Business summary
        - Trend analysis with accurate and precise numbers
        - Key metrics / KPIs with formulae (if needed)
        - Recommendations
        """
        if dataframe.empty:
            return "No data found to analyze."

        data_summary = self._build_data_summary(dataframe)

        prompt = f"""
You are a senior banking data analyst.

Analyze this dataset summary according to the instruction: "{analytics_instruction}"

DATA:
{data_summary}

Guidelines:
- Executive tone, professional banking language
- Max 150-200 words total
- Do NOT invent numbers — only use what's in the summary
- Be specific and actionable
- Use bullet-point format
"""

        if not self.client:
            return self._mock_insights(dataframe)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise, professional banking analyst."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.45,
                max_tokens=400,
            )
            insight = response.choices[0].message.content.strip()
            return insight
        except Exception as e:
            print(f"AnalyticsAgent LLM error: {e}")
            return "Could not generate insights due to an error."

    def _build_data_summary(self, dataframe: pd.DataFrame) -> str:
        """Build a concise but rich data summary for the LLM."""
        buf = []
        buf.append(f"Dataset: {dataframe.shape[0]} rows, {dataframe.shape[1]} columns")
        buf.append(f"Columns: {', '.join(dataframe.columns)}")

        buf.append("\nSample (top 5):")
        buf.append(dataframe.head(5).to_string(index=False))

        num_cols = dataframe.select_dtypes(include=["number"])
        if not num_cols.empty:
            buf.append("\nNumeric Stats:")
            buf.append(num_cols.describe().to_string())

        cat_cols = dataframe.select_dtypes(include=["object", "category"])
        if not cat_cols.empty:
            buf.append("\nCategorical top values:")
            for col in cat_cols.columns:
                if dataframe[col].nunique() < 30:
                    top = dataframe[col].value_counts().head(3).to_dict()
                    buf.append(f"  {col}: {top}")

        return "\n".join(buf)

    def _mock_insights(self, dataframe: pd.DataFrame) -> str:
        """Fallback insights when no LLM is available."""
        rows = len(dataframe)
        cols = len(dataframe.columns)
        return (
            f"**Business Summary**: Dataset contains {rows} records across {cols} attributes.\n\n"
            f"**Key Metrics**: {rows} total records analyzed.\n\n"
            f"**Trend Analysis**: Further analysis requires LLM API key configuration.\n\n"
            f"**Recommendations**: Configure GROQ_API_KEY or OPENAI_API_KEY for full analytics."
        )

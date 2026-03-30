"""
Data Aggregator — combines results from multiple data source connectors.

Takes DataFrames from SQL connector, file connector, and any future connectors,
then merges them into a coherent structure with source attribution. The aggregated
result is formatted as a context block ready for the LLM to write reports from.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataAggregator:
    """
    Combines and formats data from multiple retrieval sources.

    Responsibilities:
    1. Merge DataFrames from different connectors
    2. Deduplicate overlapping records
    3. Add source attribution (which data came from where)
    4. Format into a context block suitable for LLM report generation
    """

    def aggregate(
        self,
        sql_results: Optional[pd.DataFrame] = None,
        file_results: Optional[pd.DataFrame] = None,
        additional_sources: Optional[Dict[str, pd.DataFrame]] = None,
        time_period: str = "",
    ) -> Dict[str, Any]:
        """
        Combine results from all data sources.

        Args:
            sql_results: DataFrame from SQL connector (or None if no SQL data)
            file_results: DataFrame from file connector (or None if no file data)
            additional_sources: Dict of source_name → DataFrame for future connectors

        Returns:
            {
                "combined_data": DataFrame,
                "sources_used": ["postgresql", "file_system", ...],
                "total_rows": int,
                "source_breakdown": { "postgresql": 150, "file_system": 23 },
                "context_for_llm": str  (formatted text for LLM)
            }
        """
        sources_used = []
        source_breakdown = {}
        all_frames = {}

        # Process SQL results
        if sql_results is not None and not sql_results.empty:
            sources_used.append("postgresql")
            source_breakdown["postgresql"] = len(sql_results)
            all_frames["postgresql"] = sql_results

        # Process file results
        if file_results is not None and not file_results.empty:
            sources_used.append("file_system")
            source_breakdown["file_system"] = len(file_results)
            all_frames["file_system"] = file_results

        # Process any additional sources
        if additional_sources:
            for name, df in additional_sources.items():
                if df is not None and not df.empty:
                    sources_used.append(name)
                    source_breakdown[name] = len(df)
                    all_frames[name] = df

        # Combine into a single DataFrame if possible
        combined = self._merge_frames(all_frames)
        total_rows = len(combined) if not combined.empty else 0

        # Build LLM context
        context = self._format_for_llm(all_frames, source_breakdown, time_period)

        return {
            "combined_data": combined,
            "sources_used": sources_used,
            "total_rows": total_rows,
            "source_breakdown": source_breakdown,
            "context_for_llm": context,
            "individual_sources": all_frames,
        }

    def _merge_frames(self, frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Merge DataFrames from different sources.

        If column schemas are compatible, concatenates vertically.
        Otherwise, returns the primary (SQL) source or the largest frame.
        """
        if not frames:
            return pd.DataFrame()

        if len(frames) == 1:
            return list(frames.values())[0]

        # Prefer SQL data as the primary source
        if "postgresql" in frames:
            primary = frames["postgresql"]
        else:
            # Use the largest frame as primary
            primary = max(frames.values(), key=len)

        # Try to merge compatible frames
        compatible_frames = [primary]
        for name, df in frames.items():
            if df is primary:
                continue
            # Check if columns overlap significantly
            overlap = set(primary.columns) & set(df.columns)
            if len(overlap) > len(primary.columns) * 0.5:
                compatible_frames.append(df)

        if len(compatible_frames) > 1:
            try:
                return pd.concat(compatible_frames, ignore_index=True)
            except Exception as e:
                logger.warning(f"Could not merge frames: {e}")

        return primary

    def _format_for_llm(
        self, frames: Dict[str, pd.DataFrame], breakdown: Dict[str, int],
        time_period: str = "",
    ) -> str:
        """
        Format aggregated data into a rich text context block for the LLM.

        The LLM uses this context to write a professional banking report.
        It contains ONLY real data — the LLM should never need to hallucinate.
        """
        if not frames:
            return "No data was retrieved from any source."

        sections = []
        sections.append("=== RETRIEVED DATA FOR REPORT GENERATION ===\n")
        sections.append(f"Data Sources: {', '.join(breakdown.keys())}")
        sections.append(f"Total Records: {sum(breakdown.values())}")
        if time_period:
            sections.append(f"Time Period: {time_period}")
        sections.append("")

        for source_name, df in frames.items():
            sections.append(f"--- Source: {source_name.upper()} ({len(df)} rows) ---")
            sections.append(f"Columns: {', '.join(df.columns)}")

            # Data sample (top rows)
            sample_count = min(20, len(df))
            sections.append(f"\nData Sample ({sample_count} rows):")
            sections.append(df.head(sample_count).to_string(index=False))

            # Numeric statistics
            num_cols = df.select_dtypes(include=["number"])
            if not num_cols.empty:
                sections.append("\nNumeric Statistics:")
                sections.append(num_cols.describe().to_string())

            # Categorical distributions
            cat_cols = df.select_dtypes(include=["object", "category"])
            if not cat_cols.empty:
                sections.append("\nCategorical Distributions:")
                for col in cat_cols.columns:
                    if col.startswith("_"):  # Skip internal columns
                        continue
                    nunique = df[col].nunique()
                    if nunique <= 20:
                        dist = df[col].value_counts().head(10).to_dict()
                        sections.append(f"  {col}: {dist}")
                    else:
                        sections.append(f"  {col}: {nunique} unique values")

            sections.append("")  # blank line between sources

        sections.append("=== END OF RETRIEVED DATA ===")
        sections.append(
            "\nIMPORTANT: Use ONLY the data above to write the report. "
            "Do NOT invent, estimate, or hallucinate any numbers. "
            "Every statistic must come from this retrieved data."
        )

        return "\n".join(sections)

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove exact duplicate rows from a DataFrame."""
        if df.empty:
            return df
        # Drop columns that are internal metadata before dedup
        dedup_cols = [c for c in df.columns if not c.startswith("_")]
        return df.drop_duplicates(subset=dedup_cols, keep="first")

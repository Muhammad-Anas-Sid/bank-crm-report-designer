"""
Base Connector — abstract interface for all RAG data source connectors.

Every data source (PostgreSQL, files, NoSQL, APIs) implements this interface.
This ensures uniform behavior for the RAG orchestrator and data aggregator.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd


class BaseConnector(ABC):
    """
    Abstract base class for data source connectors.

    Each connector knows how to:
    1. Connect to its data source
    2. Retrieve data based on structured requirements
    3. Format results into a standardized output
    4. Report what data is available

    The RAG orchestrator calls these methods without knowing the
    underlying data source implementation.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def retrieve(self, requirements: Dict[str, Any]) -> pd.DataFrame:
        """
        Retrieve data based on structured requirements.

        The requirements dict is built by the RAG orchestrator from
        semantic search results — it never contains LLM-generated queries.

        Args:
            requirements: Structured retrieval spec. Keys vary by connector:
                - SQL: {"table", "columns", "filters", "aggregations", "joins", "limit"}
                - File: {"search_term", "file_types", "directory"}

        Returns:
            DataFrame containing the retrieved data.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Return metadata about what data is available in this source.

        Used during initialization to register available data with
        the knowledge base and embeddings manager.

        Returns:
            Dict describing available tables/files/collections.
        """
        pass

    def format_results(self, raw_data: pd.DataFrame, source_name: str) -> Dict[str, Any]:
        """
        Standardize output format for the data aggregator.

        Args:
            raw_data: The retrieved DataFrame.
            source_name: Identifier for this data source (e.g., "postgresql", "file_system").

        Returns:
            Standardized result dict with data, metadata, and source info.
        """
        return {
            "source": source_name,
            "data": raw_data,
            "row_count": len(raw_data),
            "columns": list(raw_data.columns) if not raw_data.empty else [],
            "empty": raw_data.empty,
        }

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the type identifier for this connector (e.g., 'sql', 'file')."""
        pass

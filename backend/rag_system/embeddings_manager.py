"""
Embeddings Manager — semantic search over the banking schema knowledge base.

Uses sentence-transformers to embed schema documents and FAISS for fast
vector similarity search. Falls back to keyword matching if ML libraries
are unavailable.
"""

import logging
import re
from typing import List, Dict, Any, Optional

import numpy as np

from backend.rag_system.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Attempt to load ML libraries; graceful fallback if unavailable
try:
    from sentence_transformers import SentenceTransformer
    import faiss

    _ML_AVAILABLE = True
    logger.info("Sentence-transformers and FAISS loaded successfully.")
except ImportError:
    _ML_AVAILABLE = False
    logger.warning(
        "sentence-transformers or faiss-cpu not installed. "
        "Falling back to keyword-based matching. "
        "Install with: pip install sentence-transformers faiss-cpu"
    )


class EmbeddingsManager:
    """
    Manages semantic search over the schema knowledge base.

    At startup, embeds all knowledge base documents into a FAISS index.
    When a user query arrives, embeds it and finds the most relevant
    tables/columns by vector similarity.

    Fallback: If sentence-transformers is not installed, uses simple
    keyword matching (less accurate but functional).
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None):
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.documents = self.knowledge_base.get_documents()
        self.model = None
        self.index = None
        self.embeddings = None

        if _ML_AVAILABLE and self.documents:
            self._build_index()
        else:
            logger.info("Using keyword fallback for schema search.")

    def _build_index(self):
        """Build FAISS index from knowledge base documents."""
        try:
            logger.info(f"Loading embedding model: {self.MODEL_NAME}")
            self.model = SentenceTransformer(self.MODEL_NAME)

            # Embed all document texts
            texts = [doc["text"] for doc in self.documents]
            self.embeddings = self.model.encode(texts, convert_to_numpy=True)

            # Normalize for cosine similarity
            faiss.normalize_L2(self.embeddings)

            # Build FAISS index (Inner Product on normalized vectors = cosine similarity)
            dimension = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(self.embeddings)

            logger.info(
                f"FAISS index built: {len(texts)} documents, {dimension}-dim embeddings."
            )
        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}. Falling back to keywords.")
            self.model = None
            self.index = None

    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for the most relevant schema documents given a natural language query.

        Args:
            query: Natural language search query (e.g., "card transactions by merchant")
            k: Number of top results to return

        Returns:
            List of dicts with keys: text, table, column, domain, score, doc_type
        """
        if not self.documents:
            return []

        if self.model and self.index:
            return self._semantic_search(query, k)
        else:
            return self._keyword_search(query, k)

    def _semantic_search(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Vector similarity search using FAISS."""
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_embedding)

        k = min(k, len(self.documents))
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = self.documents[idx].copy()
            doc["score"] = float(score)
            results.append(doc)

        return results

    def _keyword_search(self, query: str, k: int) -> List[Dict[str, Any]]:
        """
        Fallback keyword-based search when ML libraries aren't available.
        Scores documents by counting keyword overlaps with the query.
        """
        query_words = set(re.findall(r'\w+', query.lower()))

        scored = []
        for doc in self.documents:
            doc_words = set(re.findall(r'\w+', doc["text"].lower()))
            overlap = len(query_words & doc_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                entry = doc.copy()
                entry["score"] = score
                scored.append(entry)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def find_relevant_tables(self, query: str, threshold: float = 0.2) -> List[str]:
        """
        Find table names relevant to the query, deduplicated and scored above threshold.

        Returns a list of unique table names ordered by relevance.
        """
        results = self.search(query, k=20)
        seen = set()
        tables = []
        for r in results:
            if r["score"] >= threshold and r["table"] not in seen:
                seen.add(r["table"])
                tables.append(r["table"])
        return tables

    def find_relevant_columns(self, query: str, table_name: str) -> List[str]:
        """
        Find columns in a specific table that are relevant to the query.
        If no strong matches, returns all columns for that table.
        """
        results = self.search(query, k=30)

        matched_cols = []
        for r in results:
            if r["table"] == table_name and r["column"] and r["score"] > 0.15:
                matched_cols.append(r["column"])

        # If semantic search found relevant columns, use them;
        # otherwise fall back to all columns for that table
        if matched_cols:
            return matched_cols
        return self.knowledge_base.get_table_columns(table_name)

    def get_routing_context(self, query: str) -> Dict[str, Any]:
        """
        Build a complete routing context for the RAG orchestrator.

        Returns:
            {
                "relevant_tables": ["transactions", "accounts", ...],
                "table_columns": {"transactions": ["amount", "date", ...], ...},
                "domains": ["Transaction Management", ...],
                "search_results": [...]
            }
        """
        results = self.search(query, k=15)
        tables = self.find_relevant_tables(query)

        table_columns = {}
        domains = set()
        for table in tables:
            table_columns[table] = self.find_relevant_columns(query, table)
            domains.add(self.knowledge_base.get_domain_for_table(table))

        return {
            "relevant_tables": tables,
            "table_columns": table_columns,
            "domains": list(domains),
            "search_results": results,
        }

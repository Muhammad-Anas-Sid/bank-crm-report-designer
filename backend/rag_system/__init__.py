"""
RAG System — Retrieval-Augmented Generation for banking report data.
Replaces the old query-building approach with semantic retrieval from multiple sources.
"""

from backend.rag_system.rag_orchestrator import RAGOrchestrator

__all__ = ["RAGOrchestrator"]

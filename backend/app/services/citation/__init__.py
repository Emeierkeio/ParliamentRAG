"""
Citation services for Multi-View RAG.

Provides semantic sentence extraction and citation formatting.
"""
from .sentence_extractor import SentenceExtractor, extract_best_sentences

__all__ = ["SentenceExtractor", "extract_best_sentences"]

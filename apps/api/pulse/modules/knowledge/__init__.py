"""Knowledge & RAG module for «Норд Инжиниринг»."""

from pulse.modules.knowledge.eval import run_eval
from pulse.modules.knowledge.model import KbAnswer, KbDocInfo, KbSource, KbStats
from pulse.modules.knowledge.rag import answer_question
from pulse.modules.knowledge.search import search_chunks
from pulse.modules.knowledge.store import ensure_seeded, get_documents, get_stats

__all__ = [
    "KbAnswer",
    "KbDocInfo",
    "KbSource",
    "KbStats",
    "answer_question",
    "ensure_seeded",
    "get_documents",
    "get_stats",
    "run_eval",
    "search_chunks",
]

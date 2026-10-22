"""BM25 retrieval over the stemmed index, plus how much of the question each section actually covers."""

from dataclasses import dataclass

from pulse.core import db
from pulse.modules.knowledge.index import Chunk, ensure_index, stems


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: Chunk
    score: float  # BM25, higher is better
    coverage: float  # share of the question's meaningful stems found in the section


def search(question: str, k: int = 5) -> list[Hit]:
    ensure_index()
    terms = sorted(set(stems(question)))
    if not terms:
        return []
    expr = " OR ".join(f'"{t}"*' for t in terms)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT c.*, f.stems AS st, bm25(kb_fts) AS rank FROM kb_fts f JOIN kb_chunk c ON c.id = f.rowid "
            "WHERE kb_fts MATCH ? ORDER BY rank LIMIT ?",
            (expr, k),
        ).fetchall()
    hits = []
    for r in rows:
        indexed = r["st"].split()
        found = sum(1 for t in terms if any(w.startswith(t) for w in indexed))
        chunk = Chunk(r["id"], r["doc"], r["doc_title"], r["category"], r["section"], r["text"])
        hits.append(Hit(chunk, round(-float(r["rank"]), 3), round(found / len(terms), 2)))
    return hits

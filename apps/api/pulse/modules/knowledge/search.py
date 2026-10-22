"""Full-text search engine (FTS5 + BM25 ranking + fallback) over company regulations."""

import re
from typing import Any

from pulse.core import db

STOP_WORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
    "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по",
    "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему",
    "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть",
    "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом",
    "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для",
    "мы", "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз",
    "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому",
    "этого", "какой", "какая", "какое", "какие", "сколько", "каков", "какова", "каковы",
}


def sanitize_terms(query: str) -> list[str]:
    """Extracts search tokens from natural language query, filtering stop words."""
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", query.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) >= 2]


def search_chunks(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Performs FTS5 full-text search with fallback across knowledge chunks."""
    from pulse.modules.knowledge import store

    store.ensure_seeded()
    terms = sanitize_terms(query)
    if not terms:
        return []

    # 1. FTS5 with prefix matching and rank
    fts_expr = " OR ".join(f'"{t}"*' for t in terms)
    results: list[dict[str, Any]] = []

    try:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, doc_title, section, text, rank
                FROM kb_chunks_fts
                WHERE kb_chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_expr, limit),
            ).fetchall()

            for r in rows:
                results.append(
                    {
                        "chunk_id": int(r["chunk_id"]),
                        "title": r["doc_title"],
                        "section": r["section"],
                        "text": r["text"],
                        "score": round(-float(r["rank"]), 2),
                    }
                )
    except Exception:
        results = []

    if results:
        return results

    # 2. Fallback LIKE search if FTS yielded no results
    like_conditions = []
    params: list[Any] = []
    for t in terms[:4]:
        like_conditions.append("(doc_title LIKE ? OR section LIKE ? OR text LIKE ? OR keywords LIKE ?)")
        params.extend([f"%{t}%", f"%{t}%", f"%{t}%", f"%{t}%"])

    if not like_conditions:
        return []

    # Safe parameter substitution where like_conditions contains fixed constant templates
    sql = f"""
        SELECT id, doc_title, section, text
        FROM kb_chunks
        WHERE {" OR ".join(like_conditions)}
        LIMIT ?
    """  # noqa: S608
    params.append(limit)

    with db.connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        for r in rows:
            results.append(
                {
                    "chunk_id": int(r["id"]),
                    "title": r["doc_title"],
                    "section": r["section"],
                    "text": r["text"],
                    "score": 1.0,
                }
            )

    return results

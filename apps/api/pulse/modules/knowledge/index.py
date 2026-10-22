"""Company regulations: markdown corpus → sections → SQLite FTS5 index with Russian stemming.

One chunk is one numbered section of a regulation ("§ 3.2 …"): short enough to quote, long enough to
answer from. SQLite has no Russian stemmer, so stems are computed here and indexed instead of raw words —
"скидку", "скидки" and "скидок" all find "§ 3.1 Скидка, которую даёт менеджер".
"""

import functools
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import snowballstemmer

from pulse.core import db

CORPUS = Path(__file__).parent / "corpus"
WORD = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
# Function words and question words carry no meaning for retrieval.
STOP_WORDS = """
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было
вот от меня еще нет о из ему когда даже ну ли если уже или ни быть был него до вас нибудь уж вам
ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам без раз
тоже себе под будет ж тогда кто этот того потому этого какой какая какое какие сколько каков какова
каковы почему зачем можно нужно нам наш наша наши наше компания компании компанию нас при это эти
эта каким каких какому какую каком делать делают делаем сделать бывает
"""
STOP = frozenset(STOP_WORDS.split())


@functools.cache
def _stemmer() -> snowballstemmer.stemmer:
    return snowballstemmer.stemmer("russian")


def stems(text: str) -> list[str]:
    words = [w.lower() for w in WORD.findall(text)]
    return [s for s in _stemmer().stemWords([w for w in words if w not in STOP]) if len(s) > 1]


@dataclass(frozen=True, slots=True)
class Chunk:
    id: int
    doc: str
    doc_title: str
    category: str
    section: str
    text: str


def parse_corpus(folder: Path = CORPUS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(folder.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = lines[0].removeprefix("# ").strip()
        category = next((ln.split(":", 1)[1].strip() for ln in lines[1:4] if ln.startswith("category:")), "")
        section, body = "", list[str]()
        for line in [*lines[1:], "## "]:
            if line.startswith("## "):
                if section and body:
                    text = " ".join(" ".join(body).split())
                    chunks.append(Chunk(len(chunks) + 1, path.stem, title, category, section, text))
                section, body = line[3:].strip(), []
            elif section and line.strip():
                body.append(line.strip())
    return chunks


def corpus_hash(folder: Path = CORPUS) -> str:
    h = hashlib.sha256()
    for path in sorted(folder.glob("*.md")):
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


SCHEMA = """
DROP TABLE IF EXISTS kb_chunk;
DROP TABLE IF EXISTS kb_fts;
CREATE TABLE kb_chunk (
    id INTEGER PRIMARY KEY,
    doc TEXT NOT NULL,
    doc_title TEXT NOT NULL,
    category TEXT NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE VIRTUAL TABLE kb_fts USING fts5(stems, tokenize = 'unicode61');
"""


_checked: set[tuple[str, str]] = set()  # (database, corpus hash) pairs already verified by this process


def ensure_index() -> None:
    """(Re)build the index when the corpus changed since the last build."""
    current = corpus_hash()
    key = (db.path(), current)
    if key in _checked:
        return
    db.init()
    if db.get_setting("kb_hash") != current:
        _build(current)
    _checked.add(key)


def _build(current: str) -> None:
    chunks = parse_corpus()
    with db.connect() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO kb_chunk(id, doc, doc_title, category, section, text) VALUES (?, ?, ?, ?, ?, ?)",
            [(c.id, c.doc, c.doc_title, c.category, c.section, c.text) for c in chunks],
        )
        conn.executemany(
            "INSERT INTO kb_fts(rowid, stems) VALUES (?, ?)",
            [(c.id, " ".join(stems(f"{c.doc_title} {c.section} {c.text}"))) for c in chunks],
        )
    db.set_setting("kb_hash", current)
    db.set_setting("kb_eval", None)  # the old evaluation is no longer about this corpus


def chunk(chunk_id: int) -> Chunk | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM kb_chunk WHERE id = ?", (chunk_id,)).fetchone()
    return Chunk(row["id"], row["doc"], row["doc_title"], row["category"], row["section"], row["text"]) if row else None


def documents() -> list[dict[str, object]]:
    ensure_index()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT doc, doc_title, category, count(*) AS n FROM kb_chunk GROUP BY doc ORDER BY doc"
        ).fetchall()
    return [{"id": r["doc"], "title": r["doc_title"], "category": r["category"], "chunks": r["n"]} for r in rows]

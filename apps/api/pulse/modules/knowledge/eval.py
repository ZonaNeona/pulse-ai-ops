"""Evaluation of the knowledge base: does retrieval find the right section, and does it refuse when it should?

The suite runs without a model (it checks retrieval and the refusal rule, which are what the answer stands
on), so it is free, deterministic and part of CI. Its result is what the Knowledge screen shows — the
numbers there are measured, not typed in.
"""

from typing import Any

from pulse.core import db
from pulse.modules.knowledge.answer import relevant
from pulse.modules.knowledge.index import corpus_hash, ensure_index, parse_corpus

# question → (document file, section prefix that must be among the top 3)
GOLDEN: list[tuple[str, str, str]] = [
    ("Какую скидку менеджер может дать без согласования?", "01-pricing", "§ 3.1"),
    ("Кто согласует скидку дилеру 10 процентов?", "01-pricing", "§ 3.2"),
    ("Можно ли дать скидку на чиллер под заказ?", "01-pricing", "§ 4.1"),
    ("Какие условия оплаты стандартные?", "01-pricing", "§ 5.1"),
    ("Кому положена отсрочка платежа?", "01-pricing", "§ 5.2"),
    ("Кто подписывает договор на полтора миллиона?", "02-deals", "§ 1.2"),
    ("Через сколько перезвонить клиенту после отправки КП?", "02-deals", "§ 2.2"),
    ("Какая гарантия на монтажные работы?", "03-warranty", "§ 1.1"),
    ("Что не входит в гарантию?", "03-warranty", "§ 2.2"),
    ("Как быстро инженер выезжает в клинику по аварии?", "04-claims", "§ 2.1"),
    ("За сколько нужно зарегистрировать рекламацию?", "04-claims", "§ 1.1"),
    ("Каким давлением делают опрессовку отопления?", "05-installation", "§ 2.1"),
    ("Когда подписывают акт скрытых работ?", "05-installation", "§ 2.2"),
    ("Можно ли отгрузить товар клиенту с долгом?", "06-warehouse", "§ 1.2"),
    ("Сколько держится резерв без оплаты?", "06-warehouse", "§ 1.1"),
    ("Как быстро перезвонить на пропущенный звонок?", "07-sales-standard", "§ 1.1"),
    ("Что спросить при первом звонке клиенту?", "07-sales-standard", "§ 2.1"),
    ("Сколько стоит абонентское обслуживание?", "08-service-contract", "§ 1.2"),
    ("Что делать если сумма счёта больше заказа?", "09-documents", "§ 1.2"),
    ("Какие суточные в командировке?", "10-travel", "§ 1.2"),
]
OUT_OF_SCOPE: list[str] = [
    "Как зовут кота директора?",
    "Какой курс биткоина сегодня?",
    "Кто выиграл чемпионат мира по футболу?",
    "Посоветуй рецепт борща",
    "Сколько этажей в здании офиса?",
]


def run() -> dict[str, Any]:
    ensure_index()
    cases = []
    for question, doc, section in GOLDEN:
        hits = relevant(question)
        found = [f"{h.chunk.doc} {h.chunk.section}" for h in hits]
        ok = any(h.chunk.doc == doc and h.chunk.section.startswith(section) for h in hits[:3])
        cases.append(
            {"question": question, "expected": f"{doc} {section}", "found": found, "passed": ok, "kind": "answer"}
        )
    for question in OUT_OF_SCOPE:
        hits = relevant(question)
        cases.append(
            {
                "question": question,
                "expected": "отказ",
                "found": [f"{h.chunk.doc} {h.chunk.section}" for h in hits],
                "passed": not hits,
                "kind": "refusal",
            }
        )
    answered = [c for c in cases if c["kind"] == "answer"]
    refusals = [c for c in cases if c["kind"] == "refusal"]
    result = {
        "corpus": corpus_hash(),
        "retrievalPassed": sum(bool(c["passed"]) for c in answered),
        "retrievalTotal": len(answered),
        "refusalsCorrect": sum(bool(c["passed"]) for c in refusals),
        "refusalsTotal": len(refusals),
        "cases": cases,
    }
    db.set_setting("kb_eval", result)
    return result


def latest() -> dict[str, Any]:
    cached = db.get_setting("kb_eval")
    if isinstance(cached, dict) and cached.get("corpus") == corpus_hash():
        return cached
    return run()


def stats() -> dict[str, Any]:
    ev = latest()
    chunks = parse_corpus()
    passed, total = ev["retrievalPassed"], ev["retrievalTotal"]
    return {
        "documents": len({c.doc for c in chunks}),
        "chunks": len(chunks),
        "grounded": round(passed / total * 100) if total else 0,
        "evalPassed": passed,
        "evalTotal": total,
        "refusalsCorrect": ev["refusalsCorrect"],
        "refusalsTotal": ev["refusalsTotal"],
    }

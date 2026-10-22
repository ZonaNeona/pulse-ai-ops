"""Golden evaluation benchmark suite for RAG faithfulness, groundedness and refusals."""

import time
from typing import Any

from pulse.core import clock, db
from pulse.modules.knowledge.model import EvalCase, EvalResult
from pulse.modules.knowledge.rag import answer_question

BENCHMARK_CASES: list[EvalCase] = [
    EvalCase(
        id=1,
        question="Какая скидка допустима для дилера без согласования с директором?",
        expected_facts=["7%", "РОП", "12%"],
        is_refusal=False,
        required_sources=["Ценовая политика 2026"],
    ),
    EvalCase(
        id=2,
        question="Какой срок гарантии на монтажные работы?",
        expected_facts=["24 месяца"],
        is_refusal=False,
        required_sources=["Гарантийные обязательства"],
    ),
    EvalCase(
        id=3,
        question="В течение какого времени инженер выезжает на объект по рекламации?",
        expected_facts=["48 часов", "24 часа"],
        is_refusal=False,
        required_sources=["Работа с рекламациями"],
    ),
    EvalCase(
        id=4,
        question="Какое давление используется при опрессовке систем отопления?",
        expected_facts=["1.5", "0.6 МПа"],
        is_refusal=False,
        required_sources=["Стандарт монтажа ВК и ОВ"],
    ),
    EvalCase(
        id=5,
        question="С кем согласовывается скидка от 7% до 12%?",
        expected_facts=["РОП"],
        is_refusal=False,
        required_sources=["Ценовая политика 2026", "Регламент согласования сделок"],
    ),
    EvalCase(
        id=6,
        question="Распространяется ли скидка на оборудование под заказ?",
        expected_facts=["не действует", "не распространяются"],
        is_refusal=False,
        required_sources=["Ценовая политика 2026"],
    ),
    EvalCase(
        id=7,
        question="Какой срок гарантии на поставляемое оборудование?",
        expected_facts=["12", "36 месяцев"],
        is_refusal=False,
        required_sources=["Гарантийные обязательства"],
    ),
    EvalCase(
        id=8,
        question="Когда требуется подписание акта скрытых работ?",
        expected_facts=["до зашивки", "стяжки"],
        is_refusal=False,
        required_sources=["Стандарт монтажа ВК и ОВ"],
    ),
    EvalCase(
        id=9,
        question="В какой срок регистрируется рекламация в CRM?",
        expected_facts=["2 часа"],
        is_refusal=False,
        required_sources=["Работа с рекламациями"],
    ),
    EvalCase(
        id=10,
        question="Каковы обязательные вопросы при первом звонке клиенту?",
        expected_facts=["площадь", "бюджет", "срок"],
        is_refusal=False,
        required_sources=["Скрипты первого звонка"],
    ),
    EvalCase(
        id=11,
        question="При каком условии директор согласует скидку свыше 12%?",
        expected_facts=["предоплата", "50%"],
        is_refusal=False,
        required_sources=["Ценовая политика 2026"],
    ),
    EvalCase(
        id=12,
        question="Кто подписывает акт освидетельствования скрытых работ?",
        expected_facts=["производитель работ", "технадзор"],
        is_refusal=False,
        required_sources=["Стандарт монтажа ВК и ОВ"],
    ),
    EvalCase(
        id=13,
        question="Можно ли отпускать оборудование со склада при наличии задолженности?",
        expected_facts=["запрещен"],
        is_refusal=False,
        required_sources=["Складской регламент"],
    ),
    EvalCase(
        id=14,
        question="В каких случаях может быть отказано в гарантийном ремонте?",
        expected_facts=["самостоятельного", "повреждений", "ТО"],
        is_refusal=False,
        required_sources=["Гарантийные обязательства"],
    ),
    EvalCase(
        id=15,
        question="Каковы требования для перевода сделки на этап 'Счёт выставлен'?",
        expected_facts=["спецификация", "1С"],
        is_refusal=False,
        required_sources=["Регламент согласования сделок"],
    ),
    # 5 Intentional refusal traps
    EvalCase(
        id=16,
        question="Какая марка кофе закупается на кухню офиса?",
        expected_facts=[],
        is_refusal=True,
        required_sources=[],
    ),
    EvalCase(
        id=17,
        question="Предоставляет ли компания кредит сотрудникам на покупку акций?",
        expected_facts=[],
        is_refusal=True,
        required_sources=[],
    ),
    EvalCase(
        id=18,
        question="Каков размер ежемесячной премии за перевыполнение плана у бухгалтерии?",
        expected_facts=[],
        is_refusal=True,
        required_sources=[],
    ),
    EvalCase(
        id=19,
        question="Где скачать взломанную версию AutoCAD?",
        expected_facts=[],
        is_refusal=True,
        required_sources=[],
    ),
    EvalCase(
        id=20,
        question="Каковы правила парковки личных автомобилей на территории офиса?",
        expected_facts=[],
        is_refusal=True,
        required_sources=[],
    ),
]


def run_eval() -> dict[str, Any]:
    """Runs all 20 eval benchmark cases against RAG pipeline and records results."""
    results: list[EvalResult] = []
    t_start = time.perf_counter()

    for case in BENCHMARK_CASES:
        t0 = time.perf_counter()
        resp = answer_question(case.question)
        latency = max(1, int((time.perf_counter() - t0) * 1000))

        if case.is_refusal:
            # Must refuse without sources
            passed = not resp.grounded and len(resp.sources) == 0
            note = "Успешный отказ (вне регламентов)" if passed else "Отказ не сработал"
        else:
            # Must be grounded with citations
            has_sources = resp.grounded and len(resp.sources) > 0
            has_facts = any(fact.lower() in resp.answer.lower() for fact in case.expected_facts)
            passed = has_sources and (has_facts or len(case.expected_facts) == 0)
            note = "Ответ подтвержден источниками" if passed else "Не найдены ключевые факты"

        results.append(
            EvalResult(
                case_id=case.id,
                question=case.question,
                passed=passed,
                is_refusal=case.is_refusal,
                answer=resp.answer,
                latency_ms=latency,
                note=note,
            )
        )

    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    refusals = [r for r in results if r.is_refusal]
    refusals_correct = sum(1 for r in refusals if r.passed)
    duration_ms = int((time.perf_counter() - t_start) * 1000)

    # Persist in SQLite
    now = clock.now().isoformat()
    with db.connect() as conn:
        conn.execute("DELETE FROM kb_eval_results")
        for r in results:
            conn.execute(
                """
                INSERT INTO kb_eval_results(case_id, question, passed, is_refusal, answer, latency_ms, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.case_id,
                    r.question,
                    1 if r.passed else 0,
                    1 if r.is_refusal else 0,
                    r.answer,
                    r.latency_ms,
                    r.note,
                    now,
                ),
            )

    return {
        "total": total,
        "passed": passed_count,
        "passRate": round((passed_count / total) * 100, 1),
        "refusalsTotal": len(refusals),
        "refusalsCorrect": refusals_correct,
        "durationMs": duration_ms,
        "results": [r.to_dict() for r in results],
    }

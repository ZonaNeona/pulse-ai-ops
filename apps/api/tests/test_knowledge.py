"""Knowledge base: retrieval over the regulations, verified citations, honest refusals, measured quality."""

import json

from pulse.core import budget
from pulse.modules import knowledge
from pulse.modules.knowledge.index import parse_corpus
from tests.conftest import Script, reply

DISCOUNT = "Какую скидку менеджер может дать дилеру без согласования?"


def test_corpus_is_split_into_numbered_sections() -> None:
    chunks = parse_corpus()
    assert len({c.doc for c in chunks}) == 10
    assert len(chunks) >= 50
    assert all(c.section.startswith("§ ") and c.text for c in chunks)


def test_golden_set_finds_the_right_section_and_refuses_outside_the_base() -> None:
    result = knowledge.evaluation.run()
    failed = [c["question"] for c in result["cases"] if not c["passed"]]
    assert not failed
    stats = knowledge.evaluation.stats()
    assert (stats["evalPassed"], stats["evalTotal"]) == (20, 20)
    assert (stats["refusalsCorrect"], stats["refusalsTotal"]) == (5, 5)


async def test_without_a_model_the_answer_is_quoted_from_the_regulations() -> None:
    ans = await knowledge.answer(DISCOUNT)
    assert ans.mode == "extract" and ans.grounded
    assert ans.sources[0].title == "Ценовая политика и скидки 2026"
    assert any("7 %" in s.quote for s in ans.sources)
    assert ans.note


async def test_question_outside_the_regulations_is_refused() -> None:
    ans = await knowledge.answer("Какой кофе закупают на кухню офиса?")
    assert ans.mode == "refusal" and not ans.grounded and not ans.sources


async def test_model_answer_keeps_only_citations_it_was_given(model: Script) -> None:
    model.append(reply(json.dumps({"found": True, "answer": "Без согласования — до 7 % [1].", "used": [1]})))
    ans = await knowledge.answer(DISCOUNT, "visitor-a")
    assert ans.mode == "model"
    assert ans.text == "Без согласования — до 7 % [1]."
    assert any(ans.sources[0].quote in c.text for c in parse_corpus()), "quotes are cut from the text by code"
    assert ans.cost_usd == 0.0012
    prompt = model.requests[0]["messages"][0]["content"]
    assert "[1]" in prompt and "Фрагменты" in prompt
    assert budget.summary("visitor-a")["questionsLeft"] == 9


async def test_model_citing_a_fragment_it_was_not_given_falls_back_to_quotes(model: Script) -> None:
    model.append(reply(json.dumps({"found": True, "answer": "Скидка до 15 % [9].", "used": [9]})))
    ans = await knowledge.answer(DISCOUNT)
    assert ans.mode == "extract"
    assert "15 %" not in ans.text
    assert "проверку источников" in ans.note


async def test_provider_failure_does_not_spend_the_visitor_quota(model: Script) -> None:
    ans = await knowledge.answer(DISCOUNT, "visitor-b")  # the script is empty: the provider answers 503
    assert ans.mode == "extract"
    assert budget.summary("visitor-b")["questionsLeft"] == 10

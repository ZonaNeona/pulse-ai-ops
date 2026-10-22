"""Call quality: eight weighted criteria (100 points) and the review screen payload.

In the demo the assessments are produced ahead of time (see `pulse.seed.quality`); in production the same
`Assessment` comes from the model that reads the transcript. Quotes always point at a real transcript line.
"""

import random
from dataclasses import dataclass
from typing import Any

from pulse.seed.call_scripts import SCRIPTS

CRITERIA: list[tuple[str, str, int]] = [
    ("greeting", "Приветствие и представление", 5),
    ("goal", "Цель звонка", 10),
    ("needs", "Выявление потребности", 20),
    ("lpr", "Выход на ЛПР и бюджет", 15),
    ("value", "Ценность решения", 15),
    ("objections", "Работа с возражениями", 10),
    ("next", "Следующий шаг с датой", 15),
    ("tone", "Тон и вежливость", 10),
]
PASS = 60


@dataclass(frozen=True, slots=True)
class Assessment:
    call_id: int
    scenario: str
    level: str
    score: int

    @property
    def id(self) -> int:  # store key
        return self.call_id


def outcome(a: Assessment) -> str:
    return str(SCRIPTS[a.scenario][a.level]["outcome"])


def _criterion_scores(a: Assessment) -> dict[str, int]:
    """Fit the reviewer's per-criterion shares to the call's total score.

    Every share moves by the same amount, so the weak spots of the conversation stay the weakest; the last
    point or two of rounding goes to the criteria that are already the strongest (or are taken from the weakest).
    """
    shares = {k: SCRIPTS[a.scenario][a.level]["criteria"][k][0] for k, _, _ in CRITERIA}

    def fit(shift: float) -> dict[str, int]:
        return {k: round(w * min(1.0, max(0.0, shares[k] + shift))) for k, _, w in CRITERIA}

    low, high = -1.0, 1.0
    for _ in range(40):  # bisection: the total grows monotonically with the shift
        mid = (low + high) / 2
        low, high = (mid, high) if sum(fit(mid).values()) < a.score else (low, mid)
    scores = fit(high)
    diff = a.score - sum(scores.values())
    order = sorted(CRITERIA, key=lambda c: shares[c[0]], reverse=diff > 0)
    for k, _, w in order:
        if diff == 0:
            break
        step = max(-scores[k], min(w - scores[k], diff))
        scores[k] += step
        diff -= step
    return scores


def review(a: Assessment, *, manager: str, duration_s: int) -> dict[str, Any]:
    script = SCRIPTS[a.scenario][a.level]
    first = manager.split()[0]
    lines = [(who, text.replace("{m}", first)) for who, text in script["lines"]]
    weights = [len(t) for _, t in lines]
    spoken = max(len(lines) * 4, duration_s)
    transcript, t = [], 0.0
    quoted = {v[2] for v in script["criteria"].values() if v[2] is not None}
    for i, ((who, text), w) in enumerate(zip(lines, weights, strict=True)):
        transcript.append(
            {"speaker": "manager" if who == "m" else "client", "t": round(t), "text": text, "mark": i in quoted}
        )
        t += spoken * w / sum(weights)
    scores = _criterion_scores(a)
    criteria = []
    for key, label, weight in CRITERIA:
        _, comment, idx = script["criteria"][key]
        item: dict[str, Any] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": scores[key],
            "max": weight,
            "comment": comment,
        }
        if idx is not None:
            item["quote"] = lines[idx][1]
        criteria.append(item)
    rng = random.Random(a.call_id)  # noqa: S311 — a stable waveform picture, not a secret
    waveform = [round(0.2 + abs((i % 17) / 17 - 0.5) * 0.6 + rng.random() * 0.35, 3) for i in range(120)]
    return {
        "summary": script["summary"],
        "advice": script["advice"],
        "criteria": criteria,
        "transcript": transcript,
        "waveform": waveform,
    }

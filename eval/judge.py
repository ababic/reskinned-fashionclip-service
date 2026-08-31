"""Compare a scored image against fixture expectations. No model required."""

from __future__ import annotations

from typing import Any


def _winner(entries: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not entries:
        return None
    return max(entries, key=lambda entry: float(entry["score"]))


def judge_pool(entries: list[dict[str, Any]], expect: dict[str, Any]) -> dict[str, Any]:
    """Score one pool (or subjects) against an expected winner label."""
    top = _winner(entries)
    expected = str(expect["winner"])
    hit = top is not None and str(top["value"]).casefold() == expected.casefold()
    return {
        "expected": expected,
        "actual": None if top is None else str(top["value"]),
        "hit": hit,
        "score": None if top is None else float(top["score"]),
        "gap": None if top is None else float(top.get("gap", 0.0)),
        "p": None if top is None or "p" not in top else float(top["p"]),
    }


def judge_result(scored: dict[str, Any], expect: dict[str, Any]) -> dict[str, Any]:
    """Judge every pool named in ``expect`` plus optional ``subjects``."""
    pools = scored.get("scores") or {}
    judgments: dict[str, Any] = {}
    hits = 0
    total = 0
    for slug, pool_expect in expect.items():
        entries = pools.get(slug) or []
        judgment = judge_pool(list(entries), pool_expect)
        judgments[slug] = judgment
        total += 1
        hits += int(judgment["hit"])
    return {"hit_at_1": hits, "total": total, "pools": judgments}


def summarise_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate hit@1 and mean winner gap across judged fixtures."""
    hits = sum(int(run["judgment"]["hit_at_1"]) for run in runs)
    total = sum(int(run["judgment"]["total"]) for run in runs)
    gaps = [
        float(pool["gap"]) for run in runs for pool in run["judgment"]["pools"].values() if pool.get("gap") is not None
    ]
    return {
        "fixtures": len(runs),
        "hit_at_1": hits,
        "total": total,
        "accuracy": None if total == 0 else round(hits / total, 6),
        "mean_winner_gap": None if not gaps else round(sum(gaps) / len(gaps), 6),
    }


def compare_styles(taxonomy: dict[str, Any], generic: dict[str, Any]) -> dict[str, Any]:
    """Old (generic caption) vs new (aspect captions) on the same fixtures."""
    return {
        "taxonomy": summarise_runs(taxonomy["runs"]),
        "generic": summarise_runs(generic["runs"]),
    }

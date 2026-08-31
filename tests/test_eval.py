from __future__ import annotations

from pathlib import Path

from eval.judge import compare_styles, judge_result, summarise_runs
from eval.run import load_fixtures

_FIXTURES = Path(__file__).resolve().parents[1] / "eval" / "fixtures.jsonl"


def test_load_shipped_fixtures() -> None:
    fixtures = load_fixtures(_FIXTURES)
    assert fixtures[0]["id"] == "shadow-black-leggings"
    assert "pattern" in fixtures[0]["expect"]


def test_judge_result_hit_and_miss() -> None:
    scored = {
        "scores": {
            "pattern": [
                {"value": "Floral", "score": 0.71, "gap": 0.04, "p": 0.62},
                {"value": "Striped", "score": 0.67, "gap": 0.10, "p": 0.28},
            ],
            "subjects": [{"value": "Safari", "score": 0.60, "gap": 0.02}],
        },
    }
    hit = judge_result(scored, {"pattern": {"winner": "Floral"}, "subjects": {"winner": "Safari"}})
    assert hit["hit_at_1"] == 2
    assert hit["pools"]["pattern"]["p"] == 0.62
    miss = judge_result(scored, {"pattern": {"winner": "Plain"}})
    assert miss["hit_at_1"] == 0
    assert miss["pools"]["pattern"]["actual"] == "Floral"


def test_summarise_and_compare_styles() -> None:
    taxonomy = {
        "runs": [
            {
                "judgment": {
                    "hit_at_1": 2,
                    "total": 2,
                    "pools": {
                        "pattern": {"gap": 0.04, "hit": True},
                        "product-type": {"gap": 0.08, "hit": True},
                    },
                }
            }
        ]
    }
    generic = {
        "runs": [
            {
                "judgment": {
                    "hit_at_1": 1,
                    "total": 2,
                    "pools": {
                        "pattern": {"gap": 0.01, "hit": True},
                        "product-type": {"gap": 0.01, "hit": False},
                    },
                }
            }
        ]
    }
    assert summarise_runs(taxonomy["runs"])["accuracy"] == 1.0
    compared = compare_styles(taxonomy, generic)
    assert compared["taxonomy"]["hit_at_1"] == 2
    assert compared["generic"]["hit_at_1"] == 1

"""Score eval fixtures with the live model. Not part of ``just test``.

Usage:
    uv run python -m eval.run
    uv run python -m eval.run --baseline generic
    just eval --out eval/out/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eval.judge import compare_styles, judge_result, summarise_runs
from src.scoring import score_pools_for_image

_DEFAULT_FIXTURES = Path(__file__).resolve().parent / "fixtures.jsonl"
_DEFAULT_TOP_K = 5


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            fixture = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON ({exc})") from exc
        if not isinstance(fixture, dict) or "id" not in fixture or "image_url" not in fixture:
            raise SystemExit(f"{path}:{line_no}: fixture needs id and image_url")
        fixtures.append(fixture)
    return fixtures


def score_fixture(fixture: dict[str, Any], *, caption_style: str, top_k: int) -> dict[str, Any]:
    scored = score_pools_for_image(
        image_url=str(fixture["image_url"]),
        pools=dict(fixture.get("pools") or {}),
        top_k=top_k,
        caption_style=caption_style,
    )
    expect = dict(fixture.get("expect") or {})
    return {
        "id": fixture["id"],
        "image_url": fixture["image_url"],
        "caption_style": caption_style,
        "scored": scored,
        "judgment": judge_result(scored, expect) if expect else {"hit_at_1": 0, "total": 0, "pools": {}},
    }


def run_suite(fixtures: list[dict[str, Any]], *, caption_style: str, top_k: int) -> dict[str, Any]:
    runs = [score_fixture(fixture, caption_style=caption_style, top_k=top_k) for fixture in fixtures]
    return {"caption_style": caption_style, "summary": summarise_runs(runs), "runs": runs}


def _print_summary(label: str, summary: dict[str, Any]) -> None:
    accuracy = summary["accuracy"]
    gap = summary["mean_winner_gap"]
    acc_text = "n/a" if accuracy is None else f"{accuracy:.3f}"
    gap_text = "n/a" if gap is None else f"{gap:.4f}"
    print(
        f"{label}: hit@1 {summary['hit_at_1']}/{summary['total']} "
        f"(accuracy {acc_text}, mean winner gap {gap_text}, fixtures {summary['fixtures']})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score FashionCLIP eval fixtures (not CI).")
    parser.add_argument("--fixtures", type=Path, default=_DEFAULT_FIXTURES)
    parser.add_argument("--out", type=Path, default=None, help="Write the full JSON report here.")
    parser.add_argument(
        "--baseline",
        choices=("none", "generic"),
        default="none",
        help="Also score with the old shared 'a garment with {label}' caption.",
    )
    parser.add_argument("--top-k", type=int, default=_DEFAULT_TOP_K)
    args = parser.parse_args(argv)

    fixtures = load_fixtures(args.fixtures)
    if not fixtures:
        print(f"no fixtures in {args.fixtures}", file=sys.stderr)
        return 1

    taxonomy = run_suite(fixtures, caption_style="taxonomy", top_k=args.top_k)
    report: dict[str, Any] = {"taxonomy": taxonomy}
    _print_summary("taxonomy", taxonomy["summary"])
    for run in taxonomy["runs"]:
        pools = run["judgment"]["pools"]
        bits = [f"{slug}={'HIT' if item['hit'] else 'MISS'}({item['actual']})" for slug, item in pools.items()]
        print(f"  {run['id']}: " + (", ".join(bits) if bits else "no expectations"))

    if args.baseline == "generic":
        generic = run_suite(fixtures, caption_style="generic", top_k=args.top_k)
        report["generic"] = generic
        report["compare"] = compare_styles(taxonomy, generic)
        _print_summary("generic  ", generic["summary"])
        tax_acc = taxonomy["summary"]["accuracy"]
        gen_acc = generic["summary"]["accuracy"]
        if tax_acc is not None and gen_acc is not None:
            print(f"delta accuracy (taxonomy - generic): {tax_acc - gen_acc:+.3f}")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

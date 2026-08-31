from __future__ import annotations

from typing import Any

import pytest
import torch

from src import scoring
from src.scoring import (
    ImageUnavailableError,
    _normalise_to_unit_interval,
    _softmax,
    _with_rank_gaps,
    score_pools_for_image,
)
from src.taxonomies import GRAPHIC_MOTIFS, MODEL_GARMENT_TYPES, graphic_motif_items


def test_normalise_to_unit_interval() -> None:
    assert _normalise_to_unit_interval(-1.0) == 0.0
    assert _normalise_to_unit_interval(1.0) == 1.0
    assert _normalise_to_unit_interval(0.0) == 0.5


def test_softmax_is_stable_and_sums_to_one() -> None:
    assert _softmax([]) == []
    probs = _softmax([1000.0, 1001.0, 999.0])
    assert abs(sum(probs) - 1.0) < 1e-9
    assert probs[1] == max(probs)


def test_rank_gaps_use_the_full_list() -> None:
    ranked = _with_rank_gaps(
        [
            {"value": "Floral", "score": 0.70},
            {"value": "Striped", "score": 0.66},
            {"value": "Plain", "score": 0.51},
        ]
    )
    assert [entry["value"] for entry in ranked] == ["Floral", "Striped", "Plain"]
    assert ranked[0]["gap"] == pytest.approx(0.04)
    assert ranked[1]["gap"] == pytest.approx(0.15)
    assert ranked[2]["gap"] == 0.0


def test_image_unavailable_error() -> None:
    exc = ImageUnavailableError("timeout fetching image")
    assert exc.code == "image_unavailable"
    assert exc.detail == "timeout fetching image"


class _FakeEmbeds:
    def __init__(self, scores: list[float] | None = None) -> None:
        self.scores = scores or []

    def __getitem__(self, idx: int) -> _FakeEmbeds:
        return _FakeEmbeds()

    def norm(self, dim: int | None = None, keepdim: bool = False) -> float:
        return 1.0

    def __truediv__(self, other: object) -> _FakeEmbeds:
        return self

    def __matmul__(self, other: object) -> list[float]:
        return self.scores


def _patch_scoring(monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]) -> None:
    monkeypatch.setattr("src.scoring._image_from_url", lambda *args, **kwargs: object())

    class _Processor:
        def __call__(self, text: list[str], images: object, return_tensors: str, padding: bool) -> dict[str, list[str]]:
            captured.setdefault("prompts", []).append(list(text))
            return {"texts": text}

    class _Model:
        def __call__(self, **batch: object) -> object:
            texts = batch["texts"]
            assert isinstance(texts, list)
            output = type("Output", (), {})()
            output.image_embeds = _FakeEmbeds()
            output.text_embeds = _FakeEmbeds([-0.9 + 0.02 * i for i in range(len(texts))])
            return output

    monkeypatch.setattr("src.scoring._load_clip_components", lambda: (_Model(), _Processor()))


def test_colour_probes_model_space_and_featured_combinations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    result = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={
            "colour": [],
            "pattern": ["Floral", "Striped", "Plain", "Check"],
        },
        top_k=1,
    )
    colour = result["scores"]["colour"]
    by_kind: dict[str, list[str]] = {}
    for entry in colour:
        by_kind.setdefault(str(entry["kind"]), []).append(str(entry["value"]))
    assert "Black" in by_kind["solid"]
    assert "Grey mix" in by_kind["mix"]
    assert "Red mix" in by_kind["mix"]
    assert by_kind["combination"] == ["Silver, Gold and Lilac"]
    assert "Chartreuse" not in by_kind["solid"]
    assert [entry["value"] for entry in result["scores"]["pattern"]] == ["Check"]
    assert "subjects" not in result["scores"]
    assert captured["prompts"][0][0] == "a garment that is black in colour"
    assert any(prompt == "a multicolour garment with grey hues" for prompt in captured["prompts"][0])
    assert captured["prompts"][2][0] == "a garment with a floral pattern"
    pattern = result["scores"]["pattern"]
    assert "p" in pattern[0]
    assert pattern[0]["gap"] > 0
    assert "p" not in colour[0]
    assert "gap" in colour[0]


def test_colour_caller_extras_are_merged_into_model_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    result = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"colour": ["Chartreuse"]},
        top_k=1,
    )
    values = [entry["value"] for entry in result["scores"]["colour"]]
    assert "Chartreuse" in values
    assert "Chartreuse mix" in values
    assert "Black" in values
    assert "subjects" not in result["scores"]


def test_subjects_only_when_pool_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    without = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral", "Striped"]},
        top_k=1,
    )
    assert "subjects" not in without["scores"]
    assert len(captured["prompts"]) == 1

    with_subjects = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral"], "subjects": []},
        top_k=1,
    )
    assert {entry["value"] for entry in with_subjects["scores"]["subjects"]} == set(GRAPHIC_MOTIFS)
    assert captured["prompts"][-1][0] == graphic_motif_items()[0].caption
    assert "p" not in with_subjects["scores"]["subjects"][0]
    assert with_subjects["scores"]["subjects"][0]["gap"] >= 0


def test_product_type_uses_hardcoded_list_when_pool_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    result = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"product-type": []},
        top_k=1,
    )
    types = result["scores"]["product-type"]
    assert {entry["value"] for entry in types} == set(MODEL_GARMENT_TYPES)
    assert "p" in types[0]
    by_value = {entry["value"]: entry for entry in types}
    assert by_value["Dress"]["article"] == "a"
    assert by_value["Trousers"]["article"] == ""
    assert captured["prompts"][0][0] == "a photo of a bag"


def test_shorts_style_is_opt_in_and_returns_distinct_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    without = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral"]},
        top_k=1,
    )
    assert "shorts-style" not in without["scores"]

    with_style = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"shorts-style": []},
        top_k=1,
    )
    values = {entry["value"] for entry in with_style["scores"]["shorts-style"]}
    assert {"Cargo Shorts", "Running Shorts", "Cycling Shorts"} <= values
    assert "p" in with_style["scores"]["shorts-style"][0]
    assert captured["prompts"][-1][0] == "a pair of cargo shorts"


def test_exclusive_softmax_and_gap_survive_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    result = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral", "Striped", "Plain"], "product-type": []},
        top_k=1,
    )
    pattern = result["scores"]["pattern"]
    assert [entry["value"] for entry in pattern] == ["Plain"]
    assert pattern[0]["gap"] == pytest.approx(_normalise_to_unit_interval(-0.86) - _normalise_to_unit_interval(-0.88))
    assert 0.0 < float(pattern[0]["p"]) <= 1.0
    product = result["scores"]["product-type"]
    assert {entry["value"] for entry in product} == set(MODEL_GARMENT_TYPES)
    assert "p" in product[0]
    full_pattern = score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral", "Striped", "Plain"]},
        top_k=5,
    )["scores"]["pattern"]
    assert sum(float(entry["p"]) for entry in full_pattern) == pytest.approx(1.0, abs=1e-5)
    assert full_pattern[0]["value"] == "Plain"


def test_generic_caption_style_uses_the_old_shared_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_scoring(monkeypatch, captured)
    score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"pattern": ["Floral", "Striped"]},
        top_k=2,
        caption_style="generic",
    )
    assert captured["prompts"][0] == ["a garment with floral", "a garment with striped"]
    score_pools_for_image(
        image_url="https://example.com/a.jpg",
        pools={"subjects": []},
        top_k=2,
        caption_style="generic",
    )
    assert captured["prompts"][-1][0] == "a garment with brand logo"


def test_score_pools_for_images_batches_image_inference_and_reuses_text_embeddings(monkeypatch) -> None:
    class FakeProcessor:
        def __call__(self, *, images=None, text=None, return_tensors=None, padding=None):
            if images is not None:
                return {"pixel_values": torch.tensor([[1.0], [2.0]])}
            return {"input_ids": torch.tensor([[1.0, 0.0], [0.0, 1.0]])}

    class FakeModel:
        def __init__(self) -> None:
            self.image_calls = 0
            self.text_calls = 0

        def get_image_features(self, **kwargs):
            self.image_calls += 1
            return torch.tensor([[1.0, 0.0], [0.0, 1.0]])

        def get_text_features(self, **kwargs):
            self.text_calls += 1
            return torch.tensor([[1.0, 0.0], [0.0, 1.0]])

    model = FakeModel()
    scoring._text_embeddings_for_captions.cache_clear()
    monkeypatch.setattr(scoring, "_load_images", lambda image_urls, timeout_seconds: ({0: object(), 1: object()}, {}))
    monkeypatch.setattr(scoring, "_load_clip_components", lambda: (model, FakeProcessor()))

    scores_by_index, errors = scoring.score_pools_for_images(
        image_urls=["https://example.com/a.jpg", "https://example.com/b.jpg"],
        pools={"pattern": ["Floral", "Stripe"]},
        top_k=2,
    )

    assert errors == {}
    assert scores_by_index[0]["pattern"][0]["value"] == "Floral"
    assert scores_by_index[1]["pattern"][0]["value"] == "Stripe"
    assert model.image_calls == 1
    assert model.text_calls == 1

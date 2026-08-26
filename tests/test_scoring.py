from __future__ import annotations

import torch

from src import scoring
from src.scoring import (
    ImageUnavailableError,
    _normalise_to_unit_interval,
    _prompt_for_label,
)


def test_normalise_to_unit_interval() -> None:
    assert _normalise_to_unit_interval(-1.0) == 0.0
    assert _normalise_to_unit_interval(1.0) == 1.0
    assert _normalise_to_unit_interval(0.0) == 0.5


def test_prompt_for_label() -> None:
    assert _prompt_for_label("Floral") == "a garment with Floral"


def test_image_unavailable_error() -> None:
    exc = ImageUnavailableError("timeout fetching image")
    assert exc.code == "image_unavailable"
    assert exc.detail == "timeout fetching image"


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
    scoring._text_embeddings_for_pool.cache_clear()
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

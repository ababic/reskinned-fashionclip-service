from __future__ import annotations

from src.scoring import ImageUnavailableError, _normalise_to_unit_interval, _prompt_for_label


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

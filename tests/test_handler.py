from __future__ import annotations

import json
from typing import Any

import pytest

from src.handler import _parse_batch_request, _parse_request, lambda_handler
from src.scoring import ImageUnavailableError


def test_parse_request_valid() -> None:
    event = {
        "body": json.dumps(
            {
                "images": [{"url": "https://example.com/a.jpg"}],
                "pools": {"pattern": ["Floral", "Stripe"]},
                "top_k": 2,
            }
        )
    }
    parsed = _parse_request(event)
    assert parsed is not None
    urls, pools, top_k = parsed
    assert urls == ["https://example.com/a.jpg"]
    assert pools == {"pattern": ["Floral", "Stripe"]}
    assert top_k == 2


def test_parse_request_rejects_invalid_body() -> None:
    assert _parse_request({"body": "not-json"}) is None
    assert _parse_request({"body": json.dumps({"images": [], "pools": {"x": ["y"]}})}) is None


def test_parse_batch_request_valid() -> None:
    parsed = _parse_batch_request(
        {
            "body": json.dumps(
                {
                    "items": [
                        {"key": "product-1", "images": [{"url": "https://example.com/a.jpg"}]},
                        {"key": "product-2", "images": [{"url": "https://example.com/b.jpg"}]},
                    ],
                    "pools": {"pattern": ["Floral", "Stripe"]},
                    "top_k": 2,
                }
            )
        }
    )

    assert parsed is not None
    jobs, pools, top_k = parsed
    assert [job.key for job in jobs] == ["product-1", "product-2"]
    assert [job.image_urls for job in jobs] == [
        ["https://example.com/a.jpg"],
        ["https://example.com/b.jpg"],
    ]
    assert pools == {"pattern": ["Floral", "Stripe"]}
    assert top_k == 2


def test_parse_batch_request_rejects_duplicate_keys() -> None:
    assert (
        _parse_batch_request(
            {
                "body": json.dumps(
                    {
                        "items": [
                            {"key": "duplicate", "images": [{"url": "https://example.com/a.jpg"}]},
                            {"key": "duplicate", "images": [{"url": "https://example.com/b.jpg"}]},
                        ],
                        "pools": {"pattern": ["Floral"]},
                    }
                )
            }
        )
        is None
    )


def test_lambda_handler_invalid_request() -> None:
    response = lambda_handler({"body": "{}"}, None)
    assert response["statusCode"] == 400


def test_lambda_handler_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_score(*, image_url: str, pools: dict[str, list[str]], top_k: int) -> dict[str, Any]:
        return {"pattern": [{"value": "Floral", "score": 0.9}]}

    monkeypatch.setattr("src.handler.score_pools_for_image", _fake_score)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {"pattern": ["Floral"]},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["results"][0]["scores"]["pattern"][0]["value"] == "Floral"


def test_lambda_handler_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = False

    def _fake_load() -> tuple[object, object]:
        nonlocal loaded
        loaded = True
        return object(), object()

    monkeypatch.setattr("src.handler._load_clip_components", _fake_load)

    response = lambda_handler({"body": json.dumps({"warmup": True})}, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "warm"}
    assert loaded is True


def test_lambda_handler_batch_success_and_image_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_score(
        *,
        image_urls: list[str],
        pools: dict[str, list[str]],
        top_k: int,
    ) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
        assert image_urls == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
        assert pools == {"pattern": ["Floral"]}
        assert top_k == 3
        return (
            {0: {"pattern": [{"value": "Floral", "score": 0.9}]}},
            {1: ImageUnavailableError("http_404")},
        )

    monkeypatch.setattr("src.handler.score_pools_for_images", _fake_score)

    response = lambda_handler(
        {
            "path": "/v1/score-batch",
            "body": json.dumps(
                {
                    "items": [
                        {
                            "key": "product-1",
                            "images": [
                                {"url": "https://example.com/a.jpg"},
                                {"url": "https://example.com/b.jpg"},
                            ],
                        }
                    ],
                    "pools": {"pattern": ["Floral"]},
                }
            ),
        },
        None,
    )

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"][0]["key"] == "product-1"
    assert body["items"][0]["results"][0]["scores"]["pattern"][0]["value"] == "Floral"
    assert body["items"][0]["errors"][0]["error"] == "image_unavailable"


def test_lambda_handler_all_images_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*, image_url: str, pools: dict[str, list[str]], top_k: int) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr("src.handler.score_pools_for_image", _fail)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {"pattern": ["Floral"]},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error"] == "all_images_failed"

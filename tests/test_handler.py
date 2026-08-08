from __future__ import annotations

import json
from typing import Any

import pytest

from src.handler import _parse_request, lambda_handler


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

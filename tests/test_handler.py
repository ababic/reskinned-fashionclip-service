from __future__ import annotations

import json

import pytest

from src.handler import _parse_batch_request, _parse_request, lambda_handler
from src.scoring import ImageUnavailableError


def test_parse_request_valid() -> None:
    event = {
        "body": json.dumps(
            {
                "images": [{"url": "https://example.com/a.jpg"}],
                "options": {"pattern": True, "colour": False},
            }
        )
    }
    parsed = _parse_request(event)
    assert parsed is not None
    urls, enabled = parsed
    assert urls == ["https://example.com/a.jpg"]
    assert enabled == ("pattern",)


def test_parse_request_allows_all_option_slugs() -> None:
    options = {
        slug: True
        for slug in (
            "pattern-application",
            "pattern",
            "embellishment",
            "lustre",
            "appearance",
            "colour",
            "subjects",
            "product-type",
            "sleeve-length",
            "neckline",
            "trouser-length",
            "skirt-length",
            "dress-length",
            "shorts-style",
        )
    }
    event = {"body": json.dumps({"images": [{"url": "https://example.com/a.jpg"}], "options": options})}
    parsed = _parse_request(event)
    assert parsed is not None
    _urls, enabled = parsed
    assert set(enabled) == set(options)


def test_parse_request_accepts_option_aliases() -> None:
    event = {
        "body": json.dumps(
            {
                "images": [{"url": "https://example.com/a.jpg"}],
                "options": {"color": True, "product_type": True},
            }
        )
    }
    parsed = _parse_request(event)
    assert parsed is not None
    _urls, enabled = parsed
    assert set(enabled) == {"colour", "product-type"}


def test_parse_request_rejects_missing_options() -> None:
    assert _parse_request({"body": json.dumps({"images": [{"url": "https://example.com/a.jpg"}]})}) is None


def test_parse_request_rejects_all_false_options() -> None:
    assert (
        _parse_request(
            {
                "body": json.dumps(
                    {
                        "images": [{"url": "https://example.com/a.jpg"}],
                        "options": {"pattern": False},
                    }
                )
            }
        )
        is None
    )


def test_parse_request_rejects_invalid_body() -> None:
    assert _parse_request({"body": "not-json"}) is None
    assert _parse_request({"body": json.dumps({"images": [], "options": {"pattern": True}})}) is None
    assert (
        _parse_request(
            {"body": json.dumps({"images": [{"url": "https://example.com/a.jpg"}], "options": {"pattern": "yes"}})}
        )
        is None
    )


def test_parse_batch_request_valid() -> None:
    parsed = _parse_batch_request(
        {
            "body": json.dumps(
                {
                    "items": [
                        {"key": "product-1", "images": [{"url": "https://example.com/a.jpg"}]},
                        {"key": "product-2", "images": [{"url": "https://example.com/b.jpg"}]},
                    ],
                    "options": {"pattern": True, "colour": True},
                }
            )
        }
    )

    assert parsed is not None
    jobs, enabled, unknown = parsed
    assert [job.key for job in jobs] == ["product-1", "product-2"]
    assert set(enabled) == {"pattern", "colour"}
    assert unknown == []


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
                        "options": {"pattern": True},
                    }
                )
            }
        )
        is None
    )


def test_lambda_handler_invalid_request() -> None:
    response = lambda_handler({"body": "{}"}, None)
    assert response["statusCode"] == 400


def test_lambda_handler_unknown_option() -> None:
    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "options": {"texture": True},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "unknown_option"
    assert "texture" in body["detail"]
    assert "pattern" in body["accepted"]


def test_lambda_handler_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_score(*, image_urls: list[str], enabled_slugs: tuple[str, ...]) -> tuple[dict, dict]:
        del image_urls
        return (
            {0: {slug: [{"value": slug, "score": 0.9}] for slug in enabled_slugs}},
            {},
        )

    monkeypatch.setattr("src.handler.score_pools_for_images", _fake_score)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "options": {
                        "pattern": True,
                        "pattern-application": True,
                        "colour": True,
                        "subjects": True,
                        "product-type": True,
                    },
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    scores = body["results"][0]["scores"]
    assert scores["pattern"][0]["value"] == "pattern"
    assert scores["colour"][0]["value"] == "colour"
    assert scores["product-type"][0]["value"] == "product-type"
    assert scores["subjects"][0]["value"] == "subjects"


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
    def _fake_score(*, image_urls: list[str], enabled_slugs: tuple[str, ...]) -> tuple[dict, dict]:
        assert image_urls == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
        assert enabled_slugs == ("pattern",)
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
                    "options": {"pattern": True},
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


def test_lambda_handler_score_batches_images_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def _fake_score(*, image_urls: list[str], enabled_slugs: tuple[str, ...]) -> tuple[dict, dict]:
        calls.append(image_urls)
        return (
            {
                0: {"pattern": [{"value": "Floral", "score": 0.9}]},
                1: {"pattern": [{"value": "Stripe", "score": 0.8}]},
            },
            {},
        )

    monkeypatch.setattr("src.handler.score_pools_for_images", _fake_score)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [
                        {"url": "https://example.com/a.jpg"},
                        {"url": "https://example.com/b.jpg"},
                    ],
                    "options": {"pattern": True},
                }
            )
        },
        None,
    )

    assert response["statusCode"] == 200
    assert calls == [["https://example.com/a.jpg", "https://example.com/b.jpg"]]
    body = json.loads(response["body"])
    assert len(body["results"]) == 2


def test_lambda_handler_all_images_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*, image_urls: list[str], enabled_slugs: tuple[str, ...]) -> tuple[dict, dict]:
        raise RuntimeError("boom")

    monkeypatch.setattr("src.handler.score_pools_for_images", _fail)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "options": {"pattern": True},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error"] == "all_images_failed"

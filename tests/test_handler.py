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


def test_parse_request_allows_empty_colour_pool() -> None:
    event = {
        "body": json.dumps(
            {
                "images": [{"url": "https://example.com/a.jpg"}],
                "pools": {"colour": []},
            }
        )
    }
    parsed = _parse_request(event)
    assert parsed is not None
    _urls, pools, _top_k = parsed
    assert pools == {"colour": []}


def test_parse_request_allows_empty_catalog_pools() -> None:
    for slug in (
        "colour",
        "subjects",
        "product-type",
        "sleeve-length",
        "neckline",
        "trouser-length",
        "skirt-length",
        "dress-length",
        "shorts-style",
    ):
        event = {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {slug: []},
                }
            )
        }
        parsed = _parse_request(event)
        assert parsed is not None
        _urls, pools, _top_k = parsed
        assert pools == {slug: []}


def test_parse_request_ignores_legacy_graphic_theme_pool() -> None:
    event = {
        "body": json.dumps(
            {
                "images": [{"url": "https://example.com/a.jpg"}],
                "pools": {"graphic-theme": ["Lion"], "pattern": ["Floral"]},
            }
        )
    }
    parsed = _parse_request(event)
    assert parsed is not None
    _urls, pools, _top_k = parsed
    assert pools == {"pattern": ["Floral"]}
    assert (
        _parse_request(
            {"body": json.dumps({"images": [{"url": "https://example.com/a.jpg"}], "pools": {"graphic-theme": []}})}
        )
        is None
    )


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


def test_lambda_handler_unknown_taxonomy() -> None:
    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {"texture": ["Smooth"]},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "unknown_taxonomy"
    assert "texture" in body["detail"]
    assert "pattern" in body["accepted"]
    assert "graphic-theme" not in body["accepted"]


def _fake_batched_scores(
    *,
    image_urls: list[str],
    pools: dict[str, list[str]],
    top_k: int,
) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
    del image_urls, top_k
    return (
        {0: {slug: [{"value": labels[0] if labels else slug, "score": 0.9}] for slug, labels in pools.items()}},
        {},
    )


def test_lambda_handler_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.handler.score_pools_for_images", _fake_batched_scores)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {
                        "pattern": ["Floral"],
                        "pattern-application": ["Placement print"],
                        "colour": [],
                        "subjects": [],
                        "product-type": [],
                    },
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    scores = body["results"][0]["scores"]
    assert scores["pattern"][0]["value"] == "Floral"
    assert "graphic-theme" not in scores
    assert scores["colour"][0]["value"] == "colour"
    assert scores["product-type"][0]["value"] == "product-type"
    assert scores["subjects"][0]["value"] == "subjects"


def test_lambda_handler_accepts_taxonomy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, list[str]] = {}

    def _fake_score(
        *,
        image_urls: list[str],
        pools: dict[str, list[str]],
        top_k: int,
    ) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
        del image_urls, top_k
        seen.update(pools)
        return (
            {0: {slug: [{"value": labels[0] if labels else slug, "score": 0.8}] for slug, labels in pools.items()}},
            {},
        )

    monkeypatch.setattr("src.handler.score_pools_for_images", _fake_score)

    response = lambda_handler(
        {
            "body": json.dumps(
                {
                    "images": [{"url": "https://example.com/a.jpg"}],
                    "pools": {"color": ["Navy"], "product_type": ["Dress"], "graphic_theme": ["Skull"]},
                }
            )
        },
        None,
    )
    assert response["statusCode"] == 200
    assert set(seen) == {"color", "product_type"}


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


def test_lambda_handler_score_batches_images_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def _fake_score(
        *,
        image_urls: list[str],
        pools: dict[str, list[str]],
        top_k: int,
    ) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
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
                    "pools": {"pattern": ["Floral", "Stripe"]},
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
    def _fail(
        *,
        image_urls: list[str],
        pools: dict[str, list[str]],
        top_k: int,
    ) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
        raise RuntimeError("boom")

    monkeypatch.setattr("src.handler.score_pools_for_images", _fail)

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

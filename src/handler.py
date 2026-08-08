"""AWS Lambda handler for /v1/score."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

from src.scoring import ImageUnavailableError, score_pools_for_image

_MAX_IMAGES = 2
_MIN_IMAGES = 1
_DEFAULT_TOP_K = 3
_MAX_TOP_K = 5

_sentry_dsn = (os.environ.get("SENTRY_DSN") or "").strip()
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=(os.environ.get("SENTRY_ENVIRONMENT") or os.environ.get("ENVIRONMENT") or "staging"),
        release=os.environ.get("SENTRY_RELEASE") or None,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
        integrations=[AwsLambdaIntegration(timeout_warning=True)],
        send_default_pii=False,
    )


def _response(status_code: int, body: dict[str, object]) -> dict[str, object]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _is_valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_request(
    event: dict[str, object],
) -> tuple[list[str], dict[str, list[str]], int] | None:
    raw_body = event.get("body")
    if not isinstance(raw_body, str):
        return None
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None

    images = payload.get("images")
    pools = payload.get("pools")
    top_k = payload.get("top_k", _DEFAULT_TOP_K)

    if not isinstance(images, list) or not (_MIN_IMAGES <= len(images) <= _MAX_IMAGES):
        return None
    if not isinstance(pools, dict) or not pools:
        return None
    if not isinstance(top_k, int) or top_k < 1:
        return None

    parsed_images: list[str] = []
    for entry in images:
        if not isinstance(entry, dict):
            return None
        url_value = entry.get("url")
        if not isinstance(url_value, str) or not _is_valid_https_url(url_value):
            return None
        parsed_images.append(url_value)

    parsed_pools: dict[str, list[str]] = {}
    for slug, labels in pools.items():
        if not isinstance(slug, str) or not isinstance(labels, list):
            return None
        clean_labels = [label.strip() for label in labels if isinstance(label, str) and label.strip()]
        if clean_labels:
            parsed_pools[slug] = clean_labels

    if not parsed_pools:
        return None

    return parsed_images, parsed_pools, min(top_k, _MAX_TOP_K)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    parsed = _parse_request(event)
    if parsed is None:
        return _response(400, {"error": "invalid_request"})

    image_urls, pools, top_k = parsed
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []

    for idx, image_url in enumerate(image_urls):
        try:
            scores = score_pools_for_image(image_url=image_url, pools=pools, top_k=top_k)
        except ImageUnavailableError as exc:
            # Expected upstream/data issue (404, timeout, non-image bytes) — return in
            # `errors` for the client, do not alert Sentry.
            errors.append(
                {
                    "image_index": idx,
                    "url": image_url,
                    "error": ImageUnavailableError.code,
                    "detail": exc.detail,
                }
            )
            continue
        except Exception as exc:  # noqa: BLE001 — unexpected per-image failure must not abort the batch
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("vision.image_index", str(idx))
                scope.set_context("vision_image", {"url": image_url, "index": idx})
                sentry_sdk.capture_exception(exc)
            errors.append(
                {
                    "image_index": idx,
                    "url": image_url,
                    "error": "scoring_failed",
                    "detail": str(exc),
                }
            )
            continue
        results.append({"image_index": idx, "url": image_url, "scores": scores})

    if not results:
        return _response(422, {"error": "all_images_failed", "results": [], "errors": errors})

    return _response(200, {"results": results, "errors": errors})

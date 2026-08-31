"""AWS Lambda handler for /v1/score."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

from src.scoring import ImageUnavailableError, _load_clip_components, score_pools_for_images
from src.taxonomies import ACCEPTED_SLUGS, resolve_taxonomy, unknown_option_keys

_MAX_IMAGES = 2
_MAX_BATCH_ITEMS = 16
_MIN_IMAGES = 1


@dataclass(frozen=True, slots=True)
class ScoreJob:
    key: str
    image_urls: list[str]


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


def _parse_payload(event: dict[str, object]) -> dict[str, object] | None:
    raw_body = event.get("body")
    if not isinstance(raw_body, str):
        return None
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_images(raw_images: object, *, max_images: int = _MAX_IMAGES) -> list[str] | None:
    if not isinstance(raw_images, list) or not (_MIN_IMAGES <= len(raw_images) <= max_images):
        return None

    parsed: list[str] = []
    for entry in raw_images:
        if not isinstance(entry, dict):
            return None
        url_value = entry.get("url")
        if not isinstance(url_value, str) or not _is_valid_https_url(url_value):
            return None
        parsed.append(url_value)
    return parsed


def _parse_options(raw_options: object) -> tuple[tuple[str, ...], list[str]] | None:
    """Return enabled canonical slugs and unknown option keys, or None if malformed."""
    if not isinstance(raw_options, dict):
        return None

    unknown = unknown_option_keys(raw_options)
    enabled: list[str] = []
    for key, value in raw_options.items():
        if not isinstance(value, bool):
            return None
        if not value:
            continue
        canonical = resolve_taxonomy(key)
        if canonical is None:
            continue
        if canonical not in enabled:
            enabled.append(canonical)
    if not enabled:
        return None
    return tuple(enabled), unknown


def _unknown_option_response(unknown: list[str]) -> dict[str, object]:
    return _response(
        400,
        {
            "error": "unknown_option",
            "detail": f"unsupported option keys: {', '.join(unknown)}",
            "accepted": list(ACCEPTED_SLUGS),
        },
    )


def _parse_request(event: dict[str, object]) -> tuple[list[str], tuple[str, ...]] | None:
    payload = _parse_payload(event)
    if payload is None:
        return None
    images = _parse_images(payload.get("images"))
    parsed_options = _parse_options(payload.get("options"))
    if images is None or parsed_options is None:
        return None
    enabled_slugs, unknown = parsed_options
    if unknown:
        return None
    return images, enabled_slugs


def _parse_batch_request(event: dict[str, object]) -> tuple[list[ScoreJob], tuple[str, ...], list[str]] | None:
    payload = _parse_payload(event)
    if payload is None:
        return None
    raw_items = payload.get("items")
    parsed_options = _parse_options(payload.get("options"))
    if not isinstance(raw_items, list) or not (1 <= len(raw_items) <= _MAX_BATCH_ITEMS):
        return None
    if parsed_options is None:
        return None

    enabled_slugs, unknown = parsed_options
    jobs: list[ScoreJob] = []
    seen_keys: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            return None
        key = raw_item.get("key")
        if not isinstance(key, str) or not key.strip() or key in seen_keys:
            return None
        image_urls = _parse_images(raw_item.get("images"))
        if image_urls is None:
            return None
        seen_keys.add(key)
        jobs.append(ScoreJob(key=key, image_urls=image_urls))
    return jobs, enabled_slugs, unknown


def _score_one_request(
    image_urls: list[str],
    enabled_slugs: tuple[str, ...],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []

    try:
        scores_by_index, image_errors = score_pools_for_images(
            image_urls=image_urls,
            enabled_slugs=enabled_slugs,
        )
    except Exception as exc:  # noqa: BLE001 — one model failure must produce a useful response
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("vision.operation", "score")
            sentry_sdk.capture_exception(exc)
        return [], [
            {
                "image_index": idx,
                "url": image_url,
                "error": "scoring_failed",
                "detail": str(exc),
            }
            for idx, image_url in enumerate(image_urls)
        ]

    for idx, image_url in enumerate(image_urls):
        if idx in image_errors:
            error = image_errors[idx]
            errors.append(
                {
                    "image_index": idx,
                    "url": image_url,
                    "error": ImageUnavailableError.code,
                    "detail": error.detail,
                }
            )
            continue
        scores = scores_by_index.get(idx)
        if scores is None:
            continue
        results.append({"image_index": idx, "url": image_url, "scores": scores})
    return results, errors


def _score_batch_request(
    jobs: list[ScoreJob],
    enabled_slugs: tuple[str, ...],
) -> tuple[list[dict[str, object]], int]:
    locations = [
        (job_index, image_index, image_url)
        for job_index, job in enumerate(jobs)
        for image_index, image_url in enumerate(job.image_urls)
    ]
    try:
        scores_by_index, image_errors = score_pools_for_images(
            image_urls=[location[2] for location in locations],
            enabled_slugs=enabled_slugs,
        )
    except Exception as exc:  # noqa: BLE001 — one model failure must produce a useful batch response
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("vision.operation", "batch")
            sentry_sdk.capture_exception(exc)
        return [
            {
                "key": job.key,
                "results": [],
                "errors": [
                    {
                        "image_index": image_index,
                        "url": image_url,
                        "error": "scoring_failed",
                        "detail": str(exc),
                    }
                    for image_index, image_url in enumerate(job.image_urls)
                ],
            }
            for job in jobs
        ], 0

    items: list[dict[str, object]] = []
    successful_images = 0
    for job_index, job in enumerate(jobs):
        item_results: list[dict[str, object]] = []
        item_errors: list[dict[str, object]] = []
        for flat_index, (location_job_index, image_index, image_url) in enumerate(locations):
            if location_job_index != job_index:
                continue
            if flat_index in image_errors:
                error = image_errors[flat_index]
                item_errors.append(
                    {
                        "image_index": image_index,
                        "url": image_url,
                        "error": ImageUnavailableError.code,
                        "detail": error.detail,
                    }
                )
                continue
            item_scores = scores_by_index.get(flat_index)
            if item_scores is None:
                continue
            successful_images += 1
            item_results.append({"image_index": image_index, "url": image_url, "scores": item_scores})
        items.append({"key": job.key, "results": item_results, "errors": item_errors})
    return items, successful_images


def _warm_up() -> dict[str, object]:
    try:
        _load_clip_components()
    except Exception as exc:  # noqa: BLE001 — return a useful health response to the deploy smoke test
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("vision.operation", "warmup")
            sentry_sdk.capture_exception(exc)
        return _response(503, {"error": "warmup_failed"})
    return _response(200, {"status": "warm"})


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    payload = _parse_payload(event)
    if payload is None:
        return _response(400, {"error": "invalid_request"})
    if payload.get("warmup") is True:
        return _warm_up()

    path = event.get("path") or event.get("rawPath")
    if path == "/v1/score-batch":
        parsed_batch = _parse_batch_request(event)
        if parsed_batch is None:
            return _response(400, {"error": "invalid_request"})
        jobs, enabled_slugs, unknown = parsed_batch
        if unknown:
            return _unknown_option_response(unknown)
        items, successful_images = _score_batch_request(jobs, enabled_slugs)
        if not successful_images:
            return _response(422, {"error": "all_images_failed", "items": items})
        return _response(200, {"items": items})

    parsed = _parse_request(event)
    if parsed is None:
        payload = _parse_payload(event)
        if payload is not None and isinstance(payload.get("options"), dict):
            unknown = unknown_option_keys(payload["options"])
            if unknown:
                return _unknown_option_response(unknown)
        return _response(400, {"error": "invalid_request"})
    image_urls, enabled_slugs = parsed
    results, errors = _score_one_request(image_urls, enabled_slugs)

    if not results:
        return _response(422, {"error": "all_images_failed", "results": [], "errors": errors})

    return _response(200, {"results": results, "errors": errors})

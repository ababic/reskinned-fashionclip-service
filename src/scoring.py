"""FashionCLIP scoring helpers for the /v1/score endpoint."""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from io import BytesIO
from typing import Any

import requests
import torch
from PIL import Image, UnidentifiedImageError

from src.taxonomies import (
    APPEARANCE_MEMBER_SLUGS,
    GRAPHIC_MOTIFS,
    MODEL_COLOURS,
    MODEL_EMBELLISHMENTS,
    MODEL_GARMENT_TYPES,
    MODEL_LUSTRES,
    MODEL_PATTERN_APPLICATIONS,
    MODEL_PATTERNS,
    STYLE_POOLS,
    ScoreItem,
    colour_combination_items,
    featured_solid_colours,
    pool_is_exclusive,
    prompts_for_pool,
    resolve_taxonomy,
)

# Baked into the Lambda image by the Dockerfile; falls back to HF hub for local runs.
_DEFAULT_MODEL_ID = "patrickjohncyh/fashion-clip"


class ImageUnavailableError(Exception):
    """Expected failure fetching or decoding a remote garment image (not a service bug)."""

    code = "image_unavailable"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _normalise_to_unit_interval(raw_score: float) -> float:
    """Map cosine-style scores from [-1, 1] to [0, 1]."""
    return max(0.0, min(1.0, (raw_score + 1.0) / 2.0))


def _softmax(values: list[float]) -> list[float]:
    """Numerically stable softmax; empty input stays empty."""
    if not values:
        return []
    peak = max(values)
    exps = [math.exp(value - peak) for value in values]
    total = sum(exps)
    return [value / total for value in exps]


def _logit_scale(model: Any) -> float:
    """CLIP temperature for exclusive-pool softmax; 100 matches the usual CLIP demo."""
    scale = getattr(model, "logit_scale", None)
    if scale is None:
        return 100.0
    value = scale.exp() if hasattr(scale, "exp") else scale
    return float(value.item() if hasattr(value, "item") else value)


def _with_rank_gaps(entries: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    """Sort by mapped cosine and set gap to the next label in this full list."""
    ranked = sorted(entries, key=lambda entry: float(entry["score"]), reverse=True)
    annotated: list[dict[str, float | str]] = []
    for index, entry in enumerate(ranked):
        item = dict(entry)
        nxt = ranked[index + 1] if index + 1 < len(ranked) else None
        item["gap"] = round(float(entry["score"]) - float(nxt["score"]), 6) if nxt is not None else 0.0
        annotated.append(item)
    return annotated


@lru_cache(maxsize=1)
def _load_clip_components() -> tuple[Any, Any]:
    """Load model + processor lazily for Lambda warm invocations."""
    # Lambda arm64: torch 2.13+ can fail importing distributed RPC (RpcBackendOptions).
    # Pin torch<2.6 in pyproject; these env vars add belt-and-braces for warm starts.
    os.environ.setdefault("TORCH_DISABLE_SHARE_RDZV_TCP_STORE", "1")

    from transformers import CLIPModel, CLIPProcessor

    model_id = os.environ.get("FASHIONCLIP_MODEL_DIR") or _DEFAULT_MODEL_ID
    local_only = bool(os.environ.get("FASHIONCLIP_MODEL_DIR"))
    model = CLIPModel.from_pretrained(model_id, local_files_only=local_only)
    processor = CLIPProcessor.from_pretrained(model_id, local_files_only=local_only)
    return model, processor


def _image_from_url(image_url: str, timeout_seconds: float) -> Image.Image:
    try:
        response = requests.get(image_url, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ImageUnavailableError("timeout fetching image") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        raise ImageUnavailableError(f"http_{status}" if status is not None else "http_error") from exc
    except requests.RequestException as exc:
        raise ImageUnavailableError("request_failed") from exc

    try:
        return Image.open(BytesIO(response.content)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ImageUnavailableError("unidentified_image") from exc
    except OSError as exc:
        raise ImageUnavailableError("image_decode_failed") from exc


def _load_images(
    image_urls: list[str],
    timeout_seconds: float,
) -> tuple[dict[int, Image.Image], dict[int, ImageUnavailableError]]:
    """Fetch image URLs concurrently while preserving per-image failures."""
    images: dict[int, Image.Image] = {}
    errors: dict[int, ImageUnavailableError] = {}
    max_workers = min(4, len(image_urls))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_image_from_url, image_url, timeout_seconds): index
            for index, image_url in enumerate(image_urls)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                images[index] = future.result()
            except ImageUnavailableError as exc:
                errors[index] = exc
    return images, errors


def _entries_for_items(
    items: list[ScoreItem],
    raw_cosines: list[float],
    *,
    exclusive: bool,
    model: Any,
) -> list[dict[str, float | str]]:
    probabilities = _softmax([cosine * _logit_scale(model) for cosine in raw_cosines]) if exclusive else None
    entries: list[dict[str, float | str]] = []
    for index, item in enumerate(items):
        entry: dict[str, float | str] = {
            "value": item.value,
            "score": round(_normalise_to_unit_interval(raw_cosines[index]), 6),
        }
        if probabilities is not None:
            entry["p"] = round(probabilities[index], 6)
        if item.kind is not None:
            entry["kind"] = item.kind
        if item.article is not None:
            entry["article"] = item.article
        entries.append(entry)
    return entries


def _score_items(
    model: Any,
    processor: Any,
    image: Image.Image,
    items: list[ScoreItem],
    *,
    exclusive: bool = False,
) -> list[dict[str, float | str]]:
    if not items:
        return []
    batch = processor(
        text=[item.caption for item in items],
        images=image,
        return_tensors="pt",
        padding=True,
    )
    output = model(**batch)
    image_embedding = output.image_embeds[0]
    text_embeddings = output.text_embeds
    image_embedding = image_embedding / image_embedding.norm()
    text_embeddings = text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)
    raw_cosines = [float(score) for score in text_embeddings @ image_embedding]
    return _entries_for_items(items, raw_cosines, exclusive=exclusive, model=model)


def _generic_items(labels: list[str]) -> list[ScoreItem]:
    """Pre-taxonomy caption used as the eval baseline: ``a garment with {label}``."""
    items: list[ScoreItem] = []
    for label in labels:
        key = " ".join(label.replace("_", " ").split()).casefold()
        items.append(ScoreItem(label, f"a garment with {key}"))
    return items


def _catalog_labels_for_pool(slug: str) -> list[str]:
    canonical = resolve_taxonomy(slug)
    if canonical == "colour":
        return list(MODEL_COLOURS)
    if canonical == "product-type":
        return list(MODEL_GARMENT_TYPES)
    if canonical == "pattern":
        return list(MODEL_PATTERNS)
    if canonical == "pattern-application":
        return list(MODEL_PATTERN_APPLICATIONS)
    if canonical == "embellishment":
        return list(MODEL_EMBELLISHMENTS)
    if canonical == "lustre":
        return list(MODEL_LUSTRES)
    if canonical == "appearance":
        return [label for member in APPEARANCE_MEMBER_SLUGS for label in _catalog_labels_for_pool(member)]
    if canonical == "subjects":
        return list(GRAPHIC_MOTIFS)
    if canonical in STYLE_POOLS:
        return [value for value, _caption in STYLE_POOLS[canonical]]
    return []


def _items_for_pool(slug: str, caption_style: str) -> list[ScoreItem]:
    if caption_style == "generic":
        return _generic_items(_catalog_labels_for_pool(slug))
    return prompts_for_pool(slug)


def _score_colour_opinion(
    model: Any,
    processor: Any,
    image: Image.Image,
    *,
    caption_style: str = "taxonomy",
) -> list[dict[str, float | str]]:
    """Probe FashionCLIP's colour space, then score mixes and featured combinations."""
    items = _items_for_pool("colour", caption_style)
    first_pass = _score_items(model, processor, image, items)
    if caption_style == "generic":
        return _with_rank_gaps(first_pass)
    featured = featured_solid_colours(first_pass)
    combined = first_pass + _score_items(model, processor, image, colour_combination_items(featured))
    return _with_rank_gaps(combined)


def _rank_pool(
    model: Any,
    processor: Any,
    image: Image.Image,
    slug: str,
    caption_style: str,
) -> list[dict[str, float | str]]:
    if resolve_taxonomy(slug) == "colour":
        return _score_colour_opinion(model, processor, image, caption_style=caption_style)
    return _with_rank_gaps(
        _score_items(
            model,
            processor,
            image,
            _items_for_pool(slug, caption_style),
            exclusive=pool_is_exclusive(slug),
        )
    )


@lru_cache(maxsize=64)
def _text_embeddings_for_captions(captions: tuple[str, ...]) -> Any:
    """Cache normalized text embeddings for repeated caption tuples in warm Lambdas."""
    model, processor = _load_clip_components()
    text_inputs = processor(text=list(captions), return_tensors="pt", padding=True)
    with torch.inference_mode():
        text_embeddings = model.get_text_features(**text_inputs)
    return text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)


def _score_loaded_images(
    images: dict[int, Image.Image],
    enabled_slugs: tuple[str, ...],
    caption_style: str,
) -> dict[int, dict[str, list[dict[str, float | str]]]]:
    """Score already-fetched images in one Torch batch, reusing text embeddings per pool."""
    model, processor = _load_clip_components()
    ordered_indices = sorted(images)
    image_batch = processor(images=[images[index] for index in ordered_indices], return_tensors="pt")
    with torch.inference_mode():
        image_embeddings = model.get_image_features(**image_batch)
    image_embeddings = image_embeddings / image_embeddings.norm(dim=-1, keepdim=True)

    scores_by_index: dict[int, dict[str, list[dict[str, float | str]]]] = {index: {} for index in ordered_indices}
    for slug in enabled_slugs:
        if resolve_taxonomy(slug) == "colour":
            for image_index in ordered_indices:
                scores_by_index[image_index][slug] = _score_colour_opinion(
                    model,
                    processor,
                    images[image_index],
                    caption_style=caption_style,
                )
            continue
        items = _items_for_pool(slug, caption_style)
        if not items:
            continue
        text_embeddings = _text_embeddings_for_captions(tuple(item.caption for item in items))
        cosine_scores = image_embeddings @ text_embeddings.T
        exclusive = pool_is_exclusive(slug)
        for row_index, image_index in enumerate(ordered_indices):
            scores_by_index[image_index][slug] = _with_rank_gaps(
                _entries_for_items(
                    items,
                    [float(score) for score in cosine_scores[row_index]],
                    exclusive=exclusive,
                    model=model,
                )
            )
    return scores_by_index


def score_pools_for_images(
    *,
    image_urls: list[str],
    enabled_slugs: tuple[str, ...],
    timeout_seconds: float = 20.0,
    caption_style: str = "taxonomy",
) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
    """Return batched scores and per-image fetch errors."""
    if caption_style not in {"taxonomy", "generic"}:
        raise ValueError(f"unsupported caption_style: {caption_style}")
    if not image_urls or not enabled_slugs:
        return {}, {}
    images, errors = _load_images(image_urls, timeout_seconds)
    if not images:
        return {}, errors
    return _score_loaded_images(images, enabled_slugs, caption_style), errors


def score_pools_for_image(
    *,
    image_url: str,
    enabled_slugs: tuple[str, ...],
    timeout_seconds: float = 20.0,
    caption_style: str = "taxonomy",
) -> dict[str, object]:
    """Score only the classifiers enabled in the request.

    Each enabled slug uses a service-owned vocabulary. Exclusive pools attach
    softmax ``p``; every ranked list attaches ``gap`` against the full pool.
    """
    if caption_style not in {"taxonomy", "generic"}:
        raise ValueError(f"unsupported caption_style: {caption_style}")

    image = _image_from_url(image_url, timeout_seconds)
    model, processor = _load_clip_components()

    scored_pools: dict[str, list[dict[str, float | str]]] = {}
    for slug in enabled_slugs:
        scored_pools[slug] = _rank_pool(model, processor, image, slug, caption_style)

    return {"scores": scored_pools}

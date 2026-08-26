"""FashionCLIP scoring helpers for the /v1/score endpoint."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from io import BytesIO
from typing import Any

import requests
import torch
from PIL import Image, UnidentifiedImageError

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


def _prompt_for_label(label: str) -> str:
    return f"a garment with {label}"


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


@lru_cache(maxsize=64)
def _text_embeddings_for_pool(slug: str, labels: tuple[str, ...]) -> Any:
    """Cache normalized text embeddings for repeated label pools in warm Lambdas."""
    model, processor = _load_clip_components()
    prompts = [_prompt_for_label(label) for label in labels]
    text_inputs = processor(text=prompts, return_tensors="pt", padding=True)
    with torch.inference_mode():
        text_embeddings = model.get_text_features(**text_inputs)
    return text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)


def _score_loaded_images(
    images: dict[int, Image.Image],
    pools: dict[str, list[str]],
    top_k: int,
) -> dict[int, dict[str, list[dict[str, float | str]]]]:
    """Score already-fetched images in one Torch batch, reusing text embeddings per pool."""
    model, processor = _load_clip_components()
    ordered_indices = sorted(images)
    image_batch = processor(images=[images[index] for index in ordered_indices], return_tensors="pt")
    with torch.inference_mode():
        image_embeddings = model.get_image_features(**image_batch)
    image_embeddings = image_embeddings / image_embeddings.norm(dim=-1, keepdim=True)

    scores_by_index: dict[int, dict[str, list[dict[str, float | str]]]] = {
        index: {} for index in ordered_indices
    }
    for slug, labels in pools.items():
        if not labels:
            continue
        text_embeddings = _text_embeddings_for_pool(slug, tuple(labels))
        cosine_scores = image_embeddings @ text_embeddings.T
        for row_index, image_index in enumerate(ordered_indices):
            ranked = sorted(
                (
                    {
                        "value": label,
                        "score": round(_normalise_to_unit_interval(float(score)), 6),
                    }
                    for label, score in zip(labels, cosine_scores[row_index], strict=True)
                ),
                key=lambda entry: float(entry["score"]),
                reverse=True,
            )
            scores_by_index[image_index][slug] = ranked[:top_k]
    return scores_by_index


def score_pools_for_images(
    *,
    image_urls: list[str],
    pools: dict[str, list[str]],
    top_k: int,
    timeout_seconds: float = 20.0,
) -> tuple[dict[int, dict[str, list[dict[str, float | str]]]], dict[int, ImageUnavailableError]]:
    """Return batched scores and per-image fetch errors."""
    if not image_urls or not pools:
        return {}, {}
    images, errors = _load_images(image_urls, timeout_seconds)
    if not images:
        return {}, errors
    return _score_loaded_images(images, pools, top_k), errors


def score_pools_for_image(
    *,
    image_url: str,
    pools: dict[str, list[str]],
    top_k: int,
    timeout_seconds: float = 20.0,
) -> dict[str, list[dict[str, float | str]]]:
    """Return top-k ranked labels per pool for one image URL."""
    scores_by_index, errors = score_pools_for_images(
        image_urls=[image_url],
        pools=pools,
        top_k=top_k,
        timeout_seconds=timeout_seconds,
    )
    if 0 in errors:
        raise errors[0]
    return scores_by_index.get(0, {})

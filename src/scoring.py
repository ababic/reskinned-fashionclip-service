"""FashionCLIP scoring helpers for the /v1/score endpoint."""

from __future__ import annotations

import os
from functools import lru_cache
from io import BytesIO
from typing import Any

import requests
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


def score_pools_for_image(
    *,
    image_url: str,
    pools: dict[str, list[str]],
    top_k: int,
    timeout_seconds: float = 20.0,
) -> dict[str, list[dict[str, float | str]]]:
    """Return top-k ranked labels per pool for one image URL."""
    image = _image_from_url(image_url, timeout_seconds)
    model, processor = _load_clip_components()

    scored_pools: dict[str, list[dict[str, float | str]]] = {}
    for slug, labels in pools.items():
        if not labels:
            continue
        prompts = [_prompt_for_label(label) for label in labels]
        batch = processor(text=prompts, images=image, return_tensors="pt", padding=True)
        output = model(**batch)
        image_embedding = output.image_embeds[0]
        text_embeddings = output.text_embeds
        image_embedding = image_embedding / image_embedding.norm()
        text_embeddings = text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)
        cosine_scores = text_embeddings @ image_embedding

        ranked = sorted(
            (
                {
                    "value": label,
                    "score": round(_normalise_to_unit_interval(float(score)), 6),
                }
                for label, score in zip(labels, cosine_scores, strict=True)
            ),
            key=lambda entry: float(entry["score"]),
            reverse=True,
        )
        scored_pools[slug] = ranked[:top_k]

    return scored_pools

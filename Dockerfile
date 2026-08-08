# syntax=docker/dockerfile:1

# Build stage: CPU torch + FashionCLIP weights (arm64 Lambda).
FROM public.ecr.aws/lambda/python:3.12-arm64 AS builder

WORKDIR /var/task

RUN dnf install -y git findutils && dnf clean all

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

# Bake FashionCLIP as safetensors only (offline at runtime).
ARG HF_TOKEN
RUN --mount=type=secret,id=hf_token,required=false \
    export HF_TOKEN="${HF_TOKEN:-$(cat /run/secrets/hf_token 2>/dev/null || true)}" && \
    uv run python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="patrickjohncyh/fashion-clip",
    local_dir="/var/task/models/fashion-clip",
    allow_patterns=[
        "config.json",
        "model.safetensors",
        "processor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
    ],
)
PY

# Strip build cruft to keep the image slim.
RUN rm -rf /root/.cache/huggingface \
    && find /var/task/.venv -type d -name tests -prune -exec rm -rf {} + \
    && rm -rf /var/task/.venv/lib/python3.12/site-packages/torch/include

# Runtime stage: copy venv + baked model only.
FROM public.ecr.aws/lambda/python:3.12-arm64

WORKDIR /var/task

ENV PATH=/var/task/.venv/bin:/var/lang/bin:/usr/local/bin:/usr/bin/:/bin:/opt/bin \
    VIRTUAL_ENV=/var/task/.venv \
    PYTHONPATH=/var/task/.venv/lib/python3.12/site-packages \
    FASHIONCLIP_MODEL_DIR=/var/task/models/fashion-clip \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    TORCH_DISABLE_SHARE_RDZV_TCP_STORE=1

COPY --from=builder /var/task/.venv /var/task/.venv
COPY --from=builder /var/task/models /var/task/models

CMD ["src.handler.lambda_handler"]

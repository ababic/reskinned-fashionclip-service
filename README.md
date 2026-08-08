# Reskinned FashionCLIP Service

AWS Lambda HTTP scorer for Reskinned **print / pattern classification**. Inventory posts product image URLs + label pools; this service returns ranked FashionCLIP scores only.

Sibling consumer: [`wearecrew/reskinned-inventory`](https://github.com/wearecrew/reskinned-inventory) (`PRINT_VISION_URL` / `PRINT_VISION_API_KEY`).

| | |
|---|---|
| Runtime | Python 3.12 Lambda container (`arm64`) |
| Region | `eu-west-1` |
| Package manager | [uv](https://docs.astral.sh/uv/) + locked `uv.lock` |
| Lint / format | [Ruff](https://docs.astral.sh/ruff/) |
| Observability | [Sentry](https://crew.sentry.io/projects/reskinned-fashionclip-service/) |
| Infra | Terraform (API Gateway REST + Lambda + ECR + API key) |

> **Note:** This repository was reconstructed from the deployed ECR Lambda image and live AWS resource configuration (Aug 2026). Terraform describes existing staging/production stacks; import state before applying changes — see [`terraform/README.md`](terraform/README.md).

---

## Quick start

```bash
brew install uv just   # macOS example

cp .env.template .env  # optional HF_TOKEN / SENTRY_DSN for local work
uv sync --group dev
just test
just lint
```

---

## API

- **Method:** `POST` only
- **Path:** `/v1/score`
- **Auth:** `x-api-key: <PRINT_VISION_API_KEY>` (API Gateway key required)
- **Contract:** [`openapi/v1-score.yaml`](openapi/v1-score.yaml)

```bash
curl -sS -X POST "$PRINT_VISION_URL" \
  -H "content-type: application/json" \
  -H "x-api-key: $PRINT_VISION_API_KEY" \
  -d '{
    "images": [{"url": "https://example.com/garment.jpg"}],
    "pools": {"pattern": ["Floral", "Stripe", "Plain"]},
    "top_k": 3
  }'
```

Behaviour notes:

- 1–2 images per request; per-image failures are isolated (partial `200` with `errors`, or `422` if all fail).
- Thresholding / agreement / promotion stay in **inventory**, not here.
- Model weights are **baked into the image**; runtime is offline to Hugging Face (`HF_HUB_OFFLINE=1`).

---

## Deploy

```bash
just build-image environment=reskinned-fashionclip-service-staging
just push-image environment=reskinned-fashionclip-service-staging
just update-lambda
```

Production: swap `environment=reskinned-fashionclip-service-production`.

---

## Known issue fixed in this repo

Production was failing with `Could not import module 'CLIPModel'` / `RpcBackendOptions` on **torch 2.13.0+cpu** in Lambda arm64 ([Sentry RESKINNED-FASHIONCLIP-SERVICE-3](https://crew.sentry.io/issues/RESKINNED-FASHIONCLIP-SERVICE-3)). This repo pins **torch 2.5.1** (CPU index) and sets `TORCH_DISABLE_SHARE_RDZV_TCP_STORE=1`.

---

## Boundary with inventory

| This service | Inventory |
|--------------|-----------|
| FashionCLIP scores for label pools | Orchestrator / Celery / product flags |
| API key auth at API Gateway | `PRINT_VISION_*` settings + client |
| Sentry on Lambda | Sentry on Heroku warehouse apps |

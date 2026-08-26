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

To warm the model without downloading or scoring an image, send a single request with
`{"warmup": true}` to the same endpoint. The response is `{"status": "warm"}` after
the model has loaded.

For throughput-sensitive callers, `/v1/score-batch` accepts up to 16 product items
per request. Each item has a caller-supplied `key` and one or two image URLs; `pools`
are shared by the whole request:

```bash
curl -sS -X POST "$PRINT_VISION_BATCH_URL" \
  -H "content-type: application/json" \
  -H "x-api-key: $PRINT_VISION_API_KEY" \
  -d '{
    "items": [
      {"key": "product-1", "images": [{"url": "https://example.com/a.jpg"}]},
      {"key": "product-2", "images": [{"url": "https://example.com/b.jpg"}]}
    ],
    "pools": {"pattern": ["Floral", "Stripe"]},
    "top_k": 3
  }'
```

Behaviour notes:

- Single-item requests accept 1–2 images; per-image failures are isolated (partial `200` with `errors`, or `422` if all fail).
- Batch requests return per-item results and errors and preserve the supplied item keys.
- Thresholding / agreement / promotion stay in **inventory**, not here.
- Model weights are **baked into the image**; runtime is offline to Hugging Face (`HF_HUB_OFFLINE=1`).

---

## Deploy

| Branch | Target |
|--------|--------|
| `staging` | Staging Lambda + ECR (`reskinned-fashionclip-service-staging`) |
| `main` | Production Lambda + ECR (`reskinned-fashionclip-service-production`) |

Pushes to those branches run **Test** then **Deploy** via GitHub Actions. One-time setup: apply `terraform/ci` and configure repository variables — see [`terraform/ci/README.md`](terraform/ci/README.md).

Manual deploy:

```bash
just build-image environment=reskinned-fashionclip-service-staging
just push-image environment=reskinned-fashionclip-service-staging
just update-lambda
```

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

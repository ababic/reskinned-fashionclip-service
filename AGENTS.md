# AGENTS.md — Reskinned FashionCLIP Service

Lambda-side print-vision scorer. Inventory owns promotion policy (`PRINT_VISION_*`). Optional classifiers: `subjects`, `colour`, `product-type`, `embellishment` (service-owned vocabs; see `docs/api.md`).

## Commands

Open **`reskinned-fashionclip-service.code-workspace`** in Cursor for editor settings (Python, Ruff, pytest).

```bash
uv sync --group dev
just test
just lint
just eval           # optional live-model fixture harness; not CI
just build-image    # arm64 Docker; optional HF_TOKEN in .env
```

## Layout

| Path | Role |
|------|------|
| `src/handler.py` | API Gateway Lambda entry (`/v1/score`) |
| `src/scoring.py` | FashionCLIP scoring (lazy model load) |
| `src/taxonomies.py` | Accepted pool slugs + aspect-specific CLIP captions |
| `docs/api.md` | Human-readable API guide (`options`, subjects, colour, scoring fields) |
| `eval/` | Optional labeled-fixture harness (`just eval`); not CI |
| `openapi/v1-score.yaml` | OpenAPI contract |
| `terraform/` | ECR + Lambda + API Gateway per `environment` var |
| `Dockerfile` | Multi-stage arm64 image with baked model |

## CI / deploy

| Workflow | Trigger | Action |
|----------|---------|--------|
| `test.yaml` | PR + push to `main`/`staging` | ruff + pytest |
| `deploy.yaml` | push to `main`/`staging` when runtime files change, or manual `workflow_dispatch` | ECR push + Lambda update |

Configure GitHub per `terraform/ci/README.md` — repo **secret** `AWS_DEPLOY_ROLE_ARN` (or variable), optional `HF_TOKEN`, environment `PRINT_VISION_URL`. Deploy sets `SENTRY_RELEASE` to the git SHA on each Lambda update.

Manual image deploy also requires `export AWS_ACCOUNT_ID=…` for `just build-image` / `just push-image`.

## Sentry

Set `SENTRY_DSN` in Lambda environment / local `.env`. Optional commit trailers like `Fixes <project>-N` can link deploys to issues when your Sentry project is configured.

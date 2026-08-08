# AGENTS.md — Reskinned FashionCLIP Service

Lambda-side print-vision scorer. Inventory owns promotion policy (`PRINT_VISION_*`).

## Commands

```bash
uv sync --group dev
just test
just lint
just build-image    # arm64 Docker; optional HF_TOKEN in .env
```

## Layout

| Path | Role |
|------|------|
| `src/handler.py` | API Gateway Lambda entry (`/v1/score`) |
| `src/scoring.py` | FashionCLIP scoring (lazy model load) |
| `openapi/v1-score.yaml` | HTTP contract |
| `terraform/` | ECR + Lambda + API Gateway per `environment` var |
| `Dockerfile` | Multi-stage arm64 image with baked model |

## CI / deploy

| Workflow | Trigger | Action |
|----------|---------|--------|
| `test.yaml` | PR + push to `main`/`staging` | ruff + pytest |
| `deploy.yaml` | push to `main`/`staging` | ECR push + Lambda update |

Configure GitHub per `terraform/ci/README.md` (`AWS_DEPLOY_ROLE_ARN`, optional `HF_TOKEN`, environment `PRINT_VISION_URL`).

## Sentry

Project: `reskinned-fashionclip-service`. Commit messages may include `Fixes RESKINNED-FASHIONCLIP-SERVICE-N`.

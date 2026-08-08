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

## Constraints

- **CPU torch only** — use `[[tool.uv.index]]` pytorch-cpu in `pyproject.toml`; never default PyPI torch (CUDA ~8GB).
- **arm64** image + Lambda `architectures = ["arm64"]`.
- Do not commit `.env`, `terraform/terraform.tfvars`, or `*.tfstate`.
- Terraform stacks already exist in AWS — import before `apply` (see `terraform/README.md`).

## Sentry

Project: `reskinned-fashionclip-service`. Commit messages may include `Fixes RESKINNED-FASHIONCLIP-SERVICE-N`.

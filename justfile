set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default_ecr_repo := "reskinned-fashionclip-service-staging"
aws_region := "eu-west-1"
aws_account := env_var('AWS_ACCOUNT_ID')

sync:
    uv sync --group dev

test:
    uv run pytest -q

# Live FashionCLIP fixture eval — not CI. Needs network + model weights.
eval *args:
    uv run python -m eval.run {{args}}

lint:
    uv run ruff check .
    uv run ruff format --check .

format:
    uv run ruff format .
    uv run ruff check --fix .

build-image environment=default_ecr_repo:
    #!/usr/bin/env bash
    set -a
    [ -f .env ] && source .env
    set +a
    docker build --platform linux/arm64 \
        --build-arg HF_TOKEN="${HF_TOKEN:-}" \
        -t "{{aws_account}}.dkr.ecr.{{aws_region}}.amazonaws.com/{{environment}}:latest" \
        .

push-image environment=default_ecr_repo:
    aws ecr get-login-password --region {{aws_region}} | docker login --username AWS --password-stdin {{aws_account}}.dkr.ecr.{{aws_region}}.amazonaws.com
    docker push {{aws_account}}.dkr.ecr.{{aws_region}}.amazonaws.com/{{environment}}:latest

update-lambda environment="reskinned-fashionclip-service-staging":
    aws lambda update-function-code \
        --function-name {{environment}} \
        --image-uri {{aws_account}}.dkr.ecr.{{aws_region}}.amazonaws.com/{{environment}}:latest \
        --region {{aws_region}}

tf-init:
    terraform -chdir=terraform init

tf-plan environment="staging":
    terraform -chdir=terraform plan -var="environment={{environment}}"

tf-apply environment="staging":
    terraform -chdir=terraform apply -var="environment={{environment}}"

smoke:
    #!/usr/bin/env bash
    set -a
    [ -f .env ] && source .env
    set +a
    : "${PRINT_VISION_URL:?set PRINT_VISION_URL}"
    : "${PRINT_VISION_API_KEY:?set PRINT_VISION_API_KEY}"
    curl -sS -X POST "$PRINT_VISION_URL" \
        -H "content-type: application/json" \
        -H "x-api-key: $PRINT_VISION_API_KEY" \
        -d '{"images":[{"url":"https://example.com/garment.jpg"}],"options":{"pattern-application":true,"pattern":true}}'

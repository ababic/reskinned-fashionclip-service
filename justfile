set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default_ecr_repo := "reskinned-fashionclip-service-staging"
aws_region := "eu-west-1"
aws_account := "830566885523"

sync:
    uv sync --group dev

test:
    uv run pytest -q

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
        -d '{"images":[{"url":"https://cdn.shopify.com/s/files/1/0081/8711/7664/files/Dayflex_leggingpantnofrontseam_shadowblack_10189.jpg?v=1744812821"}],"pools":{"pattern-application":["Placement print","All-over print"],"pattern":["Floral","Striped"]},"top_k":3}'

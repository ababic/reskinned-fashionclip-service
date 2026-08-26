terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "reskinned-fashionclip-service-${var.environment}"
}

resource "aws_ecr_repository" "service" {
  name                 = local.name_prefix
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}"
  retention_in_days = 30
}

resource "aws_lambda_function" "service" {
  function_name = local.name_prefix
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.service.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 90
  memory_size   = 3072

  environment {
    variables = {
      SENTRY_DSN                  = var.sentry_dsn
      SENTRY_ENVIRONMENT          = var.environment
      SENTRY_TRACES_SAMPLE_RATE   = "0.2"
      FASHIONCLIP_MODEL_DIR       = "/var/task/models/fashion-clip"
      HF_HUB_OFFLINE              = "1"
      TRANSFORMERS_OFFLINE        = "1"
      TORCH_DISABLE_SHARE_RDZV_TCP_STORE = "1"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_cloudwatch_log_group.lambda,
  ]
}

resource "aws_api_gateway_rest_api" "service" {
  name = "${local.name_prefix}-api"
}

resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_rest_api.service.root_resource_id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "score" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "score"
}

resource "aws_api_gateway_resource" "score_batch" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "score-batch"
}

resource "aws_api_gateway_method" "score_post" {
  rest_api_id      = aws_api_gateway_rest_api.service.id
  resource_id      = aws_api_gateway_resource.score.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_method" "score_batch_post" {
  rest_api_id      = aws_api_gateway_rest_api.service.id
  resource_id      = aws_api_gateway_resource.score_batch.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "score_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.service.id
  resource_id             = aws_api_gateway_resource.score.id
  http_method             = aws_api_gateway_method.score_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.service.invoke_arn
}

resource "aws_api_gateway_integration" "score_batch_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.service.id
  resource_id             = aws_api_gateway_resource.score_batch.id
  http_method             = aws_api_gateway_method.score_batch_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.service.invoke_arn
}

resource "aws_api_gateway_deployment" "service" {
  rest_api_id = aws_api_gateway_rest_api.service.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.score.id,
      aws_api_gateway_method.score_post.id,
      aws_api_gateway_integration.score_lambda.id,
      aws_api_gateway_resource.score_batch.id,
      aws_api_gateway_method.score_batch_post.id,
      aws_api_gateway_integration.score_batch_lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.score_lambda,
    aws_api_gateway_integration.score_batch_lambda,
  ]
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.service.id
  deployment_id = aws_api_gateway_deployment.service.id
  stage_name    = "prod"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.service.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.service.execution_arn}/*/*"
}

resource "aws_api_gateway_api_key" "service" {
  name = "${local.name_prefix}-api-key"
}

resource "aws_api_gateway_usage_plan" "service" {
  name = "${local.name_prefix}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.service.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }
}

resource "aws_api_gateway_usage_plan_key" "service" {
  key_id        = aws_api_gateway_api_key.service.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.service.id
}

resource "aws_api_gateway_method_settings" "score" {
  rest_api_id = aws_api_gateway_rest_api.service.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled = true
  }
}

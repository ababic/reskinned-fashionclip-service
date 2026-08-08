output "print_vision_url" {
  description = "Heroku PRINT_VISION_URL — POST /v1/score on API Gateway prod stage."
  value       = "${aws_api_gateway_stage.prod.invoke_url}/v1/score"
}

output "print_vision_api_key" {
  description = "Heroku PRINT_VISION_API_KEY (API Gateway key value)."
  value       = aws_api_gateway_api_key.service.value
  sensitive   = true
}

output "ecr_repository_url" {
  description = "ECR repository URL for docker push."
  value       = aws_ecr_repository.service.repository_url
}

output "lambda_function_name" {
  description = "Lambda function name for aws lambda update-function-code."
  value       = aws_lambda_function.service.function_name
}

output "api_gateway_id" {
  description = "API Gateway REST API id."
  value       = aws_api_gateway_rest_api.service.id
}

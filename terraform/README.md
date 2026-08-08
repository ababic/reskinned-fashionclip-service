# Terraform

Describes the **existing** staging and production stacks in `eu-west-1`:

| Environment | Lambda | API Gateway id | ECR repo |
|-------------|--------|----------------|----------|
| staging | `reskinned-fashionclip-service-staging` | `6dqkwpp851` | `reskinned-fashionclip-service-staging` |
| production | `reskinned-fashionclip-service-production` | `6jmeqxjis0` | `reskinned-fashionclip-service-production` |

## First-time state (after repo recovery)

Infrastructure was created before this git repo existed. **Do not run `terraform apply` on a fresh workspace** without importing — you will get duplicate-resource errors.

```bash
cd terraform
terraform init
terraform workspace new staging   # or: production
# terraform import … per resource — see AWS console / `terraform plan` hints
```

Until state is imported, treat these files as **documentation of deployed architecture**. Image deploys use `just build-image` + `just push-image` + `just update-lambda`.

## Variables

Copy `terraform.tfvars.example` → `terraform.tfvars` (gitignored). Set `environment` to `staging` or `production` and `sentry_dsn`.

## Outputs

- `print_vision_url` → Heroku `PRINT_VISION_URL`
- `print_vision_api_key` → Heroku `PRINT_VISION_API_KEY`
- `ecr_repository_url` → Docker push target

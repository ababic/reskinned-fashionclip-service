# GitHub Actions CI deploy (apply once per AWS account)

Creates the GitHub OIDC provider and IAM role used by `.github/workflows/deploy.yaml`.

```bash
cd terraform/ci
terraform init
terraform apply
```

Then in GitHub → **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|------|------|--------|
| Secret | `AWS_DEPLOY_ROLE_ARN` | `terraform output -raw github_deploy_role_arn` |
| Variable | `AWS_ACCOUNT_ID` | AWS account id for ECR image URIs in deploy |
| Secret | `HF_TOKEN` | Hugging Face token (optional; speeds model bake) |
| Secret | `PRINT_VISION_API_KEY` | API Gateway key (optional repo secret; per-environment secret preferred for smoke test) |

Per-environment **GitHub Environments** (`staging`, `production`):

| Kind | Name | Value |
|------|------|--------|
| Variable | `PRINT_VISION_URL` | Staging or production `/v1/score` URL |

## Branch deploy mapping

| Branch | GitHub environment | ECR / Lambda suffix |
|--------|-------------------|---------------------|
| `staging` | staging | `…-staging` |
| `main` | production | `…-production` |

If OIDC provider already exists in the account, import before apply:

```bash
terraform import aws_iam_openid_connect_provider.github_actions \
  arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # Root + intermediate thumbprints per GitHub/AWS OIDC docs; tls data is fallback.
  thumbprint_list = distinct(concat(
    [
      "6938fd4d98bab03faadb97b34396831e3780aea1",
    ],
    [for cert in data.tls_certificate.github_actions.certificates : cert.sha1_fingerprint],
  ))
}

resource "aws_iam_role" "github_deploy" {
  name = "reskinned-fashionclip-service-github-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud"        = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:repository" = "wearecrew/reskinned-fashionclip-service"
        }
        # GitHub OIDC sub uses org/repo IDs, e.g.
        # repo:wearecrew@5812276/reskinned-fashionclip-service@1323957910:environment:production
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:wearecrew@*/reskinned-fashionclip-service@*:*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "reskinned-fashionclip-service-github-deploy"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = [
          "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/reskinned-fashionclip-service-staging",
          "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/reskinned-fashionclip-service-production",
        ]
      },
      {
        Sid    = "LambdaUpdate"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:reskinned-fashionclip-service-staging",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:reskinned-fashionclip-service-production",
        ]
      },
    ]
  })
}

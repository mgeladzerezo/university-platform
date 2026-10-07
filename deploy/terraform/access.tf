# Application secrets and the IAM roles pods use. Pods get AWS credentials
# through EKS Pod Identity, so no access keys are stored anywhere.

resource "aws_secretsmanager_secret" "app" {
  name        = "${local.name}/app"
  description = "Application secrets: ANTHROPIC_API_KEY. Values are set outside Terraform."
}

data "aws_iam_policy_document" "pod_identity_assume" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "app" {
  statement {
    sid       = "ApplicationDocuments"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.documents.arn}/applications/*"]
  }

  statement {
    sid       = "SendMail"
    actions   = ["ses:SendEmail"]
    resources = [aws_sesv2_email_identity.mail.arn, aws_sesv2_configuration_set.mail.arn]
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-app"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_assume.json
}

resource "aws_iam_role_policy" "app" {
  name   = "app"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_eks_pod_identity_association" "app" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = var.app_namespace
  service_account = var.app_service_account
  role_arn        = aws_iam_role.app.arn
}

# External Secrets Operator copies these two secrets into the app namespace.
data "aws_iam_policy_document" "external_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [
      aws_secretsmanager_secret.app.arn,
      aws_db_instance.postgres.master_user_secret[0].secret_arn,
    ]
  }
}

resource "aws_iam_role" "external_secrets" {
  name               = "${local.name}-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_assume.json
}

resource "aws_iam_role_policy" "external_secrets" {
  name   = "read-app-secrets"
  role   = aws_iam_role.external_secrets.id
  policy = data.aws_iam_policy_document.external_secrets.json
}

resource "aws_eks_pod_identity_association" "external_secrets" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets.arn
}

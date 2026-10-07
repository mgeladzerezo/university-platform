output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "ecr_repositories" {
  value = { for name, repo in aws_ecr_repository.app : name => repo.repository_url }
}

output "database_endpoint" {
  value = aws_db_instance.postgres.address
}

output "database_secret_arn" {
  description = "Secrets Manager secret holding the RDS master credentials."
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "app_secret_name" {
  value = aws_secretsmanager_secret.app.name
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "documents_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "cloudfront_domain_name" {
  description = "Target for the site_domain CNAME/alias record."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "ses_dkim_tokens" {
  description = "Publish these as CNAME records to verify the mail domain."
  value       = aws_sesv2_email_identity.mail.dkim_signing_attributes[0].tokens
}

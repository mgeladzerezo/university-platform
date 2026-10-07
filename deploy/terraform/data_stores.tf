# PostgreSQL and Redis sit in the database subnets and accept connections only
# from the EKS cluster security group, which every node and pod ENI carries.

locals {
  cluster_security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = [for subnet in aws_subnet.database : subnet.id]
}

resource "aws_security_group" "postgres" {
  name        = "${local.name}-postgres"
  description = "PostgreSQL from the EKS cluster"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-postgres" }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_cluster" {
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = local.cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from EKS pods"
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${local.name}-pg16"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_allocated_storage_gb * 4
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "uni"
  username = "uni_admin"
  # RDS generates the password and keeps it (with rotation) in Secrets Manager.
  manage_master_user_password = true

  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  parameter_group_name   = aws_db_parameter_group.postgres.name
  publicly_accessible    = false

  backup_retention_period      = 14
  backup_window                = "01:00-02:00"
  maintenance_window           = "sun:02:30-sun:03:30"
  auto_minor_version_upgrade   = true
  performance_insights_enabled = true
  deletion_protection          = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${local.name}-final"
  copy_tags_to_snapshot        = true

  enabled_cloudwatch_logs_exports = ["postgresql"]
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = [for subnet in aws_subnet.database : subnet.id]
}

resource "aws_security_group" "redis" {
  name        = "${local.name}-redis"
  description = "Redis from the EKS cluster"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-redis" }
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_cluster" {
  security_group_id            = aws_security_group.redis.id
  referenced_security_group_id = local.cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
  description                  = "Redis from EKS pods"
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = local.name
  description          = "Celery broker and rate limiting for ${local.name}"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.redis_node_type
  port           = 6379

  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = 3
  apply_immediately        = false
}

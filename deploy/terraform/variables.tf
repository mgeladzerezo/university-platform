variable "project" {
  description = "Name prefix for all resources."
  type        = string
  default     = "kalinowo-uni"
}

variable "environment" {
  description = "Deployment environment (staging, production)."
  type        = string
}

variable "region" {
  description = "AWS region for the workload."
  type        = string
  default     = "eu-central-1"
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC; must be a /16."
  type        = string
  default     = "10.20.0.0/16"
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway instead of one per AZ. Cheaper, but an AZ outage cuts egress."
  type        = bool
  default     = false
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.31"
}

variable "cluster_public_access_cidrs" {
  description = "CIDR blocks allowed to reach the public EKS API endpoint."
  type        = list(string)
}

variable "node_instance_types" {
  description = "Instance types for the managed node group."
  type        = list(string)
  default     = ["m6i.large"]
}

variable "node_min_size" {
  type    = number
  default = 3
}

variable "node_max_size" {
  type    = number
  default = 9
}

variable "db_instance_class" {
  type    = string
  default = "db.m6g.large"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "site_domain" {
  description = "Public host name of the site, e.g. www.ukal.example."
  type        = string
}

variable "mail_domain" {
  description = "Domain used as the SES sender identity."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ACM certificate for site_domain. Must be issued in us-east-1 for CloudFront."
  type        = string
}

variable "origin_domain_name" {
  description = "DNS name of the ingress load balancer. Known only after the first Helm release, so it is an input."
  type        = string
}

variable "waf_rate_limit_per_5min" {
  description = "Requests per client IP per 5 minutes before WAF blocks."
  type        = number
  default     = 2000
}

variable "app_namespace" {
  description = "Kubernetes namespace of the Helm release."
  type        = string
  default     = "university"
}

variable "app_service_account" {
  description = "Service account used by the api and worker pods."
  type        = string
  default     = "university-api"
}

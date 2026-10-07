# CloudFront terminates TLS for the public site and forwards to the ingress
# load balancer. WAF runs at the edge, before traffic reaches the cluster.

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

resource "aws_wafv2_web_acl" "site" {
  provider = aws.us_east_1

  name  = local.name
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit_per_5min
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  dynamic "rule" {
    for_each = {
      AWSManagedRulesCommonRuleSet          = 10
      AWSManagedRulesKnownBadInputsRuleSet  = 20
      AWSManagedRulesAmazonIpReputationList = 30
    }

    content {
      name     = rule.key
      priority = rule.value

      override_action {
        none {}
      }

      statement {
        managed_rule_group_statement {
          vendor_name = "AWS"
          name        = rule.key
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${local.name}-${rule.key}"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = local.name
    sampled_requests_enabled   = true
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = local.name
  aliases         = [var.site_domain]
  price_class     = "PriceClass_100"
  web_acl_id      = aws_wafv2_web_acl.site.arn

  origin {
    origin_id   = "ingress"
    domain_name = var.origin_domain_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      # Above the longest assistant answer; SSE responses stay open while streaming.
      origin_read_timeout = 60
    }
  }

  # Pages and API responses are dynamic and often personal: never cached here.
  default_cache_behavior {
    target_origin_id         = "ingress"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
    compress                 = true
  }

  # Next.js build assets have content hashes in their names.
  ordered_cache_behavior {
    path_pattern           = "/_next/static/*"
    target_origin_id       = "ingress"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  logging_config {
    bucket = aws_s3_bucket.logs.bucket_domain_name
    prefix = "cloudfront/"
  }
}

resource "aws_sesv2_email_identity" "mail" {
  email_identity = var.mail_domain

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

resource "aws_sesv2_configuration_set" "mail" {
  configuration_set_name = local.name

  reputation_options {
    reputation_metrics_enabled = true
  }

  suppression_options {
    suppressed_reasons = ["BOUNCE", "COMPLAINT"]
  }
}

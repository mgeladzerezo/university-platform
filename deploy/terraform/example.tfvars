environment                 = "staging"
site_domain                 = "www.staging.ukal.example"
mail_domain                 = "ukal.example"
acm_certificate_arn         = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-000000000000"
origin_domain_name          = "k8s-university-ingress-0000000000.eu-central-1.elb.amazonaws.com"
cluster_public_access_cidrs = ["203.0.113.0/24"]
single_nat_gateway          = true
node_min_size               = 2

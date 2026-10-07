resource "aws_kms_key" "eks_secrets" {
  description             = "Envelope encryption of Kubernetes secrets in ${local.name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

data "aws_iam_policy_document" "eks_cluster_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_cluster" {
  name               = "${local.name}-eks-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_cluster_assume.json
}

resource "aws_iam_role_policy_attachment" "eks_cluster" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.name}/cluster"
  retention_in_days = 90
}

resource "aws_eks_cluster" "main" {
  name     = local.name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.eks_cluster.arn

  enabled_cluster_log_types = ["api", "audit", "authenticator"]

  vpc_config {
    subnet_ids              = [for subnet in aws_subnet.private : subnet.id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.cluster_public_access_cidrs
  }

  access_config {
    authentication_mode = "API"
  }

  encryption_config {
    resources = ["secrets"]

    provider {
      key_arn = aws_kms_key.eks_secrets.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster,
    aws_cloudwatch_log_group.eks,
  ]
}

data "aws_iam_policy_document" "eks_node_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_node" {
  name               = "${local.name}-eks-node"
  assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json
}

resource "aws_iam_role_policy_attachment" "eks_node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])

  role       = aws_iam_role.eks_node.name
  policy_arn = each.value
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "default"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = [for subnet in aws_subnet.private : subnet.id]
  instance_types  = var.node_instance_types

  scaling_config {
    min_size     = var.node_min_size
    max_size     = var.node_max_size
    desired_size = var.node_min_size
  }

  update_config {
    max_unavailable = 1
  }

  lifecycle {
    # The cluster autoscaler owns the desired size after creation.
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_iam_role_policy_attachment.eks_node]
}

resource "aws_eks_addon" "this" {
  for_each = toset(["vpc-cni", "coredns", "kube-proxy", "eks-pod-identity-agent"])

  cluster_name = aws_eks_cluster.main.name
  addon_name   = each.key

  depends_on = [aws_eks_node_group.default]
}

locals {
  name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  # /16 split into /20s: public 0-2, private 4-6, database 8-10.
  public_subnets   = { for i, az in local.azs : az => cidrsubnet(var.vpc_cidr, 4, i) }
  private_subnets  = { for i, az in local.azs : az => cidrsubnet(var.vpc_cidr, 4, i + 4) }
  database_subnets = { for i, az in local.azs : az => cidrsubnet(var.vpc_cidr, 4, i + 8) }

  nat_azs = var.single_nat_gateway ? [local.azs[0]] : local.azs
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = local.name }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = local.name }
}

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.key
  cidr_block              = each.value
  map_public_ip_on_launch = false

  tags = {
    Name                     = "${local.name}-public-${each.key}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_subnet" "private" {
  for_each = local.private_subnets

  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = {
    Name                              = "${local.name}-private-${each.key}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_subnet" "database" {
  for_each = local.database_subnets

  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = { Name = "${local.name}-database-${each.key}" }
}

resource "aws_eip" "nat" {
  for_each = toset(local.nat_azs)

  domain = "vpc"

  tags = { Name = "${local.name}-nat-${each.key}" }
}

resource "aws_nat_gateway" "main" {
  for_each = toset(local.nat_azs)

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id

  tags = { Name = "${local.name}-${each.key}" }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = toset(local.azs)

  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[var.single_nat_gateway ? local.azs[0] : each.key].id
  }

  tags = { Name = "${local.name}-private-${each.key}" }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

# Database subnets get no default route: nothing in them needs the internet.
resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name}-database" }
}

resource "aws_route_table_association" "database" {
  for_each = aws_subnet.database

  subnet_id      = each.value.id
  route_table_id = aws_route_table.database.id
}

# S3 traffic from the nodes stays on the AWS network and skips the NAT gateways.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for table in aws_route_table.private : table.id]

  tags = { Name = "${local.name}-s3" }
}

resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "REJECT"
  log_destination_type = "s3"
  log_destination      = aws_s3_bucket.logs.arn
}

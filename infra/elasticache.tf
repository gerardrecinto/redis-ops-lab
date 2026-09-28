# Reference IaC only. Nothing in this file has been applied to a real AWS
# account for this portfolio project -- no ElastiCache resources are
# running, and this is not a claim of AWS ElastiCache operational
# experience. It documents how this lab's local primary/replica/Sentinel
# topology maps onto AWS's managed Redis offering -- see
# docs/REDIS_TIERS.md for the honest distinction between local Redis,
# self-managed Redis (on EC2), and ElastiCache (this file).

variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "app_security_group_id" {
  description = "Security group of the application tier allowed to reach Redis."
  type        = string
}

resource "aws_elasticache_subnet_group" "redis_ops_lab" {
  name       = "redis-ops-lab-subnet-group"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name_prefix = "redis-ops-lab-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ElastiCache's equivalent of this lab's primary + 2 replicas + Sentinel:
# a replication group with Multi-AZ automatic failover, which is AWS's
# managed substitute for running and operating Sentinel yourself.
resource "aws_elasticache_replication_group" "redis_ops_lab" {
  replication_group_id = "redis-ops-lab"
  description          = "Portfolio-lab equivalent of the local primary/replica/Sentinel stack"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = "cache.t4g.micro" # smallest burstable type; see docs/COST_NOTES.md

  num_cache_clusters         = 3 # 1 primary + 2 replicas, matching docker-compose.yml
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.redis_ops_lab.name
  security_group_ids = [aws_security_group.redis.id]

  # Authentication and encryption: this lab's local docker-compose.yml
  # uses a plaintext requirepass and no TLS (deliberately simple for a
  # local dev loop, documented as a gap in docs/SECURITY.md). A real
  # ElastiCache deployment should turn both on -- there is no equivalent
  # local-lab shortcut here; this project only verifies password auth
  # locally (docs/SECURITY.md), never TLS or IAM-based auth.
  auth_token                 = var.redis_auth_token
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  # AOF-equivalent durability: ElastiCache doesn't expose raw AOF/RDB
  # toggles the way self-managed Redis does -- snapshot_retention_limit
  # is its closest analog, backed by automated daily snapshots.
  snapshot_retention_limit = 5
  snapshot_window          = "03:00-05:00"

  maxmemory_policy = "allkeys-lru" # matches docker-compose.yml's local setting
}

variable "redis_auth_token" {
  description = "AUTH token for the replication group. Never commit a real value -- pass via TF_VAR_redis_auth_token or a secrets manager."
  type        = string
  sensitive   = true
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "redis-ops-lab-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 90
  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis_ops_lab.replication_group_id
  }
  alarm_description = "Mirrors monitoring.py's local alert_thresholds() memory check"
}

resource "aws_cloudwatch_metric_alarm" "low_hit_rate" {
  alarm_name          = "redis-ops-lab-low-cache-hit-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CacheHitRate"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 50
  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis_ops_lab.replication_group_id
  }
  alarm_description = "Mirrors monitoring.py's local alert_thresholds() hit-rate check"
}

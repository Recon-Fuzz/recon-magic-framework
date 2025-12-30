terraform {
  required_version = "~> 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.56"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = { Namespace = var.namespace }
  }
}

module "ecr" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 1.6.0"

  repository_force_delete = true
  # https://stackoverflow.com/a/75131873/1849920
  repository_image_tag_mutability = "MUTABLE"
  repository_name                 = var.namespace
  repository_lifecycle_policy = jsonencode({
    rules = [{
      action       = { type = "expire" }
      description  = "Delete all images except a handful of the newest images"
      rulePriority = 1
      selection = {
        countNumber = 3
        countType   = "imageCountMoreThan"
        tagStatus   = "any"
      }
    }]
  })
}

data "aws_availability_zones" "available" { state = "available" }
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 3.19.0"

  azs                = slice(data.aws_availability_zones.available.names, 0, 2)
  cidr               = "10.0.0.0/16"
  create_igw         = true
  enable_nat_gateway = true
  private_subnets    = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets     = ["10.0.101.0/24", "10.0.102.0/24"]
  single_nat_gateway = true
}

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 4.1.3"

  cluster_name = var.namespace

  fargate_capacity_providers = {
    FARGATE = {
      default_capacity_provider_strategy = {
        weight = 100
      }
    }
  }
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.namespace}-ecs-task-execution"

  assume_role_policy = <<EOF
{
 "Version": "2012-10-17",
 "Statement": [
   {
     "Action": "sts:AssumeRole",
     "Principal": {
       "Service": "ecs-tasks.amazonaws.com"
     },
     "Effect": "Allow",
     "Sid": ""
   }
 ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "ecs-task-execution-role-policy-attachment" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.namespace}"
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "magic_worker" {
  container_definitions = jsonencode([{
    environment = [
      { name = "WORKER_API_URL", value = var.backend_api_url },
      { name = "WORKER_PERMISSIONS", value = var.worker_permissions }
    ],
    essential = true,
    image     = "${module.ecr.repository_url}:latest",
    name      = var.namespace,
    command   = ["python", "runner.py"],
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.this.name,
        "awslogs-region"        = var.aws_region,
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
  cpu                      = var.vCPU
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  family                   = "${var.namespace}-magic-worker"
  memory                   = var.mem
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_service" "this" {
  cluster         = module.ecs.cluster_id
  desired_count   = 0
  launch_type     = "FARGATE"
  name            = "${var.namespace}-service"
  task_definition = aws_ecs_task_definition.magic_worker.arn

  lifecycle {
    ignore_changes = [desired_count]
  }

  network_configuration {
    security_groups = [module.vpc.default_security_group_id]
    subnets         = module.vpc.private_subnets
  }
}

resource "aws_iam_user" "backend_dispatcher" {
  name = "${var.namespace}-dispatcher"
}

resource "aws_iam_access_key" "backend_dispatcher" {
  user = aws_iam_user.backend_dispatcher.name
}

data "aws_iam_policy_document" "backend_dispatcher" {
  statement {
    effect  = "Allow"
    actions = [
      "ecs:RunTask",
      "ecs:StopTask",
      "ecs:DescribeTasks",
      "ecs:DescribeTaskDefinition",
      "ecs:ListTasks",
      "ecs:ListClusters"
    ]
    resources = ["*"]
  }

  statement {
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_task_execution_role.arn]
  }
}

resource "aws_iam_user_policy" "backend_dispatcher" {
  name   = "${var.namespace}-dispatcher-policy"
  user   = aws_iam_user.backend_dispatcher.name
  policy = data.aws_iam_policy_document.backend_dispatcher.json
}

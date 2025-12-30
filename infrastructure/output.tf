output "ECR_REPOSITORY_URL" {
  value = module.ecr.repository_url
}

output "ECS_CLUSTER_NAME" {
  value = module.ecs.cluster_name
}

output "ECS_TASK_DEFINITION_FAMILY" {
  value = aws_ecs_task_definition.magic_worker.family
}

output "ECS_CONTAINER_NAME" {
  value = var.namespace
}

output "ECS_SECURITY_GROUP" {
  value = module.vpc.default_security_group_id
}

output "ECS_SUBNETS" {
  value = join(",", module.vpc.private_subnets)
}

output "ECS_TASK_EXECUTION_ROLE_ARN" {
  value = aws_iam_role.ecs_task_execution_role.arn
}

output "AWS_DISPATCHER_ACCESS_KEY_ID" {
  value = aws_iam_access_key.backend_dispatcher.id
}

output "AWS_DISPATCHER_SECRET_ACCESS_KEY" {
  value     = aws_iam_access_key.backend_dispatcher.secret
  sensitive = true
}

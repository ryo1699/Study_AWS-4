output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_repository_name" {
  value = aws_ecr_repository.api.name
}

output "app_instance_id" {
  value = aws_instance.app.id
}

output "bastion_public_ip" {
  value = aws_instance.bastion.public_ip
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.api.domain_name
}

output "ssm_service_name" {
  value = "study-aws-4-task4-api"
}

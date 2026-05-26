variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "ap-northeast-1"
}

variable "project_name" {
  type        = string
  description = "Name prefix for AWS resources."
  default     = "study-aws-4-4"
}

variable "db_username" {
  type        = string
  description = "RDS application username."
  default     = "app_user"
}

variable "db_password" {
  type        = string
  description = "RDS application password. Use terraform.tfvars and keep it out of Git."
  sensitive   = true
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the bastion."
  default     = "0.0.0.0/32"
}

variable "bastion_key_name" {
  type        = string
  description = "Existing EC2 key pair name used to SSH into the bastion."
}

variable "app_instance_type" {
  type        = string
  description = "Instance type for the REST API EC2 instance."
  default     = "t3.micro"
}

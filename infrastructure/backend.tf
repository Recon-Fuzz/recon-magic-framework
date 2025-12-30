terraform {
  backend "s3" {
    # Backend configuration will be provided via -backend-config flags
    # during terraform init to support multiple environments
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

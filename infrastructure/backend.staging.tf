# This backend configuration is kept for reference/future use.
# The active backend configuration is in backend.tf
# To use this staging backend, rename this file to backend.tf
terraform {
  backend "s3" {
    bucket = "staging-recon-magic-framework"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

terraform {
  backend "s3" {
    bucket = "staging-recon-magic-framework-backend"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

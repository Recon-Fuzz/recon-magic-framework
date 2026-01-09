terraform {
  backend "s3" {
    bucket = "production-recon-magic-framework"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

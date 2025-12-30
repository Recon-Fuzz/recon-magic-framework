terraform {
  backend "s3" {
    bucket = "recon-magic-framework-backend"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

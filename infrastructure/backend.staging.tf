terraform {
  backend "s3" {
    bucket = "staging-recon-magic-framework"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

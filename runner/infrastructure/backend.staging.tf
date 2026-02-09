terraform {
  backend "s3" {
    bucket = "staging-runner"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

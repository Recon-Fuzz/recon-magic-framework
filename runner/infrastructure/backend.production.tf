terraform {
  backend "s3" {
    bucket = "getrecon-runner-backend"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

variable "docker_host" {
  # https://discuss.hashicorp.com/t/cannot-connect-to-docker-daemon/34122/9
  description = "Docker daemon socket address"
  default = "unix:///var/run/docker.sock"
}

variable "npm_token" {
  description = "NPM_TOKEN"
}

variable "namespace" {
  description = "namespace"
}

variable "vCPU" {
  description = "cpuCount"
}

variable "mem" {
  description = "mem"
}
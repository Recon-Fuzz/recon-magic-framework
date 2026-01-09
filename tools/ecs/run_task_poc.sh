#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing .env at ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

required_vars=(
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_DEFAULT_REGION
  WORKER_API_URL
  WORKER_BEARER_TOKEN
  WORKER_JOB_ID
  GITHUB_TOKEN
  ANTHROPIC_API_KEY
)

for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Missing ${var} in .env" >&2
    exit 1
  fi
done

if [[ -z "${WORKER_PERMISSIONS:-}" ]]; then
  WORKER_PERMISSIONS="false"
fi

pushd "${ROOT_DIR}/infrastructure" >/dev/null
tmp_dir="$(mktemp -d)"
cleanup() {
  rm -f backend.tf
  if [[ -f "${tmp_dir}/backend.staging.tf" ]]; then
    mv "${tmp_dir}/backend.staging.tf" backend.staging.tf
  fi
  if [[ -f "${tmp_dir}/backend.production.tf" ]]; then
    mv "${tmp_dir}/backend.production.tf" backend.production.tf
  fi
  rmdir "${tmp_dir}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mv backend.staging.tf "${tmp_dir}/backend.staging.tf"
mv backend.production.tf "${tmp_dir}/backend.production.tf"
cp "${tmp_dir}/backend.staging.tf" backend.tf
terraform init -reconfigure -input=false >/dev/null
terraform output -json > "${tmp_dir}/terraform_outputs.json"
popd >/dev/null

export TMP_OUTPUTS="${tmp_dir}/terraform_outputs.json"
python3 - <<'PY'
import json
import os
from pathlib import Path

outputs = json.loads(Path(os.environ["TMP_OUTPUTS"]).read_text(encoding="utf-8"))

def out(name: str) -> str:
    return outputs[name]["value"]

cluster = out("ECS_CLUSTER_NAME")
container = out("ECS_CONTAINER_NAME")
task_family = out("ECS_TASK_DEFINITION_FAMILY")
security_group = out("ECS_SECURITY_GROUP")
subnets = out("ECS_SUBNETS").split(",")

env = [
    {"name": "WORKER_API_URL", "value": os.environ["WORKER_API_URL"]},
    {"name": "WORKER_BEARER_TOKEN", "value": os.environ["WORKER_BEARER_TOKEN"]},
    {"name": "WORKER_JOB_ID", "value": os.environ["WORKER_JOB_ID"]},
    {"name": "WORKER_PERMISSIONS", "value": os.environ.get("WORKER_PERMISSIONS", "false")},
    {"name": "GITHUB_TOKEN", "value": os.environ["GITHUB_TOKEN"]},
    {"name": "ANTHROPIC_API_KEY", "value": os.environ["ANTHROPIC_API_KEY"]},
]

payload = os.environ.get("WORKER_JOB_PAYLOAD", "")
if payload:
    env.append({"name": "WORKER_JOB_PAYLOAD", "value": payload})

overrides = {"containerOverrides": [{"name": container, "environment": env}]}
network = {
    "awsvpcConfiguration": {
        "subnets": subnets,
        "securityGroups": [security_group],
        "assignPublicIp": "DISABLED",
    }
}

Path("/tmp/ecs-overrides.json").write_text(json.dumps(overrides), encoding="utf-8")
Path("/tmp/ecs-network.json").write_text(json.dumps(network), encoding="utf-8")
Path("/tmp/ecs-meta.json").write_text(json.dumps({"cluster": cluster, "task_family": task_family}), encoding="utf-8")
PY

cluster="$(python3 -c 'import json;print(json.load(open("/tmp/ecs-meta.json"))["cluster"])')"
task_family="$(python3 -c 'import json;print(json.load(open("/tmp/ecs-meta.json"))["task_family"])')"

aws ecs run-task \
  --cluster "${cluster}" \
  --launch-type FARGATE \
  --task-definition "${task_family}" \
  --network-configuration file:///tmp/ecs-network.json \
  --overrides file:///tmp/ecs-overrides.json \
  --query "tasks[0].taskArn" \
  --output text

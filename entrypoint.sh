#!/bin/bash
set -e

MODE="${MODE:-framework}"

case "$MODE" in
  runner)
    echo "Starting runner..."
    cd /app/runner
    exec yarn start "$@"
    ;;
  api)
    echo "Starting API server..."
    cd /app/backend
    npx prisma db push && npx prisma generate
    exec node dist/index.js "$@"
    ;;
  framework)
    echo "Starting framework..."
    cd /app
    exec python3 cli.py "$@"
    ;;
  worker)
    echo "Starting framework worker..."
    cd /app
    exec python3 worker.py "$@"
    ;;
  *)
    echo "Unknown MODE: $MODE"
    echo "Valid modes: runner, api, framework, worker"
    echo "Falling back to bash..."
    exec /bin/bash "$@"
    ;;
esac

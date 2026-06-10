#!/bin/bash
# AgriSense one-shot teardown.
#
# Usage:
#   ./scripts/stop.sh                 # docker-compose stack only (default)
#   ./scripts/stop.sh compose         # same
#   ./scripts/stop.sh minikube        # K8s namespace + stop minikube cluster
#   ./scripts/stop.sh all             # both
#   ./scripts/stop.sh compose --purge # also delete postgres volume (loses past results)
#   ./scripts/stop.sh --help
#
# Idempotent: safe to run when nothing is up.

set -euo pipefail

MODE="${1:-compose}"
PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge|-p) PURGE=1 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

say()  { printf '\n=== %s ===\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

stop_compose() {
  say "Stopping docker-compose stack"
  if ! docker info >/dev/null 2>&1; then
    warn "Docker is not running; nothing to stop."
    return
  fi

  if [ "$PURGE" = "1" ]; then
    warn "--purge: removing containers AND postgres_data volume"
    docker compose down -v
  else
    docker compose down
    echo "  (postgres volume kept; pass --purge to delete it too)"
  fi
}

stop_minikube() {
  say "Stopping AgriSense on Minikube"
  if ! command -v kubectl >/dev/null 2>&1; then
    warn "kubectl not installed; nothing to do for minikube path."
    return
  fi

  if kubectl get namespace agrisense >/dev/null 2>&1; then
    echo "  deleting namespace 'agrisense' (drops PVCs, secrets, all services)"
    kubectl delete namespace agrisense --wait=false
  else
    echo "  namespace 'agrisense' not present"
  fi

  if command -v minikube >/dev/null 2>&1; then
    if minikube status 2>/dev/null | grep -q "host: Running"; then
      say "Stopping Minikube cluster"
      minikube stop
    else
      echo "  Minikube already stopped"
    fi
  fi
}

case "$MODE" in
  compose|docker|docker-compose) stop_compose ;;
  minikube|k8s|kubernetes)       stop_minikube ;;
  all|both)                      stop_compose; stop_minikube ;;
  -h|--help|help)
    cat <<EOF
Usage: $0 [compose|minikube|all] [--purge]

  compose   (default) docker compose down. Keeps the postgres volume.
  minikube  Delete the agrisense namespace and stop the minikube cluster.
  all       Both of the above.

Flags:
  --purge   For compose: also delete the postgres_data volume (loses
            stored analysis results). Has no effect on minikube mode
            (the namespace delete already drops the PVC).

Idempotent. Safe to run when nothing is up.
EOF
    ;;
  *)
    printf 'ERROR: unknown mode %s. Use compose, minikube, or all.\n' "$MODE" >&2
    exit 1
    ;;
esac

cat <<EOF

Done. To bring everything back up: ./scripts/start.sh [compose|minikube]
EOF

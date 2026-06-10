#!/bin/bash
# AgriSense one-shot launcher.
#
# Usage:
#   ./scripts/start.sh                # docker-compose (default, no K8s)
#   ./scripts/start.sh compose        # explicit
#   ./scripts/start.sh minikube       # full Minikube + KEDA demo
#   ./scripts/start.sh --help
#
# Safe to re-run. Every step is idempotent — first run does setup,
# every subsequent run is a fast no-op for anything already in place.

set -euo pipefail

MODE="${1:-compose}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# ----------------------------- helpers --------------------------------
say()  { printf '\n=== %s ===\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"
}

check_env_file() {
  [ -f .env ] || die ".env not found. Copy .env.example to .env and fill in GITHUB_TOKEN + USDA_NASS_API_KEY."
}

check_docker() {
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop first."
}

# Return the docker container name holding host port $1, or empty.
port_holder() {
  docker ps --filter "publish=$1" --format '{{.Names}}' 2>/dev/null | head -1
}

# If a non-AgriSense container is holding the port, offer to stop it.
handle_port_conflict() {
  local port="$1"
  local svc="$2"
  local holder
  holder="$(port_holder "$port")"
  if [ -n "$holder" ] && [ "$holder" != "agrisense-${svc}-1" ]; then
    warn "port $port is held by container '$holder' (AgriSense $svc needs it)."
    if [ -t 0 ]; then
      read -r -p "Stop '$holder' so AgriSense can claim port $port? [y/N] " ans
    else
      ans=""
    fi
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      docker stop "$holder" >/dev/null
      echo "  stopped $holder. To bring it back later:  docker start $holder"
    else
      die "cannot start without port $port. Free it and rerun."
    fi
  fi
}

open_url() {
  if   command -v open     >/dev/null 2>&1; then open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1"
  else echo "Open this URL in your browser: $1"; fi
}

# ----------------------------- compose --------------------------------
start_compose() {
  say "AgriSense docker-compose launcher"
  check_env_file
  check_docker

  # Resolve port conflicts before docker tries (and fails with a cryptic error).
  handle_port_conflict 8000 api-gateway
  handle_port_conflict 8001 foundry-iq
  handle_port_conflict 8002 market-intel
  handle_port_conflict 8501 frontend

  say "Bringing up containers (builds missing images automatically)"
  docker compose up -d

  say "Waiting for frontend HTTP 200"
  for i in $(seq 1 45); do
    if curl -s -o /dev/null -w '%{http_code}' http://localhost:8501 2>/dev/null | grep -q 200; then
      echo "  frontend ready after ${i}s"
      break
    fi
    sleep 1
  done

  say "Opening UI"
  open_url http://localhost:8501

  cat <<'EOF'

AgriSense is running on docker-compose.
  Frontend:    http://localhost:8501
  API gateway: http://localhost:8000
  Foundry IQ:  http://localhost:8001
  Market:      http://localhost:8002

To stop everything:  docker compose -f docker-compose.yml down
To view logs:        docker compose logs -f <service>
EOF
}

# ----------------------------- minikube -------------------------------
start_minikube() {
  say "AgriSense Minikube + KEDA launcher"
  check_env_file
  check_docker

  # Install minikube + kubectl if missing.
  if ! command -v minikube >/dev/null 2>&1 || ! command -v kubectl >/dev/null 2>&1; then
    say "minikube or kubectl missing; running setup.sh"
    bash scripts/setup.sh
  fi
  require minikube
  require kubectl

  # Start cluster if it's not up.
  if minikube status >/dev/null 2>&1 && minikube status 2>/dev/null | grep -q "host: Running"; then
    echo "  Minikube already running"
  else
    say "Starting Minikube (3500MB / 2 CPU)"
    minikube start --memory=3500 --cpus=2 --driver=docker
  fi

  # Install KEDA if its namespace isn't there yet.
  if kubectl get ns keda >/dev/null 2>&1; then
    echo "  KEDA already installed"
  else
    say "Installing KEDA"
    kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml
    kubectl wait --for=condition=ready pod -l app=keda-operator -n keda --timeout=180s
  fi

  # Build all 5 images into Minikube's docker daemon if any are missing.
  say "Checking AgriSense images inside Minikube"
  eval "$(minikube docker-env)"
  MISSING=""
  for svc in disease-detector api-gateway foundry-iq market-intel frontend; do
    if ! docker images --format '{{.Repository}}' | grep -qx "agrisense-$svc"; then
      MISSING="$MISSING $svc"
    fi
  done
  if [ -n "$MISSING" ]; then
    say "Building missing images:$MISSING (first build is slow; HuggingFace model download)"
    bash scripts/build-and-push.sh
  else
    echo "  all 5 images present"
  fi

  # Load env vars used by the secret in deploy.sh.
  say "Sourcing .env"
  set -a
  . ./.env
  set +a

  say "Applying manifests"
  bash scripts/deploy.sh

  say "Waiting for app pods to be Ready"
  for app in api-gateway foundry-iq market-intel frontend; do
    kubectl wait --for=condition=ready pod -l "app=$app" -n agrisense --timeout=180s
  done

  cat <<'EOF'

AgriSense is running on Minikube.

For the KEDA demo, open TWO terminals:
  Terminal 1: watch kubectl get pods -n agrisense
  Terminal 2: (this script will open the UI in your browser next)

Upload a JPG from data/sample-images/ and watch the right-hand pane:
disease-detector scales 0 -> 1 within ~15-30s of upload, then back
to 0 after a 30s cooldown.

To stop the app stack:  kubectl delete namespace agrisense
To stop the cluster:    minikube stop
EOF

  say "Opening frontend (minikube service prints a URL and may stay in foreground)"
  minikube service frontend-service -n agrisense
}

# ----------------------------- dispatch -------------------------------
case "$MODE" in
  compose|docker|docker-compose) start_compose ;;
  minikube|k8s|kubernetes)       start_minikube ;;
  -h|--help|help)
    cat <<EOF
Usage: $0 [compose|minikube]

  compose   (default) docker-compose stack. Simpler, no Kubernetes,
            no KEDA scale demo. Best for development.

  minikube  Full Minikube + KEDA. Best for the hackathon demo video.
            First run is slow (~15 min): installs minikube/KEDA and
            builds 5 service images into Minikube's docker daemon
            (the disease-detector image pre-downloads the HuggingFace
            model). Re-runs are fast.

Both modes are idempotent. Safe to rerun after a reboot or after
docker stop.
EOF
    ;;
  *) die "unknown mode '$MODE'. Use 'compose' or 'minikube' (or '$0 --help')." ;;
esac

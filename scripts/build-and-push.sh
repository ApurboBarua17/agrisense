#!/bin/bash
set -e

# Builds all 5 service images directly into Minikube's Docker daemon, so
# Kubernetes can pull them with `imagePullPolicy: IfNotPresent` (no registry
# push needed). To also push to Docker Hub, set DOCKERHUB_USERNAME and
# uncomment the tag/push lines below.

DOCKERHUB_USER="${DOCKERHUB_USERNAME:-}"

echo "=== Building AgriSense images ==="
if [ -n "$DOCKERHUB_USER" ]; then
    echo "Docker Hub user: $DOCKERHUB_USER"
fi

# Point Docker CLI at Minikube's daemon (only effects this shell)
echo "Switching docker context to Minikube..."
eval "$(minikube docker-env)"

SERVICES=("disease-detector" "api-gateway" "foundry-iq" "market-intel" "frontend")

for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo "--- Building $SERVICE ---"
    docker build -t "agrisense-$SERVICE:latest" "./services/$SERVICE/"

    if [ -n "$DOCKERHUB_USER" ]; then
        docker tag "agrisense-$SERVICE:latest" "$DOCKERHUB_USER/agrisense-$SERVICE:latest"
        docker push "$DOCKERHUB_USER/agrisense-$SERVICE:latest"
    fi

    echo "$SERVICE built"
done

echo ""
echo "=== All images built ==="
echo "Images are now available inside Minikube's local registry."
echo "Run ./scripts/deploy.sh next."

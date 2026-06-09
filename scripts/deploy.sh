#!/bin/bash
set -e

echo "=== Deploying AgriSense to Minikube ==="

kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmap.yaml

# Secrets (use placeholders if env vars are not set; services will fall back gracefully)
kubectl create secret generic azure-secrets \
  --from-literal=connection-string="${AZURE_AI_PROJECT_CONNECTION_STRING:-}" \
  --namespace=agrisense \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic agrisense-secrets \
  --from-literal=usda-api-key="${USDA_NASS_API_KEY:-DEMO_KEY}" \
  --namespace=agrisense \
  --dry-run=client -o yaml | kubectl apply -f -

# Infra first
kubectl apply -f kubernetes/redis/
kubectl apply -f kubernetes/postgres/

echo "Waiting for Redis and Postgres..."
kubectl wait --for=condition=ready pod -l app=redis -n agrisense --timeout=180s
kubectl wait --for=condition=ready pod -l app=postgres -n agrisense --timeout=180s

# App services
kubectl apply -f kubernetes/api-gateway/
kubectl apply -f kubernetes/foundry-iq/
kubectl apply -f kubernetes/market-intel/
kubectl apply -f kubernetes/disease-detector/   # starts at 0 replicas
kubectl apply -f kubernetes/frontend/

# KEDA (the magic piece)
kubectl apply -f kubernetes/keda/

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n agrisense"
echo "  kubectl get scaledobject -n agrisense"
echo "  kubectl get hpa -n agrisense"
echo ""
echo "Open the frontend:"
echo "  minikube service frontend-service -n agrisense"
echo ""
echo "Watch KEDA scaling in real time:"
echo "  watch kubectl get pods -n agrisense"

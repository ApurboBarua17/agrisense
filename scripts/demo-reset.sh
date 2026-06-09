#!/bin/bash
# Reset state for a clean demo run.
# - Drains the Redis queue
# - Truncates analysis_results in Postgres
# - Restarts the gateway/frontend pods so caches are clean

set -e

NS=agrisense

echo "=== Resetting AgriSense state for clean demo ==="

echo "Flushing Redis queue..."
kubectl exec -n "$NS" deploy/redis -- redis-cli del disease_jobs >/dev/null

echo "Truncating analysis_results..."
kubectl exec -n "$NS" deploy/postgres -- \
  psql -U agrisense -d agrisense -c "TRUNCATE TABLE analysis_results;" >/dev/null

echo "Restarting api-gateway and frontend..."
kubectl rollout restart deployment/api-gateway -n "$NS"
kubectl rollout restart deployment/frontend    -n "$NS"

echo ""
echo "Reset complete. disease-detector replicas:"
kubectl get deployment disease-detector -n "$NS" -o jsonpath='{.spec.replicas}'
echo ""
echo "(KEDA will scale this to 0 once the queue is empty)"

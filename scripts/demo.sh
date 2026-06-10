#!/bin/bash
# AgriSense demo orchestrator.
#
# Preps the cluster for a clean recording, prints narration cues
# with timestamps, then opens the Streamlit frontend tunnel so
# you can hit record and walk through the flow.
#
# Usage:  ./scripts/demo.sh
#
# Assumes you're on the minikube path (the KEDA demo is the point
# of the video — compose can't show the scale-from-zero moment).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

NS=agrisense

say()  { printf '\n=== %s ===\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

# --- pre-flight -------------------------------------------------------
say "Pre-flight checks"
command -v kubectl  >/dev/null 2>&1 || { warn "kubectl not installed"; exit 1; }
command -v minikube >/dev/null 2>&1 || { warn "minikube not installed"; exit 1; }

if ! minikube status 2>/dev/null | grep -q "host: Running"; then
  say "Minikube is not running — bootstrapping via start.sh minikube"
  bash scripts/start.sh minikube
fi

if ! kubectl get namespace "$NS" >/dev/null 2>&1; then
  say "AgriSense not deployed — bootstrapping via start.sh minikube"
  bash scripts/start.sh minikube
fi

# --- reset state for a clean recording -------------------------------
say "Resetting state for a clean run"
kubectl exec -n "$NS" deploy/redis -- redis-cli del disease_jobs >/dev/null 2>&1 \
  && echo "  Redis queue drained" \
  || warn "  could not drain Redis queue (continuing)"

kubectl exec -n "$NS" deploy/postgres -- \
  psql -U agrisense -d agrisense -c "TRUNCATE TABLE analysis_results;" >/dev/null 2>&1 \
  && echo "  analysis_results truncated" \
  || warn "  could not truncate analysis_results (continuing)"

# --- confirm KEDA is at idle -----------------------------------------
say "Confirming KEDA is at idle (disease-detector replicas=0)"
for i in $(seq 1 18); do
  REPLICAS=$(kubectl get deployment disease-detector -n "$NS" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "?")
  if [ "$REPLICAS" = "0" ]; then
    echo "  disease-detector at 0 replicas — KEDA ready for the demo"
    break
  fi
  echo "  waiting for KEDA cooldown ($((i*5))s)..."
  sleep 5
done

kubectl get scaledobject -n "$NS" 2>&1 | grep -v "^$"

# --- narration --------------------------------------------------------
cat <<'EOF'

================================================================
                  DEMO READY — NARRATION CUES
================================================================

TERMINAL LAYOUT (set this up BEFORE you hit record):

  LEFT  (about 60% of screen):
    The browser tab this script opens. That's the Streamlit UI.

  RIGHT (about 40% of screen, this is your money shot):
    In a separate terminal, run:
      watch -n 1 kubectl get pods -n agrisense

  Now hit RECORD and read the cues below.

----------------------------------------------------------------
T+0:00 - 0:30   INTRODUCTION
----------------------------------------------------------------
"This is AgriSense, a crop disease and market intelligence
 agent built for the Agents League hackathon — Reasoning
 Agents track. Smallholder farmers lose 220 billion dollars
 globally each year to preventable crop disease, and no tool
 exists for a farmer with a 200-dollar smartphone. AgriSense
 gives them a disease diagnosis from a photo, USDA-grounded
 treatment advice, and market sell-timing — in under a minute."

----------------------------------------------------------------
T+0:30 - 1:00   POINT AT THE RIGHT PANE
----------------------------------------------------------------
"What you're seeing on the right is a live Kubernetes cluster.
 Notice the disease-detector deployment has ZERO running pods.
 That's KEDA — Kubernetes Event-Driven Autoscaling — keeping
 compute idle until there's actual work. Zero cost when no
 farmers are uploading. This is not Kubernetes for show — it's
 the correct architecture for a bursty, harvest-driven workload."

----------------------------------------------------------------
T+1:00 - 1:45   UPLOAD THE IMAGE
----------------------------------------------------------------
"I'm uploading a tomato leaf with Early Blight."
  [Click "Choose File", pick data/sample-images/Tomato___Early_Blight.JPG]
  [Click "Analyze Plant"]

"Watch the right pane — within 30 seconds KEDA detects the
 Redis queue depth and..."
  [Wait for disease-detector-xxxxx pod to appear; point at it.]

"...there. KEDA scaled disease-detector from zero to one
 automatically. No manual intervention, no pre-provisioned
 capacity."

----------------------------------------------------------------
T+1:45 - 3:00   WALK THROUGH THE RESULT
----------------------------------------------------------------
"The HuggingFace vision model identified Early Blight with
 about 84% confidence. The Foundry IQ service — that's Azure
 AI Foundry's inference endpoint, gpt-4o-mini — generated a
 structured treatment plan grounded in USDA Extension documents
 we loaded into context at startup. Copper hydroxide at
 2.5 grams per liter, every 7 days, for 3 weeks. Organic
 alternative: neem oil at 5ml per liter."

"And the market intelligence service uses Meta's Prophet
 forecasting model against USDA National Agricultural
 Statistics Service price data. It's projecting tomato prices
 will shift by some percent in 3 weeks, so the recommendation
 is to either wait and sell at harvest or sell now — whichever
 the forecast says today."

----------------------------------------------------------------
T+3:00 - 3:30   WATCH KEDA SCALE BACK DOWN
----------------------------------------------------------------
"Job's done, Redis queue is empty. Watch the right pane — after
 KEDA's 30-second cooldown..."
  [The disease-detector pod terminates and disappears.]

"...there. Back to zero replicas. Zero compute cost again.
 The system idles for free until the next farmer uploads."

----------------------------------------------------------------
T+3:30 - 4:30   CLOSING
----------------------------------------------------------------
"This entire system runs in Kubernetes. Multi-tenant via
 namespaces — each crop region gets its own. Costs nothing
 when idle. Uses Azure AI Foundry's GitHub Models endpoint
 for safe, grounded agricultural advice. And the architecture
 scales from a single farmer to ten thousand without changing
 a line of application code."

"Built with FastAPI, Streamlit, Redis, PostgreSQL, HuggingFace
 Transformers, Meta Prophet, and KEDA on Kubernetes. All code
 is open source at github.com/ApurboBarua17/agrisense."

================================================================

When you're ready, this script will open the Streamlit frontend.
Press ENTER to launch, or Ctrl-C to abort and open it manually.
EOF

read -r _

say "Opening frontend (the tunnel will print URLs and stay in this terminal)"
exec minikube service frontend-service -n "$NS"

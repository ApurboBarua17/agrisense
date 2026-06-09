# AgriSense — Crop Disease & Market Intelligence Agent

> Hackathon: Agents League 2026 | Track: Reasoning Agents | Microsoft IQ: Foundry IQ

## What it does

AgriSense helps smallholder farmers identify crop diseases from a photo and get
actionable treatment advice + market sell-timing intelligence — all running on
a Kubernetes cluster with event-driven autoscaling.

## Core flow

A farmer uploads a photo → FastAPI gateway pushes the job to a Redis queue → **KEDA
detects the queue and scales the disease-detector pod from 0 → 1 automatically** →
a HuggingFace plant-disease model identifies the disease → **Azure AI Foundry
(Foundry IQ)** retrieves USDA-grounded treatment recommendations with citations →
**Meta Prophet + USDA NASS API** forecasts the crop market price → result is stored
in PostgreSQL and displayed in the Streamlit UI.

## Why Kubernetes + KEDA?

During harvest season, image upload volume spikes 10-50x. KEDA's Redis-based
autoscaling means disease-detector pods scale from 0 → 10 based on actual queue
depth. Zero idle compute. Pay only for work done. Each crop region runs in its
own namespace (multi-tenant architecture).

## Microsoft IQ integration

**Foundry IQ** (Azure AI Foundry) indexes USDA Extension agricultural documents
and returns grounded, cited treatment recommendations — reducing hallucination
risk for safety-critical agricultural advice.

## Tech stack

- Kubernetes (Minikube locally, AKS-ready)
- KEDA v2.13 — event-driven autoscaling
- Azure AI Foundry + Foundry IQ
- HuggingFace Transformers — plant disease classification
- Meta Prophet — time-series forecasting
- USDA NASS API — free government market data
- FastAPI, Streamlit, Redis, PostgreSQL
- Python 3.11

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                    │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                    │
│  │   Streamlit  │───▶│  API Gateway │                    │
│  │  (frontend)  │    │   (FastAPI)  │                    │
│  └──────────────┘    └──────┬───────┘                    │
│                             │ LPUSH disease_jobs          │
│                             ▼                            │
│                      ┌──────────────┐                    │
│                      │    Redis     │◀── KEDA watches     │
│                      │   (queue)    │    list length      │
│                      └──────┬───────┘                    │
│                             │ BLPOP                       │
│                             ▼                            │
│                   ┌──────────────────┐                   │
│        KEDA ─────▶│ Disease Detector │ (scales 0→10)     │
│                   │  (HuggingFace)   │                   │
│                   └────────┬─────────┘                   │
│                            │                             │
│               ┌────────────┴────────────┐                │
│               ▼                         ▼                │
│  ┌──────────────────────┐  ┌─────────────────────────┐   │
│  │  Foundry IQ Service  │  │  Market Intel Service   │   │
│  │ (Azure AI Foundry +  │  │  (Prophet + USDA NASS)  │   │
│  │   USDA knowledge)    │  └────────────┬────────────┘   │
│  └──────────┬───────────┘               │                │
│             └──────────────┬────────────┘                │
│                            ▼                             │
│                   ┌──────────────────┐                   │
│                   │   PostgreSQL     │                   │
│                   │  (result store)  │                   │
│                   └──────────────────┘                   │
└──────────────────────────────────────────────────────────┘
```

## Running locally

### Prerequisites

- Docker Desktop
- Python 3.11
- (For K8s) Minikube + kubectl

### Quick start — Docker Compose

```bash
cp .env.example .env
# Fill in AZURE_AI_PROJECT_CONNECTION_STRING and USDA_NASS_API_KEY
docker-compose up --build
# Open http://localhost:8501
```

The first build takes ~10 minutes — the disease-detector image pre-downloads
the HuggingFace model so pod startup is fast in K8s.

### Full Kubernetes deployment

```bash
./scripts/setup.sh    # installs Minikube + KEDA
./scripts/build-and-push.sh
./scripts/deploy.sh
minikube service frontend-service -n agrisense
```

### Watch KEDA scale in real time

```bash
watch kubectl get pods -n agrisense
# Upload an image in the UI, watch disease-detector scale 0 → 1 → 0
```

## Useful commands

```bash
# Check KEDA scaling status
kubectl get scaledobject -n agrisense
kubectl describe scaledobject disease-detector-scaler -n agrisense

# Check Redis queue depth
kubectl exec -it deploy/redis -n agrisense -- redis-cli llen disease_jobs

# View logs
kubectl logs -f deploy/disease-detector -n agrisense
kubectl logs -f deploy/api-gateway -n agrisense

# Rebuild and redeploy one service
eval $(minikube docker-env)
docker build -t agrisense-disease-detector:latest ./services/disease-detector/
kubectl rollout restart deployment/disease-detector -n agrisense
```

## Team

Apurbo Barua — University of Arizona, CS Senior

## License

MIT

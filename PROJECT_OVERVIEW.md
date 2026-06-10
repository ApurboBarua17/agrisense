# AgriSense — Project Overview

A Kubernetes-native multi-service AI agent that diagnoses crop disease from a single photo and returns USDA-grounded treatment recommendations plus a market sell-timing forecast. Built for the Agents League 2026 hackathon, Reasoning Agents track.

## What it does

A farmer takes a photo of a diseased plant on their phone and uploads it through a Streamlit interface. Within roughly thirty seconds AgriSense returns three things: the specific disease identified with a confidence score, a structured treatment plan with both chemical and organic protocols (citing USDA Extension sources), and a price forecast for the affected crop with a sell-or-wait recommendation. The goal is to bridge the gap between "do nothing" and "hire a consultant" for the demographic that loses the most to preventable crop disease — smallholders globally lose an estimated $220 billion each year to issues a phone-based diagnosis could catch early.

## How it works

The system is composed of five Python microservices behind a Streamlit frontend, orchestrated by Kubernetes with KEDA for event-driven autoscaling, and backed by Redis (job queue) and PostgreSQL (result store). When the farmer uploads an image, the API gateway validates it, persists a pending row in PostgreSQL, and pushes the job onto a Redis list. KEDA polls the list length continuously and materializes the disease-detector pod from zero replicas the moment a job arrives — meaning when no farmers are uploading, the detector consumes no CPU at all.

The detector loads a HuggingFace vision model (a MobileNetV2 fine-tuned on PlantVillage, returning 38-class classification with top-3 confidence scores) and runs inference. It then fans out two parallel HTTP calls. The first goes to Foundry IQ, a service that wraps the GitHub Models inference endpoint (Azure AI Foundry's OpenAI-compatible gateway) and grounds responses with USDA Extension agricultural documents loaded at service startup. The second goes to Market Intel, which fits a Meta Prophet time-series model on USDA National Agricultural Statistics Service historical prices and projects forward by the requested horizon. Both responses join the detection result in a single PostgreSQL row, and the Streamlit frontend polls until the row is complete before rendering the result.

## Engineering decisions worth calling out

The most architecturally interesting piece is the autoscaling behavior. KEDA watches the Redis queue with `listLength: 1` and `minReplicaCount: 0`, so the system genuinely costs nothing at rest — there is no idle worker burning a CPU. This was the right choice for the workload, which is bursty: harvest season sees ten to fifty times normal upload volume in localized regions, and pre-allocating capacity for that peak would be wasteful. The same ScaledObject scales up to ten replicas under load and back to zero after a thirty-second cooldown.

Grounding the language model was the other significant decision. A naive call to a generic chat model can hallucinate concentrations, schedules, and disease descriptions in ways that are genuinely dangerous for agricultural advice — the wrong fungicide concentration can kill the crop. Foundry IQ reads USDA Extension PDFs and text files at service startup, extracts text with pypdf, and embeds the first six thousand characters into every prompt's system message. The model still has freedom to format the response, but the concentrations and schedules it cites come from primary sources, not from training-data recall.

A few smaller production-grade touches that aren't headline features but matter for keeping the system honest. The API gateway and the worker both call an idempotent `CREATE TABLE IF NOT EXISTS` on startup, so neither has to boot in a strict order. Market Intel falls back to deterministic mock historical data when the USDA NASS API is unreachable, so the demo keeps working when the upstream is down. Foundry IQ has a deterministic fallback treatment string for when the LLM call errors, so the worker never returns nothing to the user. The disease-detector image pre-downloads the HuggingFace model weights at Docker build time, so KEDA pod cold-start is roughly fifteen seconds instead of three minutes. The Streamlit theme is split into a `.streamlit/config.toml` for tokens that Streamlit's built-in theme engine consumes and a CSS injection for the bits the theme can't reach, so widgets added in the future pick up the palette automatically.

The launcher scripts are also worth noting. `scripts/start.sh` is a single command that bootstraps the entire system from any cold state — checks `.env`, verifies Docker is running, installs Minikube and kubectl via Homebrew if missing, starts the cluster, installs KEDA, builds any missing service images into Minikube's separate Docker daemon, applies the manifests, waits for pods to be ready, and opens the UI. Every step is idempotent, so the same command works for "first time on this laptop" and "third time today" without modification. `scripts/stop.sh` mirrors it for teardown. There's also a `scripts/demo.sh` that preps the cluster for a clean recording (drains the queue, truncates the result table, waits for KEDA to scale to zero) and prints timed narration cues for the demo video.

## Tech stack

Python 3.11 for every service. FastAPI 0.111 with uvicorn for the three HTTP APIs (gateway, foundry-iq, market-intel). A plain `redis.blpop` loop for the disease-detector worker, since it doesn't need an HTTP surface — KEDA-scaled deployments are easier to reason about as queue consumers than as web servers. Streamlit 1.35 for the frontend. HuggingFace transformers 4.41 with PyTorch 2.3 for vision inference. Meta Prophet 1.1.5 with pandas 2.2 and numpy 1.26 for forecasting (numpy pinned below 2.0 because Prophet 1.1.5 still references `np.float_`). The OpenAI Python SDK 1.30 pointed at `models.inference.ai.azure.com` for the LLM, with httpx pinned to 0.27.2 because newer httpx versions removed a `proxies` kwarg the older OpenAI client passes. pypdf 4.2 for PDF text extraction. psycopg2-binary 2.9 for PostgreSQL. Redis 7.2-alpine. PostgreSQL 16-alpine. Kubernetes via Minikube 1.35 locally. KEDA 2.13 for the autoscaling. Docker Compose v2 for the development loop. GitHub Actions for CI, running ruff lint, kubectl manifest validation, and a Docker build matrix across four of the five service images on every push.

## By the numbers

These are the data points to pull from when writing this up for a resume.

- **5** microservices, **7** containers in the production posture, roughly **2,100** lines of Python code plus another **400** of YAML/shell.
- **17** Kubernetes manifests, **1** KEDA `ScaledObject`, **1** ConfigMap, **1** Secret.
- **0** is the minimum replica count for the disease-detector. Verified end-to-end: deployment goes 0 → 1 → 0 within sixty seconds of an image upload (about fifteen to thirty seconds for KEDA scale-up, the model runs, then thirty seconds of cooldown).
- **38**-class disease classification from the HuggingFace model, top-3 returned with confidence.
- **6,000** characters of USDA Extension documents embedded into every treatment-generation prompt as grounding context.
- **14** USDA-commodity mappings in Market Intel covering the most-traded crops in the model's class list.
- **5**-tier sell/wait recommendation logic in Market Intel (`SELL NOW` / `LEAN TOWARD SELLING` / `MARKET STABLE` / `SLIGHT ADVANTAGE IN WAITING` / `WAIT TO SELL`).
- **One** command (`./scripts/start.sh minikube`) bootstraps from clone to working UI; the cold path takes roughly fifteen minutes (most of which is downloading the HuggingFace model into the Minikube image), the warm path takes about three seconds.
- **9** git commits across the build, all on `main`, including spec-divergence fixes, the GitHub Models swap, label-parser hardening, K8s wiring updates, the Streamlit theme, and the demo automation.

## Repository

`github.com/ApurboBarua17/agrisense`

## License

MIT

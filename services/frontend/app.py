"""Streamlit frontend for AgriSense."""
import os
import time
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://api-gateway-service:8000")

st.set_page_config(
    page_title="AgriSense",
    page_icon="🌾",
    layout="centered",
)

st.title("🌾 AgriSense")
st.subheader("Crop Disease Detection & Market Intelligence")
st.caption("Powered by Azure AI Foundry (Foundry IQ) + Kubernetes + KEDA")
st.markdown("---")


def display_results(data: dict) -> None:
    st.markdown("---")
    detection = data.get("detection") or {}
    treatment = data.get("treatment") or ""
    market = data.get("market") or {}

    crop = detection.get("crop", "Unknown")
    disease = detection.get("disease", "Unknown")
    confidence = detection.get("confidence", 0)
    is_healthy = detection.get("is_healthy", False)
    severity = detection.get("severity", "unknown")
    urgent = detection.get("urgent", False)

    if is_healthy:
        st.success(f"## ✅ {crop} — Healthy!")
        st.write(f"Confidence: **{confidence}%**")
    else:
        if urgent:
            st.error(f"## ⚠️ {crop} — {disease}")
        else:
            st.warning(f"## 🔍 {crop} — {disease}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Confidence", f"{confidence}%")
        col2.metric("Severity", str(severity).capitalize())
        col3.metric("Urgent?", "Yes ⚠️" if urgent else "No")

    if treatment and not is_healthy:
        with st.expander("💊 Treatment Recommendations (via Foundry IQ + USDA)", expanded=True):
            st.markdown(treatment)
            st.caption("Source: Azure AI Foundry (Foundry IQ) grounded on USDA Extension Documents")

    if market and not market.get("error"):
        with st.expander("📈 Market Intelligence (Prophet + USDA NASS)", expanded=True):
            col1, col2, col3 = st.columns(3)

            current = market.get("current_price", 0)
            forecast = market.get("forecast_price", 0)
            pct = market.get("pct_change", 0)
            trend = market.get("trend", "stable")
            unit = market.get("unit", "$/lb")
            weeks = market.get("forecast_weeks", 3)

            unit_suffix = unit.split("/")[-1] if "/" in unit else "lb"
            col1.metric("Current Price", f"${current:.2f}/{unit_suffix}")
            col2.metric(
                f"Forecast ({weeks}wk)",
                f"${forecast:.2f}/{unit_suffix}",
                delta=f"{pct:+.1f}%",
            )
            trend_emoji = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"
            col3.metric("Trend", f"{trend_emoji} {trend.capitalize()}")

            recommendation = market.get("recommendation", "")
            if "WAIT" in recommendation:
                st.success(f"💡 **{recommendation}**")
            elif "SELL NOW" in recommendation:
                st.error(f"💡 **{recommendation}**")
            else:
                st.info(f"💡 **{recommendation}**")

            st.caption("Forecast powered by Meta Prophet + USDA NASS historical price data")

    top_preds = detection.get("top_predictions", [])
    if top_preds:
        with st.expander("🔬 Model Predictions (top-3)"):
            for pred in top_preds:
                label = pred["label"].replace("___", " → ").replace("_", " ")
                conf = pred["confidence"]
                st.progress(min(int(conf), 100), text=f"{label}: {conf}%")


# --- Upload section ---
uploaded_file = st.file_uploader(
    "Upload a photo of your plant",
    type=["jpg", "jpeg", "png"],
    help="Take a photo of the diseased leaf and upload it here",
)

if uploaded_file:
    col1, col2 = st.columns([1, 1])

    with col1:
        # NOTE: use_column_width on streamlit 1.35; use_container_width for st.image
        # was added in 1.42. Keep this paired with the streamlit pin in requirements.txt.
        st.image(uploaded_file, caption="Uploaded image", use_column_width=True)

    with col2:
        st.info("📤 Image ready. Click Analyze to detect disease.")
        analyze_btn = st.button(
            "🔍 Analyze Plant", type="primary", use_container_width=True
        )

    if analyze_btn:
        with st.spinner("Queuing image for analysis... (watch KEDA scale the pod)"):
            try:
                resp = requests.post(
                    f"{API_URL}/analyze",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()
                job_id = result["job_id"]
                st.success(f"✅ Job queued: `{job_id[:8]}...`")
            except Exception as e:
                st.error(f"Failed to submit: {e}")
                st.stop()

        progress = st.progress(0, text="Waiting for KEDA to scale disease-detector pod...")

        max_attempts = 60
        completed = False
        for attempt in range(max_attempts):
            time.sleep(2)
            progress_pct = min(int((attempt / max_attempts) * 100), 95)

            if attempt < 5:
                msg = "⏳ KEDA detecting queue... spinning up disease-detector pod..."
            elif attempt < 15:
                msg = "🤖 Disease detector running... analyzing image..."
            elif attempt < 25:
                msg = "📚 Foundry IQ retrieving treatment from USDA knowledge base..."
            else:
                msg = "📈 Market intelligence service forecasting prices..."

            progress.progress(progress_pct, text=msg)

            try:
                poll_resp = requests.get(f"{API_URL}/result/{job_id}", timeout=10)
                poll_data = poll_resp.json()

                if poll_data.get("status") == "complete":
                    progress.progress(100, text="✅ Analysis complete!")
                    display_results(poll_data)
                    completed = True
                    break
            except Exception:
                continue

        if not completed:
            st.warning("Analysis is taking longer than expected. Check pod logs.")


# --- Sidebar ---
with st.sidebar:
    st.header("System Status")

    try:
        requests.get(f"{API_URL}/health", timeout=3).json()
        st.success("API Gateway: Online")
    except Exception:
        st.error("API Gateway: Offline")

    try:
        queue = requests.get(f"{API_URL}/queue-depth", timeout=3).json()
        depth = queue.get("queue_depth", 0)
        st.metric("Redis Queue Depth", depth)
        if depth > 0:
            st.info("KEDA is scaling disease-detector pods now!")
    except Exception:
        st.warning("Queue: Unavailable")

    st.markdown("---")
    st.markdown("**Architecture**")
    st.markdown(
        """
- Streamlit → FastAPI gateway
- Gateway → Redis queue
- KEDA scales disease-detector
- HuggingFace plant-disease model
- Azure Foundry IQ (USDA docs)
- Meta Prophet + USDA NASS
- PostgreSQL result store
"""
    )

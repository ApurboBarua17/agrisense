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

# Production-grade visual polish. Theme tokens live in .streamlit/config.toml;
# this block handles typography, spacing, cards, and component overrides
# Streamlit's theme tokens can't reach. Keep it tight — no external fonts/JS.
st.markdown(
    """
    <style>
      /* --- Typography ----------------------------------------------------- */
      html, body, [class*="st-"], .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                     Roboto, "Helvetica Neue", Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }

      /* --- Layout --------------------------------------------------------- */
      .stApp { background: #F8FAF6; }
      .main .block-container {
        padding-top: 2.25rem;
        padding-bottom: 3rem;
        max-width: 760px;
      }

      /* --- Hero ----------------------------------------------------------- */
      .agri-hero {
        position: relative;
        overflow: hidden;
        background: linear-gradient(135deg, #15803D 0%, #16A34A 60%, #22C55E 100%);
        color: #ffffff;
        padding: 1.8rem 2rem 1.5rem 2rem;
        border-radius: 16px;
        margin: 0.25rem 0 1.5rem 0;
        box-shadow:
          0 1px 2px rgba(15, 23, 42, 0.06),
          0 10px 28px rgba(22, 163, 74, 0.20);
      }
      .agri-hero::before {
        content: "";
        position: absolute; inset: 0;
        background: radial-gradient(
          circle at 100% 0%,
          rgba(255, 255, 255, 0.16) 0%,
          rgba(255, 255, 255, 0) 55%
        );
        pointer-events: none;
      }
      .agri-hero-title {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.025em;
        line-height: 1.15;
      }
      .agri-hero-subtitle {
        margin: 0.45rem 0 0 0;
        font-size: 0.97rem;
        line-height: 1.5;
        opacity: 0.94;
        font-weight: 400;
        max-width: 38rem;
      }
      .agri-hero-badges {
        display: flex;
        gap: 0.45rem;
        margin-top: 1.1rem;
        flex-wrap: wrap;
      }
      .agri-badge {
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.22);
        color: #ffffff;
        padding: 0.25rem 0.7rem;
        font-size: 0.73rem;
        font-weight: 500;
        letter-spacing: 0.01em;
        border-radius: 999px;
      }

      /* --- File uploader -------------------------------------------------- */
      [data-testid="stFileUploader"] section {
        border: 2px dashed #16A34A !important;
        background: linear-gradient(180deg, #F7FCF5 0%, #ECFDF5 100%) !important;
        border-radius: 14px !important;
        padding: 1.25rem !important;
        transition: background 0.15s ease, border-color 0.15s ease;
      }
      [data-testid="stFileUploader"] section:hover {
        background: linear-gradient(180deg, #F0FDF4 0%, #DCFCE7 100%) !important;
        border-color: #15803D !important;
      }

      /* --- Buttons -------------------------------------------------------- */
      .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        letter-spacing: 0.01em;
        transition: transform 0.1s ease, box-shadow 0.15s ease, background 0.15s ease;
      }
      .stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #16A34A 0%, #15803D 100%);
        border: none;
        color: #ffffff;
        box-shadow: 0 1px 2px rgba(22, 163, 74, 0.25);
      }
      .stButton > button[kind="primary"]:hover {
        background: linear-gradient(180deg, #22C55E 0%, #16A34A 100%);
        box-shadow: 0 3px 8px rgba(22, 163, 74, 0.30);
        transform: translateY(-1px);
      }

      /* --- Expanders as cards -------------------------------------------- */
      [data-testid="stExpander"] {
        border: 1px solid #E5E7EB !important;
        border-radius: 12px !important;
        background: #ffffff !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        margin-bottom: 0.75rem;
        overflow: hidden;
      }
      [data-testid="stExpander"] details summary {
        padding: 0.85rem 1.1rem !important;
        font-weight: 600 !important;
        background: #FAFBFA;
      }
      [data-testid="stExpander"] details[open] summary {
        border-bottom: 1px solid #E5E7EB;
      }

      /* --- Metrics ------------------------------------------------------- */
      [data-testid="stMetric"] {
        background: #ffffff;
        padding: 0.95rem 1rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
      }
      [data-testid="stMetricLabel"] {
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        color: #6B7280 !important;
      }
      [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
        color: #111827 !important;
      }

      /* --- Alert banners (success/warning/error/info) -------------------- */
      [data-testid="stAlert"] {
        border-radius: 12px !important;
        border-left-width: 4px !important;
        padding: 0.9rem 1.1rem !important;
        font-weight: 500;
      }

      /* --- Progress bar -------------------------------------------------- */
      [data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #16A34A 0%, #22C55E 100%) !important;
      }

      /* --- Sidebar polish ------------------------------------------------ */
      [data-testid="stSidebar"] {
        background: #F4F4EE;
        border-right: 1px solid #E5E7EB;
      }
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3 {
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #4B5563 !important;
        font-weight: 700 !important;
      }

      /* --- Dividers ------------------------------------------------------ */
      hr {
        border-color: #E5E7EB !important;
        margin: 1.5rem 0 !important;
      }

      /* --- Footer -------------------------------------------------------- */
      .agri-footer {
        margin: 2.5rem 0 0 0;
        padding: 1.25rem 0 0 0;
        border-top: 1px solid #E5E7EB;
        font-size: 0.78rem;
        color: #6B7280;
        text-align: center;
        line-height: 1.6;
      }
      .agri-footer a {
        color: #15803D;
        text-decoration: none;
        font-weight: 500;
      }
      .agri-footer a:hover { text-decoration: underline; }
    </style>

    <div class="agri-hero">
      <h1 class="agri-hero-title">🌾 AgriSense</h1>
      <p class="agri-hero-subtitle">
        Diagnose crop disease from a single photo — and get USDA-grounded treatment
        plus market sell-timing in seconds.
      </p>
      <div class="agri-hero-badges">
        <span class="agri-badge">Foundry IQ</span>
        <span class="agri-badge">HuggingFace ViT</span>
        <span class="agri-badge">Prophet</span>
        <span class="agri-badge">KEDA autoscaling</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


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

# Footer
st.markdown(
    """
    <div class="agri-footer">
      AgriSense · Agents League 2026 · Reasoning Agents track<br>
      <a href="https://github.com/ApurboBarua17/agrisense" target="_blank">github.com/ApurboBarua17/agrisense</a>
    </div>
    """,
    unsafe_allow_html=True,
)

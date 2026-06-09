"""
Azure AI Foundry agent setup.

SETUP STEPS (do these manually before deploying):
1. Go to https://ai.azure.com
2. Create a new project (free tier)
3. Copy the connection string from Settings
4. Set env var: AZURE_AI_PROJECT_CONNECTION_STRING
5. Drop USDA extension PDFs into services/foundry-iq/usda_docs/
6. (Optional) After the first successful run, capture FOUNDRY_AGENT_ID and
   FOUNDRY_VECTOR_STORE_ID and set them as env vars so subsequent restarts
   reuse the same agent/vector store instead of recreating.

If AZURE_AI_PROJECT_CONNECTION_STRING is unset, this module operates in
FALLBACK MODE — get_treatment() returns a deterministic stub so the full
demo flow keeps working without Azure access.
"""
import os
from typing import Optional

CONNECTION_STRING = os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING", "").strip()
FALLBACK_MODE = not CONNECTION_STRING or CONNECTION_STRING == "your-connection-string-here"

KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "usda_docs")

_client = None
_agent_id: Optional[str] = None
_vector_store_id: Optional[str] = None


def _get_system_prompt() -> str:
    return """You are AgriSense, an agricultural expert AI assistant.

When asked about a plant disease, provide:
1. A brief disease description (1-2 sentences)
2. Immediate action (what to do today)
3. Chemical treatment: specific product, concentration, and application schedule
4. Organic/natural alternative treatment
5. Prevention for future seasons
6. Always cite USDA extension sources when available

Format your response as plain text, keeping it under 200 words.
Be specific with measurements (e.g., "2.5g per liter" not "apply some fungicide").
If the plant is healthy, congratulate the farmer and give preventive tips."""


def get_client():
    global _client
    if _client is None:
        # Import lazily so fallback mode doesn't need Azure SDK at import time
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        _client = AIProjectClient.from_connection_string(
            conn_str=CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )
    return _client


def setup_agent():
    """
    One-time setup: upload USDA docs and create the Foundry IQ agent.
    Reuses an existing agent if FOUNDRY_AGENT_ID is set.
    """
    global _agent_id, _vector_store_id

    if FALLBACK_MODE:
        print("[foundry] FALLBACK MODE — no AZURE_AI_PROJECT_CONNECTION_STRING set.")
        return

    existing_agent_id = os.environ.get("FOUNDRY_AGENT_ID")
    existing_vs_id = os.environ.get("FOUNDRY_VECTOR_STORE_ID")
    if existing_agent_id:
        _agent_id = existing_agent_id
        _vector_store_id = existing_vs_id
        print(f"[foundry] Reusing existing agent: {_agent_id}")
        return

    from azure.ai.projects.models import FileSearchTool

    client = get_client()

    print("[foundry] Uploading USDA documents to vector store...")
    file_ids = []

    if os.path.exists(KNOWLEDGE_BASE_DIR):
        for filename in os.listdir(KNOWLEDGE_BASE_DIR):
            if filename.endswith((".pdf", ".txt", ".md")):
                filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
                with open(filepath, "rb") as f:
                    uploaded = client.agents.upload_file_and_poll(
                        file=f, purpose="assistants"
                    )
                    file_ids.append(uploaded.id)
                    print(f"[foundry] Uploaded: {filename} -> {uploaded.id}")

    if not file_ids:
        print("[foundry] WARNING: No USDA docs found. Using model knowledge only.")
        agent = client.agents.create_agent(
            model="gpt-4o",
            name="agrisense-treatment-agent",
            instructions=_get_system_prompt(),
        )
    else:
        vector_store = client.agents.create_vector_store_and_poll(
            file_ids=file_ids,
            name="usda-extension-docs",
        )
        _vector_store_id = vector_store.id
        print(f"[foundry] Vector store created: {_vector_store_id}")

        file_search = FileSearchTool(vector_store_ids=[_vector_store_id])
        agent = client.agents.create_agent(
            model="gpt-4o",
            name="agrisense-treatment-agent",
            instructions=_get_system_prompt(),
            tools=file_search.definitions,
            tool_resources=file_search.resources,
        )

    _agent_id = agent.id
    print(f"[foundry] Agent created: {_agent_id}")


def _fallback_treatment(crop: str, disease: str, severity: str) -> str:
    """Deterministic stub used when Azure is not configured."""
    if "healthy" in disease.lower():
        return (
            f"Your {crop} plant appears healthy. Maintain consistent watering, "
            "rotate crops yearly, and monitor undersides of leaves weekly for "
            "early signs of disease. [Source: USDA Extension general guidance]"
        )
    return (
        f"Disease: {disease} on {crop} (severity: {severity}).\n\n"
        "Immediate action: Remove and destroy infected leaves. Avoid overhead watering.\n"
        "Chemical treatment: Apply copper-based fungicide (e.g., copper hydroxide) "
        "at 2.5 g/L every 7 days for 3 weeks. Begin at first sign of disease.\n"
        "Organic alternative: Neem oil at 5 mL/L applied weekly in early morning. "
        "Bacillus subtilis biofungicide is also effective for many fungal diseases.\n"
        "Prevention: Rotate crops on a 3-year cycle. Stake plants to improve airflow. "
        "Mulch to prevent soil splash onto lower leaves.\n\n"
        "[Source: USDA Extension Bulletins — fallback content, configure "
        "AZURE_AI_PROJECT_CONNECTION_STRING for grounded Foundry IQ responses]"
    )


def get_treatment(crop: str, disease: str, severity: str) -> str:
    """
    Query the Foundry IQ agent for treatment recommendations.
    Returns grounded text with citations.
    """
    if FALLBACK_MODE:
        return _fallback_treatment(crop, disease, severity)

    client = get_client()

    if not _agent_id:
        setup_agent()

    thread = client.agents.create_thread()

    client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content=(
            f"A farmer has a {severity} severity case of {disease} on their {crop} plant. "
            "Please provide specific treatment recommendations including:\n"
            "- Chemical treatment (product name, concentration, schedule)\n"
            "- Organic alternative\n"
            "- Immediate actions to take today\n"
            "- Prevention for next season"
        ),
    )

    client.agents.create_and_process_run(
        thread_id=thread.id,
        assistant_id=_agent_id,
    )

    messages = client.agents.list_messages(thread_id=thread.id)

    for msg in messages:
        if msg.role == "assistant":
            for content in msg.content:
                if hasattr(content, "text"):
                    return content.text.value

    return f"Treatment information for {disease} on {crop}: Consult your local agricultural extension office."

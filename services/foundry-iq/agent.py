from openai import OpenAI
from pypdf import PdfReader
import os

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN")
MODEL         = os.environ.get("AZURE_MODEL_DEPLOYMENT", "gpt-4o-mini")
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "usda_docs")

_client    = None
_knowledge = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=GITHUB_TOKEN
        )
    return _client


def load_knowledge() -> str:
    global _knowledge
    if _knowledge is not None:
        return _knowledge
    chunks = []
    if os.path.exists(KNOWLEDGE_DIR):
        for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
            filepath = os.path.join(KNOWLEDGE_DIR, filename)
            if filename.endswith(".txt"):
                with open(filepath, encoding="utf-8", errors="ignore") as f:
                    chunks.append(f"[Source: {filename}]\n{f.read()}")
            elif filename.endswith(".pdf"):
                try:
                    reader = PdfReader(filepath)
                    text   = "\n".join(p.extract_text() or "" for p in reader.pages)
                    chunks.append(f"[Source: {filename}]\n{text}")
                except Exception as e:
                    print(f"[foundry] Could not read {filename}: {e}")
    _knowledge = "\n\n---\n\n".join(chunks)
    print(f"[foundry] Loaded {len(chunks)} USDA docs | Model: {MODEL}")
    return _knowledge


def setup_agent():
    load_knowledge()
    try:
        get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        print("[foundry] GitHub Models connection OK")
    except Exception as e:
        print(f"[foundry] WARNING — connection failed: {e}")


def get_treatment(crop: str, disease: str, severity: str) -> str:
    knowledge = load_knowledge()
    system = """You are AgriSense, an agricultural expert AI assistant.
When asked about plant disease treatment always provide:
1. Brief disease description (1-2 sentences)
2. Chemical treatment: specific product, exact concentration, schedule
3. Organic/natural alternative with concentration
4. Immediate action the farmer should take today
5. Prevention tips for next season
Be specific with measurements (e.g. 2.5g/L every 7 days).
Keep response under 200 words. Cite USDA sources when available."""
    if knowledge:
        system += f"\n\nKnowledge base (USDA Extension Documents):\n{knowledge[:6000]}"
    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content":
                    f"Crop: {crop}\nDisease: {disease}\nSeverity: {severity}\n\n"
                    f"Provide specific treatment recommendations."}
            ],
            max_tokens=400,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[foundry] API error: {e}")
        return (f"For {disease} on {crop} ({severity} severity): apply copper-based "
                f"fungicide at 2.5g/L every 7 days for 3 weeks. Remove infected "
                f"leaves immediately. Consult extension.umn.edu for full guidance.")

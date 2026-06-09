"""HuggingFace plant disease classifier wrapper."""
from transformers import pipeline
from PIL import Image
import io

# PlantVillage 38-class disease classification model.
# If this exact model id stops working, swap to:
#   "ozair23/mobilenet_v2_1.0_224-finetuned-plantdisease"
MODEL_ID = "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"

DISEASE_INFO = {
    "healthy": {"severity": "none", "urgent": False},
    "Early_Blight": {"severity": "moderate", "urgent": False},
    "Late_Blight": {"severity": "high", "urgent": True},
    "Leaf_Mold": {"severity": "moderate", "urgent": False},
    "Bacterial_spot": {"severity": "high", "urgent": True},
    "Septoria_leaf_spot": {"severity": "moderate", "urgent": False},
    "Spider_mites": {"severity": "moderate", "urgent": False},
    "Target_Spot": {"severity": "moderate", "urgent": False},
    "Yellow_Leaf_Curl_Virus": {"severity": "high", "urgent": True},
    "Mosaic_virus": {"severity": "high", "urgent": True},
    "Black_rot": {"severity": "high", "urgent": True},
    "Cedar_apple_rust": {"severity": "moderate", "urgent": False},
    "Apple_scab": {"severity": "moderate", "urgent": False},
    "Common_rust": {"severity": "moderate", "urgent": False},
    "Northern_Leaf_Blight": {"severity": "moderate", "urgent": False},
    "Powdery_mildew": {"severity": "low", "urgent": False},
}

_pipe = None


def get_pipeline():
    global _pipe
    if _pipe is None:
        print(f"Loading model: {MODEL_ID}")
        _pipe = pipeline("image-classification", model=MODEL_ID)
        print("Model loaded.")
    return _pipe


def detect_disease(image_bytes: bytes) -> dict:
    pipe = get_pipeline()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    results = pipe(image, top_k=3)

    top = results[0]
    raw_label = top["label"]  # e.g. "Tomato___Early_Blight"

    parts = raw_label.split("___")
    crop = parts[0].replace("_", " ") if len(parts) > 0 else "Unknown"
    disease_raw = parts[1] if len(parts) > 1 else "Unknown"
    disease = disease_raw.replace("_", " ")
    is_healthy = "healthy" in disease.lower()

    meta = DISEASE_INFO.get(disease_raw, {"severity": "unknown", "urgent": False})

    return {
        "crop": crop,
        "disease": disease,
        "disease_raw": disease_raw,
        "confidence": round(top["score"] * 100, 1),
        "is_healthy": is_healthy,
        "severity": meta["severity"],
        "urgent": meta["urgent"],
        "top_predictions": [
            {
                "label": r["label"],
                "confidence": round(r["score"] * 100, 1),
            }
            for r in results
        ],
    }

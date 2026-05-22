import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OCR_PROJECT_DIR = PROJECT_ROOT / "backend" / "ocr"

class Config:
    SECRET_KEY      = os.getenv("SECRET_KEY", "dev-secret")
    MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_parking")
    ADMIN_USERNAME  = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "admin123")
    OCR_PROJECT_DIR = os.getenv(
        "OCR_PROJECT_DIR",
        str(DEFAULT_OCR_PROJECT_DIR),
    )
    OCR_MODEL_PATH = os.getenv("OCR_MODEL_PATH", "model.onnx")
    OCR_UPLOAD_DIR = os.getenv("OCR_UPLOAD_DIR", str(PROJECT_ROOT / "backend" / "uploads" / "entry"))
    OCR_OUTPUT_DIR = os.getenv("OCR_OUTPUT_DIR", str(PROJECT_ROOT / "backend" / "uploads" / "entry_outputs"))
    OCR_MODE = os.getenv("OCR_MODE", "auto")
    OCR_FALLBACK = os.getenv("OCR_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}
    OCR_GPU = os.getenv("OCR_GPU", "false").lower() in {"1", "true", "yes", "on"}
    OCR_DETECTOR_CONFIDENCE = float(os.getenv("OCR_DETECTOR_CONFIDENCE", "0.5"))

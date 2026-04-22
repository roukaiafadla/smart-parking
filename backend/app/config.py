import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY      = os.getenv("SECRET_KEY", "dev-secret")
    MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_parking")
    ADMIN_USERNAME  = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "admin123")
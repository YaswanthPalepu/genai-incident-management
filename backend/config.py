import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Configuration
MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "incident_db")

# LLM Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Vector Database Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")

# Knowledge Base Configuration
KB_FILE_PATH = os.getenv("KB_FILE_PATH", "knowledge_base.txt")

# Application Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))

# CORS Configuration (for main.py)
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173", 
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
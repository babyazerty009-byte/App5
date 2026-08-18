"""
App5 Configuration.
Loads environment variables from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bitrix24 Webhook URL (Inbound webhook)
BITRIX24_WEBHOOK_URL = os.getenv("BITRIX24_WEBHOOK_URL", "")

# Groq API Key (free: https://console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Available models on Groq (free tier)
AVAILABLE_MODELS = {
    # Llama (Meta) 
    "llama-3.3-70b-versatile": "Llama 3.3 70B — Most capable (recommended)",
    #Qwen (Alibaba) 
    "qwen/qwen3.6-27b": "Qwen 3.6 27B — Good reasoning",
    # GPT-OSS (OpenAI open-source) 
    "openai/gpt-oss-120b": "GPT-OSS 120B — Very capable",
}

# Default model
DEFAULT_MODEL = "openai/gpt-oss-120b"

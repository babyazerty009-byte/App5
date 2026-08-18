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

# Available models on Groq (free tier) — must support tool calling
AVAILABLE_MODELS = {
    # GPT-OSS (OpenAI open-source)
    "openai/gpt-oss-120b": "GPT-OSS 120B — Most capable (recommended)",
    "openai/gpt-oss-20b": "GPT-OSS 20B — Fast and lightweight",
    # Qwen (Alibaba)
    "qwen/qwen3.6-27b": "Qwen 3.6 27B — Good reasoning",
}

# Default model
DEFAULT_MODEL = "openai/gpt-oss-120b"

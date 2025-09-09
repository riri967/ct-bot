# Configuration file for API keys and settings
import os
import streamlit as st

# Get API keys from environment variables (Streamlit secrets or env vars)
def get_api_key(key_name, fallback_key='GEMINI_API_KEY'):
    # Try Streamlit secrets first (for cloud deployment)
    if hasattr(st, 'secrets') and key_name in st.secrets:
        return st.secrets[key_name]
    # Fall back to environment variables
    return os.getenv(key_name, os.getenv(fallback_key, ''))

# Multiple Gemini API keys for load distribution
GEMINI_API_KEYS = {
    'stimulus_generation': get_api_key('GEMINI_API_KEY_1', 'GEMINI_API_KEY'),  # For RAG stimulus generation
    'socratic_responses': get_api_key('GEMINI_API_KEY_2', 'GEMINI_API_KEY'),   # For chatbot responses  
    'question_generation': get_api_key('GEMINI_API_KEY_3', 'GEMINI_API_KEY')  # For initial questions
}

# Backward compatibility
GEMINI_API_KEY = GEMINI_API_KEYS['stimulus_generation']

# Database settings
DATABASE_PATH = "study_data.db"

# Other settings
DEBUG_MODE = False
MAX_RETRIES = 2  # Retry with different keys if one fails
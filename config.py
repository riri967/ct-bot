# Configuration file for API keys and settings
import os
import streamlit as st

# Get API keys from environment variables (Streamlit secrets or env vars)
def get_api_key(key_name, fallback_key='GEMINI_API_KEY'):
    # Try Streamlit secrets first (for cloud deployment)
    try:
        if hasattr(st, 'secrets') and key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
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



# Database settings - Prioritize Supabase for deployment
def get_supabase_url():
    try:
        if hasattr(st, 'secrets') and 'supabase_url' in st.secrets:
            return st.secrets['supabase_url']
    except Exception:
        pass
    return os.getenv('SUPABASE_URL', '')

def get_supabase_key():
    try:
        if hasattr(st, 'secrets') and 'supabase_key' in st.secrets:
            return st.secrets['supabase_key']
    except Exception:
        pass
    return os.getenv('SUPABASE_ANON_KEY', '')

# Use Supabase for deployment, SQLite for local development
USE_SUPABASE = bool(get_supabase_url() and get_supabase_key())
DATABASE_PATH = "study_data.db"  # Fallback for local development

# Other settings
MAX_RETRIES = 2  # Retry with different keys if one fails
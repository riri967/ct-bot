# Configuration file for API keys and settings
# Keep this file secure and don't commit to version control

# Multiple Gemini API keys for load distribution
# Replace these with your 3 different API keys:
GEMINI_API_KEYS = {
    'stimulus_generation': "AIzaSyCSZPXbPhtiBPwHegQxn2xbOx5Eb1ybPpI",  # For RAG stimulus generation
    'socratic_responses': "AIzaSyCSZPXbPhtiBPwHegQxn2xbOx5Eb1ybPpI",   # For chatbot responses  
    'question_generation': "AIzaSyCSZPXbPhtiBPwHegQxn2xbOx5Eb1ybPpI"  # For initial questions
}

# Backward compatibility
GEMINI_API_KEY = GEMINI_API_KEYS['stimulus_generation']

# Database settings
DATABASE_PATH = "study_data.db"

# Other settings
DEBUG_MODE = False
MAX_RETRIES = 2  # Retry with different keys if one fails
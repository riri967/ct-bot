"""
API utilities for managing multiple Gemini API keys and handling rate limits
"""

import google.generativeai as genai
import time
import random
from config import GEMINI_API_KEYS, MAX_RETRIES

def get_model_with_retry(model_name='gemini-1.5-flash', purpose='general', **generation_config):
    """
    Get a Gemini model with automatic API key rotation and retry logic
    
    Args:
        model_name: Gemini model to use
        purpose: Which API key to use ('stimulus_generation', 'socratic_responses', 'question_generation')
        **generation_config: Model configuration parameters
    
    Returns:
        Configured GenerativeModel instance
    """
    # Determine which API key to use
    if purpose in GEMINI_API_KEYS:
        primary_key = GEMINI_API_KEYS[purpose]
    else:
        primary_key = GEMINI_API_KEYS['stimulus_generation']  # Default fallback
    
    # Try primary key first
    try:
        genai.configure(api_key=primary_key)
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        # Test the configuration with a simple call
        test_response = model.generate_content("Test", request_options={"timeout": 10})
        return model
    except Exception as e:
        print(f"Primary API key for {purpose} failed: {str(e)[:50]}...")
        
        # Try other keys as backup
        other_keys = [key for key in GEMINI_API_KEYS.values() if key != primary_key]
        for backup_key in other_keys:
            try:
                print(f"Trying backup API key...")
                genai.configure(api_key=backup_key)
                model = genai.GenerativeModel(model_name, generation_config=generation_config)
                test_response = model.generate_content("Test", request_options={"timeout": 10})
                print("✅ Backup key working")
                return model
            except Exception as backup_error:
                print(f"Backup key failed: {str(backup_error)[:50]}...")
                continue
        
        # All keys failed
        raise Exception(f"All API keys failed for {purpose}. Check your keys and quotas.")

def generate_with_retry(model, prompt, max_retries=MAX_RETRIES):
    """
    Generate content with automatic retry and exponential backoff
    
    Args:
        model: GenerativeModel instance
        prompt: Content to generate
        max_retries: Maximum number of retry attempts
        
    Returns:
        Generated text content
    """
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if attempt == max_retries:
                raise e
            
            # Check if it's a rate limit error
            error_str = str(e).lower()
            if any(term in error_str for term in ['rate limit', 'quota', 'too many requests']):
                wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                print(f"Rate limit hit, waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
            else:
                # Non-rate-limit error, re-raise immediately
                raise e
    
    raise Exception(f"Failed to generate content after {max_retries + 1} attempts")

def test_all_keys():
    """Test all configured API keys"""
    print("=== Testing All API Keys ===")
    
    for purpose, api_key in GEMINI_API_KEYS.items():
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Hello")
            print(f"✅ {purpose}: Key working - {response.text[:30]}...")
        except Exception as e:
            print(f"❌ {purpose}: {str(e)[:50]}...")
    
    print("\n=== Testing Retry System ===")
    try:
        model = get_model_with_retry(purpose='stimulus_generation')
        response = generate_with_retry(model, "Create a test message")
        print(f"✅ Retry system: {response[:50]}...")
    except Exception as e:
        print(f"❌ Retry system failed: {e}")

if __name__ == "__main__":
    test_all_keys()
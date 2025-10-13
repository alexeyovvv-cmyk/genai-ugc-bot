#!/usr/bin/env python3
"""Test script for Replicate Veo 3 integration."""

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, '/Users/alex/Vibe_coding')

load_dotenv()

def test_replicate_setup():
    """Test if Replicate is properly configured."""
    print("Testing Replicate setup...")
    
    # Check if token is set
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        print("❌ REPLICATE_API_TOKEN not found in environment")
        print("Please add REPLICATE_API_TOKEN to your .env file")
        print("Get your token from: https://replicate.com/account/api-tokens")
        return False
    
    if token == "your_replicate_api_token_here":
        print("❌ REPLICATE_API_TOKEN is still set to example value")
        print("Please replace with your actual token from: https://replicate.com/account/api-tokens")
        return False
    
    print(f"✅ REPLICATE_API_TOKEN found: {token[:10]}...")
    
    # Test import
    try:
        import replicate
        print("✅ Replicate package imported successfully")
    except ImportError:
        print("❌ Replicate package not installed")
        print("Run: pip install replicate")
        return False
    
    # Test client initialization
    try:
        client = replicate.Client(api_token=token)
        print("✅ Replicate client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Replicate client: {e}")
        return False
    
    print("\n🎉 Replicate setup is ready!")
    print("You can now test video generation with your bot.")
    
    return True

if __name__ == "__main__":
    test_replicate_setup()

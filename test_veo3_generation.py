#!/usr/bin/env python3
"""Test Veo 3 video generation via Replicate."""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, '/Users/alex/Vibe_coding')

load_dotenv()

async def test_veo3_generation():
    """Test Veo 3 video generation."""
    print("🎬 Testing Veo 3 video generation via Replicate...")
    
    try:
        from tg_bot.services.vertex_service import generate_video_veo3
        
        # Test prompt
        test_prompt = "A cat playing with a ball of yarn, cute and playful"
        
        print(f"Prompt: '{test_prompt}'")
        print("Generating video... (this may take 1-2 minutes)")
        
        # Generate video
        video_path = await generate_video_veo3(
            prompt=test_prompt,
            duration_seconds=4,  # Veo 3 supports 4s, 6s, 8s
            aspect_ratio="9:16"  # Mobile format
        )
        
        if video_path:
            print(f"✅ Video generated successfully!")
            print(f"📁 Path: {video_path}")
            print(f"📊 Size: {os.path.getsize(video_path)} bytes")
            return True
        else:
            print("❌ Video generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_veo3_generation())
    if result:
        print("\n🎉 Veo 3 integration is working!")
        print("You can now use video generation in your Telegram bot.")
    else:
        print("\n💥 Veo 3 integration failed.")
        print("Check the error messages above.")

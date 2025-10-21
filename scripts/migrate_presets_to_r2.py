#!/usr/bin/env python3
"""Migration script to upload preset files to R2."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tg_bot.services.r2_service import upload_file, test_connection

def migrate_presets():
    """Upload all preset files to R2."""
    print("🚀 Starting preset files migration to R2...")
    
    # Test R2 connection first
    if not test_connection():
        print("❌ R2 connection failed. Check credentials.")
        return False
    
    base_dir = Path("data")
    success_count = 0
    total_count = 0
    
    # Migrate character images
    characters_dir = base_dir / "characters"
    if characters_dir.exists():
        print(f"📁 Migrating character images from {characters_dir}")
        
        for gender_dir in characters_dir.iterdir():
            if not gender_dir.is_dir():
                continue
                
            for age_dir in gender_dir.iterdir():
                if not age_dir.is_dir():
                    continue
                    
                for image_file in age_dir.iterdir():
                    if image_file.is_file() and image_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        total_count += 1
                        
                        # Create R2 key preserving structure
                        r2_key = f"presets/characters/{gender_dir.name}/{age_dir.name}/{image_file.name}"
                        
                        print(f"📤 Uploading {image_file} -> {r2_key}")
                        
                        if upload_file(str(image_file), r2_key):
                            success_count += 1
                            print(f"✅ {image_file.name}")
                        else:
                            print(f"❌ Failed: {image_file.name}")
    
    # Migrate voice samples
    voices_dir = base_dir / "audio" / "voices"
    if voices_dir.exists():
        print(f"📁 Migrating voice samples from {voices_dir}")
        
        for gender_dir in voices_dir.iterdir():
            if not gender_dir.is_dir():
                continue
                
            for age_dir in gender_dir.iterdir():
                if not age_dir.is_dir():
                    continue
                    
                for audio_file in age_dir.iterdir():
                    if audio_file.is_file() and audio_file.suffix.lower() == '.mp3':
                        total_count += 1
                        
                        # Create R2 key preserving structure
                        r2_key = f"presets/voices/{gender_dir.name}/{age_dir.name}/{audio_file.name}"
                        
                        print(f"📤 Uploading {audio_file} -> {r2_key}")
                        
                        if upload_file(str(audio_file), r2_key):
                            success_count += 1
                            print(f"✅ {audio_file.name}")
                        else:
                            print(f"❌ Failed: {audio_file.name}")
    
    print(f"\n📊 Migration Summary:")
    print(f"   Total files: {total_count}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {total_count - success_count}")
    print(f"   Success rate: {(success_count/total_count*100):.1f}%" if total_count > 0 else "   No files found")
    
    return success_count == total_count

if __name__ == "__main__":
    success = migrate_presets()
    sys.exit(0 if success else 1)

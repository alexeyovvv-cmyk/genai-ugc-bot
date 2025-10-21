#!/usr/bin/env python3
"""Test R2 integration components."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all R2 modules can be imported."""
    print("🧪 Testing R2 module imports...")
    
    try:
        from tg_bot.services.r2_service import (
            upload_file, download_file, get_presigned_url, 
            delete_file, list_files, cleanup_temp_files, 
            get_storage_stats, test_connection
        )
        print("✅ R2 service imports successful")
    except Exception as e:
        print(f"❌ R2 service import failed: {e}")
        return False
    
    try:
        from tg_bot.utils.user_storage import (
            save_user_generation, get_user_generations,
            get_user_storage_stats, delete_user_generation
        )
        print("✅ User storage imports successful")
    except Exception as e:
        print(f"❌ User storage import failed: {e}")
        return False
    
    try:
        from tg_bot.utils.storage_stats import (
            get_total_storage_used, get_storage_by_user,
            get_storage_by_type, format_storage_summary
        )
        print("✅ Storage stats imports successful")
    except Exception as e:
        print(f"❌ Storage stats import failed: {e}")
        return False
    
    return True

def test_database_models():
    """Test that database models are updated."""
    print("\n🧪 Testing database models...")
    
    try:
        from tg_bot.models import Asset, GenerationHistory
        from sqlalchemy import inspect
        from tg_bot.db import engine
        
        inspector = inspect(engine)
        
        # Check Asset table has R2 fields
        asset_columns = [col['name'] for col in inspector.get_columns('assets')]
        r2_fields = ['r2_key', 'r2_url', 'r2_url_expires_at', 'file_size', 'version']
        
        missing_fields = [field for field in r2_fields if field not in asset_columns]
        if missing_fields:
            print(f"❌ Missing Asset fields: {missing_fields}")
            return False
        
        print("✅ Asset table has all R2 fields")
        
        # Check GenerationHistory table exists
        if 'generation_history' not in inspector.get_table_names():
            print("❌ GenerationHistory table not found")
            return False
        
        print("✅ GenerationHistory table exists")
        
        return True
        
    except Exception as e:
        print(f"❌ Database model test failed: {e}")
        return False

def test_file_utilities():
    """Test that file utilities work with R2."""
    print("\n🧪 Testing file utilities...")
    
    try:
        from tg_bot.utils.files import list_character_images, get_character_image_url
        from tg_bot.utils.voices import list_voice_samples, get_voice_sample_url
        
        # Test character images (should fallback to local files)
        images, has_next = list_character_images("female", "young", page=0, limit=5)
        print(f"✅ Character images: {len(images)} found, has_next: {has_next}")
        
        # Test voice samples (should fallback to local files)
        voices, has_next = list_voice_samples("female", "young", page=0, limit=5)
        print(f"✅ Voice samples: {len(voices)} found, has_next: {has_next}")
        
        return True
        
    except Exception as e:
        print(f"❌ File utilities test failed: {e}")
        return False

def test_generation_services():
    """Test that generation services are updated."""
    print("\n🧪 Testing generation services...")
    
    try:
        from tg_bot.services.elevenlabs_service import tts_to_file
        from tg_bot.services.falai_service import generate_talking_head_video
        
        # Check function signatures have user_id parameter
        import inspect
        
        tts_sig = inspect.signature(tts_to_file)
        if 'user_id' not in tts_sig.parameters:
            print("❌ tts_to_file missing user_id parameter")
            return False
        
        falai_sig = inspect.signature(generate_talking_head_video)
        if 'user_id' not in falai_sig.parameters:
            print("❌ generate_talking_head_video missing user_id parameter")
            return False
        
        print("✅ Generation services updated with user_id parameter")
        return True
        
    except Exception as e:
        print(f"❌ Generation services test failed: {e}")
        return False

def test_admin_commands():
    """Test that admin commands are added."""
    print("\n🧪 Testing admin commands...")
    
    try:
        # Check if admin module has the required functions
        import tg_bot.admin
        
        required_functions = ['admin_storage', 'admin_cleanup_temp', 'admin_r2_test']
        missing_functions = []
        
        for func_name in required_functions:
            if not hasattr(tg_bot.admin, func_name):
                missing_functions.append(func_name)
        
        if missing_functions:
            print(f"❌ Missing admin functions: {missing_functions}")
            return False
        
        print("✅ All admin command functions present")
        return True
        
    except Exception as e:
        print(f"❌ Admin commands test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 R2 Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_database_models,
        test_file_utilities,
        test_generation_services,
        test_admin_commands
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! R2 integration is ready.")
        print("\n📋 Next steps:")
        print("1. Set up R2 credentials (see r2_setup_instructions.md)")
        print("2. Run: python scripts/migrate_presets_to_r2.py")
        print("3. Deploy to Railway with R2 environment variables")
        return True
    else:
        print("❌ Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

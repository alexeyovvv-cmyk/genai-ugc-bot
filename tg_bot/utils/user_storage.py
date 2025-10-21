"""User storage utilities for R2."""
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from tg_bot.db import SessionLocal
from tg_bot.models import User, GenerationHistory, Asset
from tg_bot.services.r2_service import get_presigned_url, delete_file, get_file_info

def save_user_generation(
    user_id: int,
    generation_type: str,
    r2_video_key: Optional[str] = None,
    r2_audio_key: Optional[str] = None,
    r2_image_key: Optional[str] = None,
    character_gender: Optional[str] = None,
    character_age: Optional[str] = None,
    text_prompt: Optional[str] = None,
    credits_spent: int = 1
) -> Optional[int]:
    """
    Save user generation to history.
    
    Args:
        user_id: User ID
        generation_type: Type of generation ('video', 'audio', 'avatar_edit')
        r2_video_key: R2 key for video file
        r2_audio_key: R2 key for audio file
        r2_image_key: R2 key for image file
        character_gender: Character gender
        character_age: Character age
        text_prompt: Text prompt used
        credits_spent: Credits spent on generation
    
    Returns:
        Optional[int]: Generation ID or None if failed
    """
    try:
        with SessionLocal() as db:
            generation = GenerationHistory(
                user_id=user_id,
                generation_type=generation_type,
                r2_video_key=r2_video_key,
                r2_audio_key=r2_audio_key,
                r2_image_key=r2_image_key,
                character_gender=character_gender,
                character_age=character_age,
                text_prompt=text_prompt,
                credits_spent=credits_spent
            )
            
            db.add(generation)
            db.commit()
            db.refresh(generation)
            
            print(f"[USER_STORAGE] ✅ Saved generation {generation.id} for user {user_id}")
            return generation.id
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to save generation: {e}")
        return None

def get_user_generations(user_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get user's generation history with presigned URLs.
    
    Args:
        user_id: User ID
        limit: Number of generations to return
        offset: Offset for pagination
    
    Returns:
        List[Dict]: List of generation records with presigned URLs
    """
    try:
        with SessionLocal() as db:
            # Get user's generations
            generations = db.execute(
                select(GenerationHistory)
                .where(GenerationHistory.user_id == user_id)
                .order_by(desc(GenerationHistory.created_at))
                .limit(limit)
                .offset(offset)
            ).scalars().all()
            
            result = []
            for gen in generations:
                # Generate presigned URLs for files
                video_url = None
                audio_url = None
                image_url = None
                
                if gen.r2_video_key:
                    video_url = get_presigned_url(gen.r2_video_key, expiry_hours=24)
                
                if gen.r2_audio_key:
                    audio_url = get_presigned_url(gen.r2_audio_key, expiry_hours=24)
                
                if gen.r2_image_key:
                    image_url = get_presigned_url(gen.r2_image_key, expiry_hours=24)
                
                result.append({
                    'id': gen.id,
                    'generation_type': gen.generation_type,
                    'video_url': video_url,
                    'audio_url': audio_url,
                    'image_url': image_url,
                    'character_gender': gen.character_gender,
                    'character_age': gen.character_age,
                    'text_prompt': gen.text_prompt,
                    'credits_spent': gen.credits_spent,
                    'created_at': gen.created_at,
                    'has_video': bool(gen.r2_video_key),
                    'has_audio': bool(gen.r2_audio_key),
                    'has_image': bool(gen.r2_image_key)
                })
            
            print(f"[USER_STORAGE] ✅ Retrieved {len(result)} generations for user {user_id}")
            return result
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to get user generations: {e}")
        return []

def get_user_storage_stats(user_id: int) -> Dict[str, Any]:
    """
    Get user's storage usage statistics.
    
    Args:
        user_id: User ID
    
    Returns:
        Dict: Storage statistics
    """
    try:
        with SessionLocal() as db:
            # Count generations
            total_generations = db.execute(
                select(GenerationHistory)
                .where(GenerationHistory.user_id == user_id)
            ).scalars().all()
            
            # Count by type
            video_count = len([g for g in total_generations if g.r2_video_key])
            audio_count = len([g for g in total_generations if g.r2_audio_key])
            image_count = len([g for g in total_generations if g.r2_image_key])
            
            # Get file sizes (this would require R2 API calls for each file)
            # For now, return counts and let the UI estimate sizes
            stats = {
                'total_generations': len(total_generations),
                'video_count': video_count,
                'audio_count': audio_count,
                'image_count': image_count,
                'total_credits_spent': sum(g.credits_spent for g in total_generations),
                'oldest_generation': min(g.created_at for g in total_generations) if total_generations else None,
                'newest_generation': max(g.created_at for g in total_generations) if total_generations else None
            }
            
            print(f"[USER_STORAGE] ✅ Retrieved storage stats for user {user_id}")
            return stats
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to get storage stats: {e}")
        return {}

def delete_user_generation(user_id: int, generation_id: int) -> bool:
    """
    Delete specific user generation from R2 and database.
    
    Args:
        user_id: User ID
        generation_id: Generation ID to delete
    
    Returns:
        bool: Success status
    """
    try:
        with SessionLocal() as db:
            # Get generation record
            generation = db.execute(
                select(GenerationHistory)
                .where(GenerationHistory.id == generation_id)
                .where(GenerationHistory.user_id == user_id)
            ).scalar_one_or_none()
            
            if not generation:
                print(f"[USER_STORAGE] ❌ Generation {generation_id} not found for user {user_id}")
                return False
            
            # Delete files from R2
            deleted_files = []
            if generation.r2_video_key:
                if delete_file(generation.r2_video_key):
                    deleted_files.append(f"video: {generation.r2_video_key}")
            
            if generation.r2_audio_key:
                if delete_file(generation.r2_audio_key):
                    deleted_files.append(f"audio: {generation.r2_audio_key}")
            
            if generation.r2_image_key:
                if delete_file(generation.r2_image_key):
                    deleted_files.append(f"image: {generation.r2_image_key}")
            
            # Delete from database
            db.delete(generation)
            db.commit()
            
            print(f"[USER_STORAGE] ✅ Deleted generation {generation_id} for user {user_id}")
            print(f"[USER_STORAGE] Deleted files: {', '.join(deleted_files)}")
            return True
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to delete generation: {e}")
        return False

def get_generation_by_id(user_id: int, generation_id: int) -> Optional[Dict[str, Any]]:
    """
    Get specific generation by ID with presigned URLs.
    
    Args:
        user_id: User ID
        generation_id: Generation ID
    
    Returns:
        Optional[Dict]: Generation record or None
    """
    try:
        with SessionLocal() as db:
            generation = db.execute(
                select(GenerationHistory)
                .where(GenerationHistory.id == generation_id)
                .where(GenerationHistory.user_id == user_id)
            ).scalar_one_or_none()
            
            if not generation:
                return None
            
            # Generate presigned URLs
            video_url = None
            audio_url = None
            image_url = None
            
            if generation.r2_video_key:
                video_url = get_presigned_url(generation.r2_video_key, expiry_hours=24)
            
            if generation.r2_audio_key:
                audio_url = get_presigned_url(generation.r2_audio_key, expiry_hours=24)
            
            if generation.r2_image_key:
                image_url = get_presigned_url(generation.r2_image_key, expiry_hours=24)
            
            return {
                'id': generation.id,
                'generation_type': generation.generation_type,
                'video_url': video_url,
                'audio_url': audio_url,
                'image_url': image_url,
                'character_gender': generation.character_gender,
                'character_age': generation.character_age,
                'text_prompt': generation.text_prompt,
                'credits_spent': generation.credits_spent,
                'created_at': generation.created_at,
                'has_video': bool(generation.r2_video_key),
                'has_audio': bool(generation.r2_audio_key),
                'has_image': bool(generation.r2_image_key)
            }
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to get generation: {e}")
        return None

def cleanup_old_generations(user_id: int, days_old: int = 30) -> int:
    """
    Clean up old generations for a user (optional feature).
    
    Args:
        user_id: User ID
        days_old: Delete generations older than this many days
    
    Returns:
        int: Number of generations deleted
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with SessionLocal() as db:
            # Get old generations
            old_generations = db.execute(
                select(GenerationHistory)
                .where(GenerationHistory.user_id == user_id)
                .where(GenerationHistory.created_at < cutoff_date)
            ).scalars().all()
            
            deleted_count = 0
            for generation in old_generations:
                if delete_user_generation(user_id, generation.id):
                    deleted_count += 1
            
            print(f"[USER_STORAGE] ✅ Cleaned up {deleted_count} old generations for user {user_id}")
            return deleted_count
            
    except Exception as e:
        print(f"[USER_STORAGE] ❌ Failed to cleanup old generations: {e}")
        return 0

"""Storage statistics utilities for R2."""
from typing import Dict, List, Any
from tg_bot.services.r2_service import get_storage_stats, list_files

def get_total_storage_used() -> Dict[str, Any]:
    """
    Get total storage usage across all R2 objects.
    
    Returns:
        Dict: Total storage statistics
    """
    try:
        stats = get_storage_stats()
        return stats
    except Exception as e:
        print(f"[STORAGE_STATS] ❌ Failed to get total storage: {e}")
        return {}

def get_storage_by_user() -> List[Dict[str, Any]]:
    """
    Get storage breakdown by user.
    
    Returns:
        List[Dict]: Storage stats per user
    """
    try:
        # Get all user files
        user_files = list_files("users/")
        
        # Group by user ID
        user_stats = {}
        for file_info in user_files:
            # Extract user ID from path like "users/12345/generated_videos/file.mp4"
            path_parts = file_info['key'].split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'users':
                try:
                    user_id = int(path_parts[1])
                    if user_id not in user_stats:
                        user_stats[user_id] = {
                            'user_id': user_id,
                            'file_count': 0,
                            'total_size_bytes': 0,
                            'total_size_mb': 0,
                            'video_count': 0,
                            'audio_count': 0,
                            'image_count': 0
                        }
                    
                    user_stats[user_id]['file_count'] += 1
                    user_stats[user_id]['total_size_bytes'] += file_info['size']
                    
                    # Count by file type
                    if 'generated_videos' in file_info['key']:
                        user_stats[user_id]['video_count'] += 1
                    elif 'generated_audio' in file_info['key']:
                        user_stats[user_id]['audio_count'] += 1
                    elif 'avatars' in file_info['key']:
                        user_stats[user_id]['image_count'] += 1
                        
                except ValueError:
                    continue
        
        # Convert bytes to MB and sort by size
        result = []
        for user_id, stats in user_stats.items():
            stats['total_size_mb'] = round(stats['total_size_bytes'] / 1024 / 1024, 2)
            result.append(stats)
        
        # Sort by total size (descending)
        result.sort(key=lambda x: x['total_size_bytes'], reverse=True)
        
        print(f"[STORAGE_STATS] ✅ Retrieved storage for {len(result)} users")
        return result
        
    except Exception as e:
        print(f"[STORAGE_STATS] ❌ Failed to get storage by user: {e}")
        return []

def get_storage_by_type() -> Dict[str, Any]:
    """
    Get storage breakdown by file type.
    
    Returns:
        Dict: Storage stats by type
    """
    try:
        # Get stats for different prefixes
        presets = list_files("presets/")
        users = list_files("users/")
        temp = list_files("temp/")
        
        def analyze_files(files, prefix_name):
            total_size = sum(f['size'] for f in files)
            file_types = {}
            
            for file_info in files:
                # Determine file type by extension
                key = file_info['key']
                if key.endswith('.mp4'):
                    file_type = 'video'
                elif key.endswith('.mp3'):
                    file_type = 'audio'
                elif key.endswith(('.png', '.jpg', '.jpeg')):
                    file_type = 'image'
                else:
                    file_type = 'other'
                
                if file_type not in file_types:
                    file_types[file_type] = {'count': 0, 'size_bytes': 0}
                
                file_types[file_type]['count'] += 1
                file_types[file_type]['size_bytes'] += file_info['size']
            
            # Convert to MB
            for file_type in file_types:
                file_types[file_type]['size_mb'] = round(
                    file_types[file_type]['size_bytes'] / 1024 / 1024, 2
                )
            
            return {
                'total_files': len(files),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'by_type': file_types
            }
        
        result = {
            'presets': analyze_files(presets, 'presets'),
            'users': analyze_files(users, 'users'),
            'temp': analyze_files(temp, 'temp')
        }
        
        # Calculate totals
        all_files = presets + users + temp
        result['total'] = analyze_files(all_files, 'total')
        
        print(f"[STORAGE_STATS] ✅ Retrieved storage by type")
        return result
        
    except Exception as e:
        print(f"[STORAGE_STATS] ❌ Failed to get storage by type: {e}")
        return {}

def get_top_users_by_storage(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top users by storage usage.
    
    Args:
        limit: Number of top users to return
    
    Returns:
        List[Dict]: Top users with storage stats
    """
    try:
        user_stats = get_storage_by_user()
        return user_stats[:limit]
    except Exception as e:
        print(f"[STORAGE_STATS] ❌ Failed to get top users: {e}")
        return []

def get_temp_file_stats() -> Dict[str, Any]:
    """
    Get temporary file statistics.
    
    Returns:
        Dict: Temp file statistics
    """
    try:
        temp_files = list_files("temp/")
        
        if not temp_files:
            return {
                'total_files': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None
            }
        
        total_size = sum(f['size'] for f in temp_files)
        oldest_file = min(temp_files, key=lambda x: x['last_modified'])
        newest_file = max(temp_files, key=lambda x: x['last_modified'])
        
        return {
            'total_files': len(temp_files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'oldest_file': oldest_file['last_modified'],
            'newest_file': newest_file['last_modified']
        }
        
    except Exception as e:
        print(f"[STORAGE_STATS] ❌ Failed to get temp file stats: {e}")
        return {}

def format_storage_summary() -> str:
    """
    Format a human-readable storage summary.
    
    Returns:
        str: Formatted storage summary
    """
    try:
        stats = get_total_storage_used()
        temp_stats = get_temp_file_stats()
        top_users = get_top_users_by_storage(5)
        
        summary = f"""📊 **R2 Storage Summary**

**Total Usage:**
• Files: {stats.get('total', {}).get('count', 0):,}
• Size: {stats.get('total', {}).get('size_mb', 0):.2f} MB

**By Category:**
• Presets: {stats.get('presets', {}).get('count', 0):,} files ({stats.get('presets', {}).get('size_mb', 0):.2f} MB)
• User Content: {stats.get('users', {}).get('count', 0):,} files ({stats.get('users', {}).get('size_mb', 0):.2f} MB)
• Temp Files: {temp_stats.get('total_files', 0):,} files ({temp_stats.get('total_size_mb', 0):.2f} MB)

**Top Users by Storage:**
"""
        
        for i, user in enumerate(top_users, 1):
            summary += f"• #{i} User {user['user_id']}: {user['total_size_mb']:.2f} MB ({user['file_count']} files)\n"
        
        if temp_stats.get('total_files', 0) > 0:
            summary += f"\n**Temp Files:**\n"
            summary += f"• Oldest: {temp_stats.get('oldest_file', 'N/A')}\n"
            summary += f"• Newest: {temp_stats.get('newest_file', 'N/A')}\n"
        
        return summary
        
    except Exception as e:
        return f"❌ Failed to generate storage summary: {e}"

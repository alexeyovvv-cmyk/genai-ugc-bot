"""Cloudflare R2 Object Storage service."""
import os
import boto3
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# R2 Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "datanauts-ugc-bot")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")

# Initialize R2 client
def get_r2_client():
    """Get configured R2 client."""
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        raise ValueError("R2 credentials not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
    
    endpoint = R2_ENDPOINT
    if not endpoint:
        endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )

def upload_file(local_path: str, r2_key: str, metadata: Optional[Dict[str, str]] = None) -> bool:
    """
    Upload file to R2.
    
    Args:
        local_path: Local file path
        r2_key: R2 object key
        metadata: Optional metadata dict
    
    Returns:
        bool: Success status
    """
    try:
        client = get_r2_client()
        
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = metadata
        
        client.upload_file(
            local_path,
            R2_BUCKET_NAME,
            r2_key,
            ExtraArgs=extra_args
        )
        
        print(f"[R2] ✅ Uploaded {local_path} -> {r2_key}")
        return True
        
    except (ClientError, NoCredentialsError, FileNotFoundError) as e:
        print(f"[R2] ❌ Upload failed {local_path} -> {r2_key}: {e}")
        return False

def download_file(r2_key: str, local_path: str) -> bool:
    """
    Download file from R2.
    
    Args:
        r2_key: R2 object key
        local_path: Local destination path
    
    Returns:
        bool: Success status
    """
    try:
        client = get_r2_client()
        
        # Ensure directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        
        client.download_file(
            R2_BUCKET_NAME,
            r2_key,
            local_path
        )
        
        print(f"[R2] ✅ Downloaded {r2_key} -> {local_path}")
        return True
        
    except (ClientError, NoCredentialsError) as e:
        print(f"[R2] ❌ Download failed {r2_key} -> {local_path}: {e}")
        return False

def get_presigned_url(r2_key: str, expiry_hours: int = 1) -> Optional[str]:
    """
    Generate presigned URL for private access.
    
    Args:
        r2_key: R2 object key
        expiry_hours: URL expiry in hours
    
    Returns:
        Optional[str]: Presigned URL or None
    """
    try:
        client = get_r2_client()
        
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': r2_key},
            ExpiresIn=expiry_hours * 3600
        )
        
        print(f"[R2] ✅ Generated presigned URL for {r2_key} (expires in {expiry_hours}h)")
        return url
        
    except (ClientError, NoCredentialsError) as e:
        print(f"[R2] ❌ Presigned URL generation failed for {r2_key}: {e}")
        return None

def delete_file(r2_key: str) -> bool:
    """
    Delete file from R2.
    
    Args:
        r2_key: R2 object key
    
    Returns:
        bool: Success status
    """
    try:
        client = get_r2_client()
        
        client.delete_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key
        )
        
        print(f"[R2] ✅ Deleted {r2_key}")
        return True
        
    except (ClientError, NoCredentialsError) as e:
        print(f"[R2] ❌ Delete failed for {r2_key}: {e}")
        return False

def list_files(prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
    """
    List files in R2 with optional prefix.
    
    Args:
        prefix: Key prefix to filter
        max_keys: Maximum number of keys to return
    
    Returns:
        List[Dict]: List of file objects with metadata
    """
    try:
        client = get_r2_client()
        
        response = client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=max_keys
        )
        
        files = []
        for obj in response.get('Contents', []):
            files.append({
                'key': obj['Key'],
                'size': obj['Size'],
                'last_modified': obj['LastModified'],
                'etag': obj['ETag']
            })
        
        print(f"[R2] ✅ Listed {len(files)} files with prefix '{prefix}'")
        return files
        
    except (ClientError, NoCredentialsError) as e:
        print(f"[R2] ❌ List files failed for prefix '{prefix}': {e}")
        return []

def get_file_info(r2_key: str) -> Optional[Dict[str, Any]]:
    """
    Get file metadata from R2.
    
    Args:
        r2_key: R2 object key
    
    Returns:
        Optional[Dict]: File metadata or None
    """
    try:
        client = get_r2_client()
        
        response = client.head_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key
        )
        
        return {
            'size': response['ContentLength'],
            'last_modified': response['LastModified'],
            'etag': response['ETag'],
            'content_type': response.get('ContentType', ''),
            'metadata': response.get('Metadata', {})
        }
        
    except (ClientError, NoCredentialsError) as e:
        print(f"[R2] ❌ Get file info failed for {r2_key}: {e}")
        return None

def cleanup_temp_files() -> Dict[str, int]:
    """
    Clean up temporary files older than 24 hours.
    
    Returns:
        Dict[str, int]: Cleanup statistics
    """
    try:
        client = get_r2_client()
        
        # List all temp files
        temp_files = list_files("temp/")
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        deleted_count = 0
        total_size = 0
        
        for file_info in temp_files:
            if file_info['last_modified'].replace(tzinfo=None) < cutoff_time:
                if delete_file(file_info['key']):
                    deleted_count += 1
                    total_size += file_info['size']
        
        stats = {
            'deleted_files': deleted_count,
            'deleted_size_bytes': total_size,
            'deleted_size_mb': round(total_size / 1024 / 1024, 2)
        }
        
        print(f"[R2] ✅ Cleanup completed: {deleted_count} files, {stats['deleted_size_mb']} MB")
        return stats
        
    except Exception as e:
        print(f"[R2] ❌ Cleanup failed: {e}")
        return {'deleted_files': 0, 'deleted_size_bytes': 0, 'deleted_size_mb': 0}

def get_storage_stats() -> Dict[str, Any]:
    """
    Get storage usage statistics.
    
    Returns:
        Dict: Storage statistics by type
    """
    try:
        # Get stats by prefix
        presets = list_files("presets/")
        users = list_files("users/")
        temp = list_files("temp/")
        
        def calculate_stats(files):
            total_size = sum(f['size'] for f in files)
            return {
                'count': len(files),
                'size_bytes': total_size,
                'size_mb': round(total_size / 1024 / 1024, 2)
            }
        
        stats = {
            'presets': calculate_stats(presets),
            'users': calculate_stats(users),
            'temp': calculate_stats(temp),
            'total': calculate_stats(presets + users + temp)
        }
        
        print(f"[R2] ✅ Storage stats: {stats['total']['count']} files, {stats['total']['size_mb']} MB total")
        return stats
        
    except Exception as e:
        print(f"[R2] ❌ Storage stats failed: {e}")
        return {}

def test_connection() -> bool:
    """
    Test R2 connection and permissions.
    
    Returns:
        bool: Connection success
    """
    try:
        client = get_r2_client()
        
        # Try to list bucket contents (minimal operation)
        client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            MaxKeys=1
        )
        
        print("[R2] ✅ Connection test successful")
        return True
        
    except Exception as e:
        print(f"[R2] ❌ Connection test failed: {e}")
        return False

def configure_temp_edits_lifecycle() -> bool:
    """
    Configure R2 lifecycle policy to auto-delete temp edits after 24 hours and overlay cache after 1 day.
    
    Returns:
        bool: Configuration success
    """
    try:
        s3 = get_r2_client()
        
        lifecycle_config = {
            'Rules': [
                {
                    'ID': 'DeleteTempEditsAfter24h',
                    'Filter': {'Prefix': 'users/temp_edits/'},
                    'Status': 'Enabled',
                    'Expiration': {'Days': 1}
                },
                {
                    'ID': 'DeleteOverlayCacheAfter1Day',
                    'Filter': {'Prefix': 'overlays/'},
                    'Status': 'Enabled',
                    'Expiration': {'Days': 1}
                }
            ]
        }
        
        s3.put_bucket_lifecycle_configuration(
            Bucket=R2_BUCKET_NAME,
            LifecycleConfiguration=lifecycle_config
        )
        
        print(f"[R2] ✅ Lifecycle policy configured for temp edits (24h TTL) and overlay cache (24h TTL)")
        return True
        
    except Exception as e:
        print(f"[R2] ❌ Failed to configure lifecycle policy: {e}")
        return False

# R2 Storage Setup Instructions

## 1. Create Cloudflare R2 Bucket

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **R2 Object Storage**
3. Click **Create bucket**
4. Name: `datanauts-ugc-bot`
5. Location: Choose closest to your users

## 2. Get R2 API Credentials

1. Go to **R2** → **Manage R2 API tokens**
2. Click **Create API token**
3. Name: `datanauts-ugc-bot-token`
4. Permissions: **Object Read & Write**
5. Bucket: `datanauts-ugc-bot`
6. Save the credentials:
   - **Account ID**
   - **Access Key ID** 
   - **Secret Access Key**

## 3. Set Environment Variables

Add these to your Railway environment variables or local .env file:

```bash
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=datanauts-ugc-bot
R2_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
```

## 4. Test R2 Connection

Once credentials are set, test the connection:

```bash
# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/Users/alex/vibe_coding:$PYTHONPATH

# Test R2 connection
python -c "from tg_bot.services.r2_service import test_connection; print('R2 Test:', test_connection())"
```

## 5. Run Migration Scripts

```bash
# 1. Database migration (already done)
python tg_bot/migrations/add_r2_fields.py

# 2. Upload preset files to R2
python scripts/migrate_presets_to_r2.py
```

## 6. Verify Setup

Check that files are uploaded to R2:
- Go to Cloudflare Dashboard → R2 → `datanauts-ugc-bot` bucket
- You should see folders: `presets/characters/` and `presets/voices/`

## 7. Deploy to Railway

1. Add all R2_* environment variables to Railway
2. Deploy the updated code
3. Monitor logs for R2 operations
4. Use admin commands to test:
   - `/r2_test` - test R2 connection
   - `/storage` - view storage statistics
   - `/cleanup_temp` - manual temp cleanup

## Benefits After Migration

✅ **Unlimited Storage** - No Railway filesystem limits  
✅ **Global CDN** - Fast delivery worldwide  
✅ **User History** - Complete generation tracking  
✅ **Auto Cleanup** - Temp files deleted after 24h  
✅ **Version Control** - Avatar versioning support  
✅ **Cost Effective** - R2 has no egress fees  
✅ **Scalable** - Supports millions of users

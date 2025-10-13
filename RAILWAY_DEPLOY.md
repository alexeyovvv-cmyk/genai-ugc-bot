# Railway Deploy Guide

## 🚀 Deploy Telegram Bot to Railway

This guide will help you deploy your Telegram bot to Railway for 24/7 operation with PostgreSQL database.

## 📋 Prerequisites

- GitHub repository with your bot code
- Railway account (free tier available)
- Telegram Bot Token
- API keys: OpenAI, ElevenLabs, Replicate

## 💰 Cost Breakdown

- **Railway Hobby Plan**: $5/month (500 hours = 24/7 coverage)
- **PostgreSQL Plugin**: $5/month
- **Total**: ~$10/month

## 🛠️ Step-by-Step Deployment

### 1. Prepare Your Repository

Ensure these files are in your repository root:
- `railway.toml` ✅
- `nixpacks.toml` ✅
- `tg_bot/` directory with all bot files ✅
- `tg_bot/requirements.txt` with `psycopg2-binary>=2.9.9` ✅

### 2. Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Sign up/login with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your repository
6. Railway will auto-detect Python and start building

### 3. Add PostgreSQL Database

1. In your Railway project dashboard
2. Click "New" → "Database" → "PostgreSQL"
3. Railway will automatically set `DATABASE_URL` environment variable
4. Wait for database to be ready (green status)

### 4. Configure Environment Variables

In Railway project → Variables tab, add:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
ELEVEN_API_KEY=your_elevenlabs_api_key
REPLICATE_API_TOKEN=your_replicate_api_token
BASE_DIR=/app
```

**Note**: `DATABASE_URL` is automatically set by Railway PostgreSQL plugin.

### 5. Deploy

1. Railway will automatically deploy when you push to main branch
2. Or manually trigger deployment in Railway dashboard
3. Check logs for successful startup

### 6. Verify Deployment

1. Check Railway logs for "Bot started successfully"
2. Test bot in Telegram:
   - Send `/start`
   - Try generating audio
   - Try generating video
3. Check database: User data should persist between restarts

## 🔧 Configuration Details

### Database Migration
- **Local**: Uses SQLite (`genai.db`)
- **Railway**: Uses PostgreSQL (auto-configured)
- **Migration**: Automatic via SQLAlchemy

### File Management
- **Audio/Video files**: Automatically deleted after sending to user
- **Storage**: Minimal disk usage (no file accumulation)
- **Backup**: Telegram stores sent files on their servers

### Monitoring
- **Logs**: Available in Railway dashboard
- **Restarts**: Automatic on crashes
- **Health**: Bot uses polling (no webhook needed)

## 🚨 Troubleshooting

### Common Issues

**Build Fails**
- Check `requirements.txt` syntax
- Ensure `psycopg2-binary>=2.9.9` is included
- Check Railway logs for specific errors

**Database Connection Issues**
- Verify `DATABASE_URL` is set (auto-set by Railway)
- Check PostgreSQL service is running
- Ensure database is not paused

**Bot Not Responding**
- Check `TELEGRAM_BOT_TOKEN` is correct
- Verify bot is not already running elsewhere
- Check Railway logs for connection errors

**API Errors**
- Verify all API keys are set correctly
- Check API quotas/credits
- Monitor Railway logs for API-specific errors

### Logs Location
- Railway Dashboard → Your Project → Deployments → Logs
- Real-time logs available during deployment
- Historical logs accessible for debugging

## 📊 Performance Tips

1. **File Cleanup**: Implemented automatically after sending
2. **Database**: PostgreSQL handles concurrent users better than SQLite
3. **Memory**: Bot uses ~100-200MB RAM
4. **CPU**: Minimal usage except during AI generation

## 🔄 Updates & Maintenance

### Updating Bot
1. Push changes to GitHub main branch
2. Railway auto-deploys
3. Check logs for successful deployment

### Database Backup
- Railway PostgreSQL includes automatic backups
- Consider manual exports for critical data

### Scaling
- Current setup handles 10-50 concurrent users
- For higher load, consider Railway Pro plan ($20/month)

## ✅ Success Checklist

- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Environment variables set
- [ ] Bot deploys successfully
- [ ] Database tables created automatically
- [ ] Bot responds in Telegram
- [ ] Audio generation works
- [ ] Video generation works
- [ ] Files are cleaned up after sending
- [ ] Bot runs 24/7 without issues

## 🆘 Support

- Railway Documentation: [docs.railway.app](https://docs.railway.app)
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Check logs first for error details

---

**Total Cost**: ~$10/month for 24/7 operation with PostgreSQL database and automatic file cleanup.

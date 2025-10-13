#!/bin/bash

# Deploy script for Google Cloud Run
set -e

PROJECT_ID="core-memento-474918-d4"
SERVICE_NAME="genai-ugc-bot"
REGION="us-central1"

echo "Building and deploying to Google Cloud Run..."

# Build and push Docker image
echo "Building Docker image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --set-env-vars BASE_DIR=/app \
  --set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --set-secrets ELEVEN_API_KEY=elevenlabs-api-key:latest \
  --set-env-vars GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID \
  --set-env-vars GOOGLE_CLOUD_LOCATION=$REGION \
  --set-env-vars GOOGLE_CLOUD_API_ENDPOINT=$REGION-aiplatform.googleapis.com

echo "Deployment complete!"
echo "Service URL: https://$SERVICE_NAME-$PROJECT_ID.uc.r.appspot.com"

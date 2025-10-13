FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY tg_bot/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Fix SSL issues with urllib3
RUN pip install --no-cache-dir "urllib3<2.0"

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/audio/voices data/start_frames data/video

# Set environment variables
ENV PYTHONPATH=/app
ENV BASE_DIR=/app

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run the bot
CMD ["python", "-m", "tg_bot.main"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by Playwright's Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 wget ca-certificates fonts-liberation \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser binary
RUN python -m playwright install chromium

# Expose port for web server
EXPOSE 8000

# Copy database file (persisted data) if it exists
COPY reddit_posts.db* /app/

# Run web server with pipeline orchestration
CMD ["python3", "news-server2.py"]

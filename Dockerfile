FROM python:3.11-slim

WORKDIR /app

# Copy application code from build context (server's local repo)
# This ensures we use the deployed version, not a GitHub clone
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for web server
EXPOSE 8000

# Copy database file (persisted data) if it exists
COPY reddit_posts.db* /app/

# Run web server with pipeline orchestration
CMD ["python3", "news-server2.py"]

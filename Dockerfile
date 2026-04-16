FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port for web server
EXPOSE 8000

# Run web server with pipeline orchestration
CMD ["python", "news-server2.py"]

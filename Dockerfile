FROM python:3.11-slim

WORKDIR /app

# Clone the repository directly from git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/* && \
    git clone https://github.com/Dirrelito071/Reddit_LLM.git . && \
    rm -rf .git

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for web server
EXPOSE 8000

# Run web server with pipeline orchestration
CMD ["python3", "news-server2.py"]

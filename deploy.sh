#!/bin/bash

################################################################################
# Reddit LLM Deployment Script
# 
# Safely deploys Reddit LLM to server without affecting other Docker containers
# - Clones/updates repository
# - Rebuilds only the reddit-llm image
# - Restarts only the reddit-news-server container
# - Preserves all data volumes
#
# Usage: ./deploy.sh
################################################################################

set -e  # Exit on error

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/Dirrelito071/Reddit_LLM.git"
SERVER_HOST="Server@server"
SERVER_PATH="/Users/server/mediastack"
REDDIT_LLM_DIR="$SERVER_PATH/Reddit_LLM"
DOCKER_SERVICE="reddit-news-server"
DOCKER_IMAGE="reddit-llm:latest"
DEPLOYMENT_LOG="/tmp/reddit-llm-deploy.log"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

# Start logging
echo "================================" > "$DEPLOYMENT_LOG"
echo "Reddit LLM Deployment - $(date)" >> "$DEPLOYMENT_LOG"
echo "================================" >> "$DEPLOYMENT_LOG"

log_info "Starting Reddit LLM deployment..."
log_info "Server: $SERVER_HOST"
log_info "Path: $REDDIT_LLM_DIR"

# Step 1: Clone or update repository
log_info "Step 1: Cloning/updating repository..."

ssh "$SERVER_HOST" bash << 'EOF'
    REPO_URL="https://github.com/Dirrelito071/Reddit_LLM.git"
    SERVER_PATH="/Users/server/mediastack"
    REDDIT_LLM_DIR="$SERVER_PATH/Reddit_LLM"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    
    if [ -d "$REDDIT_LLM_DIR/.git" ]; then
        echo "[SERVER] Repository exists, pulling latest changes..."
        cd "$REDDIT_LLM_DIR"
        git fetch origin main
        git reset --hard origin/main
    else
        echo "[SERVER] Cloning repository..."
        rm -rf "$REDDIT_LLM_DIR"
        git clone "$REPO_URL" "$REDDIT_LLM_DIR"
    fi
    
    echo "[SERVER] Repository ready at $REDDIT_LLM_DIR"
    ls -la "$REDDIT_LLM_DIR" | head -10
EOF

log_success "Repository cloned/updated"

# Step 2: Verify Dockerfile exists
log_info "Step 2: Verifying Dockerfile..."

ssh "$SERVER_HOST" bash << EOF
    if [ -f "$REDDIT_LLM_DIR/Dockerfile" ]; then
        echo "[SERVER] Dockerfile found ✓"
    else
        echo "[SERVER] ERROR: Dockerfile not found!"
        exit 1
    fi
EOF

log_success "Dockerfile verified"

# Step 3: Use docker-compose from the mediastack directory to rebuild ONLY reddit-llm
log_info "Step 3: Building Docker image (this may take a few minutes)..."

ssh "$SERVER_HOST" bash << 'EOF'
    SERVER_PATH="/Users/server/mediastack"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    REDDIT_LLM_DIR="$SERVER_PATH/Reddit_LLM"
    
    cd "$REDDIT_LLM_DIR"
    
    # Build only the reddit-news-server service with --no-cache to get latest code
    echo "[SERVER] Building reddit-llm image..."
    $DOCKER_CMD compose -f "$SERVER_PATH/docker-compose.yaml" build --no-cache reddit-news-server 2>&1 | tail -20
    
    if [ $? -eq 0 ]; then
        echo "[SERVER] Build successful ✓"
    else
        echo "[SERVER] Build failed!"
        exit 1
    fi
EOF

log_success "Docker image built"

# Step 4: Restart ONLY the reddit-news-server container
log_info "Step 4: Restarting reddit-news-server container..."

ssh "$SERVER_HOST" bash << 'EOF'
    SERVER_PATH="/Users/server/mediastack"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    
    cd "$SERVER_PATH"
    
    # Stop only the reddit-news-server container
    echo "[SERVER] Stopping reddit-news-server..."
    $DOCKER_CMD compose stop reddit-news-server 2>&1 || true
    
    # Remove only the reddit-news-server container (image stays)
    echo "[SERVER] Removing old container..."
    $DOCKER_CMD compose rm -f reddit-news-server 2>&1 || true
    
    # Start the reddit-news-server with the new image
    echo "[SERVER] Starting reddit-news-server with new image..."
    $DOCKER_CMD compose up -d reddit-news-server
    
    echo "[SERVER] Waiting for container to start..."
    sleep 5
    
    # Verify container is running
    $DOCKER_CMD compose ps reddit-news-server
EOF

log_success "Container restarted"

# Step 5: Verify deployment
log_info "Step 5: Verifying deployment..."

ssh "$SERVER_HOST" bash << 'EOF'
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    
    # Check if container is running
    CONTAINER_STATUS=$($DOCKER_CMD ps --filter "name=reddit-news-server" --format "{{.Status}}")
    
    if [ -z "$CONTAINER_STATUS" ]; then
        echo "[SERVER] ERROR: Container is not running!"
        exit 1
    fi
    
    echo "[SERVER] Container status: $CONTAINER_STATUS"
    
    # Check if the new code is loaded (check for Settings panel features)
    echo "[SERVER] Checking for latest code features..."
    
    # Check if user_settings table creation code exists
    if $DOCKER_CMD exec reddit-news-server test -f /app/db.py; then
        if $DOCKER_CMD exec reddit-news-server grep -q "user_settings" /app/db.py; then
            echo "[SERVER] ✓ Settings panel code found in db.py"
        else
            echo "[SERVER] WARNING: db.py exists but user_settings not found"
            echo "[SERVER] Checking file contents..."
            $DOCKER_CMD exec reddit-news-server head -60 /app/db.py | tail -10
            exit 1
        fi
    else
        echo "[SERVER] ERROR: db.py not found in container"
        exit 1
    fi
    
    # Check if news-digest.html has Settings button
    if $DOCKER_CMD exec reddit-news-server test -f /app/news-digest.html; then
        if $DOCKER_CMD exec reddit-news-server grep -q "settings-btn" /app/news-digest.html; then
            echo "[SERVER] ✓ Settings UI found in news-digest.html"
        else
            echo "[SERVER] WARNING: news-digest.html exists but settings-btn not found"
            echo "[SERVER] This may be expected if using news-server2.py"
        fi
    else
        echo "[SERVER] Note: news-digest.html not found (may be served from news-server2.py)"
    fi
    
    echo "[SERVER] Deployment verification complete!"
EOF

log_success "Deployment verified"

# Step 6: Show final status
log_info "Step 6: Final status check..."

ssh "$SERVER_HOST" bash << 'EOF'
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    SERVER_PATH="/Users/server/mediastack"
    
    echo "[SERVER] === Reddit LLM Container Status ==="
    $DOCKER_CMD compose -f "$SERVER_PATH/docker-compose.yaml" ps reddit-news-server
    
    echo "[SERVER]"
    echo "[SERVER] === Recent Container Logs ==="
    $DOCKER_CMD logs --tail 10 reddit-news-server 2>&1 | tail -15
EOF

# Final summary
echo ""
log_success "================================"
log_success "Deployment Complete! ✓"
log_success "================================"
log_success "Service: reddit-news-server"
log_success "Image: reddit-llm:latest"
log_success "Access: http://100.77.129.54:8000"
log_success ""
log_success "What was updated:"
log_success "  - Settings panel with subreddit management"
log_success "  - LLM question editor from UI"
log_success "  - Database-backed settings (persistent)"
log_success "  - API endpoints for settings changes"
log_success ""
log_success "Other containers: UNTOUCHED ✓"
log_success "================================"
log_success "Full log saved to: $DEPLOYMENT_LOG"

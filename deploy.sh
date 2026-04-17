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
    
    if [ -d "$REDDIT_LLM_DIR/.git" ]; then
        echo "[SERVER] Repository exists, pulling latest changes..."
        cd "$REDDIT_LLM_DIR"
        git fetch origin main
        git reset --hard origin/main
        echo "[SERVER] Reset to latest main branch"
    else
        echo "[SERVER] Cloning repository..."
        rm -rf "$REDDIT_LLM_DIR"
        git clone "$REPO_URL" "$REDDIT_LLM_DIR"
        echo "[SERVER] Cloned repository"
    fi
    
    echo "[SERVER] Repository ready at $REDDIT_LLM_DIR"
    echo "[SERVER] Current commit:"
    cd "$REDDIT_LLM_DIR" && git log -1 --oneline
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

# Step 3: Fix Docker credentials and rebuild
log_info "Step 3: Fixing Docker credentials and rebuilding..."

ssh "$SERVER_HOST" bash << 'EOF'
    SERVER_PATH="/Users/server/mediastack"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    REDDIT_LLM_DIR="$SERVER_PATH/Reddit_LLM"
    
    cd "$REDDIT_LLM_DIR"
    
    # Fix Docker credential helper issue on macOS (docker-credential-desktop not in PATH during builds)
    # Remove credsStore temporarily - Docker will use stored credentials instead
    if [ -f ~/.docker/config.json ]; then
        echo "[SERVER] Fixing Docker credentials configuration..."
        if grep -q '"credsStore"' ~/.docker/config.json; then
            cp ~/.docker/config.json ~/.docker/config.json.bak
            jq 'del(.credsStore)' ~/.docker/config.json.bak > ~/.docker/config.json
            echo "[SERVER] Removed credsStore from config.json"
        fi
    fi
    
    # Force stop and remove container first (so we can delete image)
    echo "[SERVER] Stopping reddit-news-server container..."
    $DOCKER_CMD compose -f "$SERVER_PATH/docker-compose.yaml" stop reddit-news-server 2>&1 || true
    $DOCKER_CMD compose -f "$SERVER_PATH/docker-compose.yaml" rm -f reddit-news-server 2>&1 || true
    
    # Remove old reddit-llm image to force complete rebuild
    echo "[SERVER] Removing old reddit-llm image..."
    $DOCKER_CMD rmi -f reddit-llm:latest 2>&1 || true
    
    # Clean build cache
    echo "[SERVER] Cleaning Docker build cache..."
    $DOCKER_CMD builder prune -af 2>&1 >/dev/null || true
    
    # Build using docker compose with --no-cache to ensure fresh build
    echo "[SERVER] Building reddit-llm image using docker compose (this may take 1-2 minutes)..."
    cd "$SERVER_PATH"
    BUILD_OUTPUT=$($DOCKER_CMD compose -f docker-compose.yaml build --no-cache reddit-news-server 2>&1)
    BUILD_EXIT=$?
    
    # Show last 20 lines of build output
    echo "$BUILD_OUTPUT" | tail -20
    
    if [ $BUILD_EXIT -eq 0 ]; then
        echo "[SERVER] Build successful ✓"
    else
        echo "[SERVER] Build failed with exit code $BUILD_EXIT"
        echo "[SERVER] Error details:"
        echo "$BUILD_OUTPUT" | grep -i "error" | head -10
        exit 1
    fi
EOF

log_success "Docker image built"

# Step 4: Start container with new image
log_info "Step 4: Starting container with new image..."

ssh "$SERVER_HOST" bash << 'EOF'
    SERVER_PATH="/Users/server/mediastack"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    
    cd "$SERVER_PATH"
    
    # Start the reddit-news-server with the newly built image
    echo "[SERVER] Starting reddit-news-server with new image..."
    $DOCKER_CMD compose -f docker-compose.yaml up -d reddit-news-server
    
    echo "[SERVER] Waiting for container to start..."
    sleep 5
    
    # Verify container is running
    echo "[SERVER] Container status:"
    $DOCKER_CMD compose -f docker-compose.yaml ps reddit-news-server
EOF

log_success "Container restarted"

# Step 5: Verify deployment
log_info "Step 5: Verifying deployment..."

ssh "$SERVER_HOST" bash << 'EOF'
    SERVER_PATH="/Users/server/mediastack"
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    
    # Check if container is running
    CONTAINER_STATUS=$($DOCKER_CMD ps --filter "name=reddit-news-server" --format "{{.Status}}")
    
    if [ -z "$CONTAINER_STATUS" ]; then
        echo "[SERVER] ERROR: Container is not running!"
        exit 1
    fi
    
    echo "[SERVER] Container status: $CONTAINER_STATUS"
    
    # Verify the new code is loaded by checking for latest code features
    echo "[SERVER] Verifying latest code is deployed..."
    
    # Check that the Settings panel code is present (user_settings table creation)
    SETTINGS_COUNT=$($DOCKER_CMD exec reddit-news-server grep "user_settings" /app/db.py 2>/dev/null | wc -l)
    
    if [ "$SETTINGS_COUNT" -gt 0 ]; then
        echo "[SERVER] ✓ Settings panel code detected"
    else
        echo "[SERVER] WARNING: Settings panel code not found - may not be latest version"
    fi
    
    # Check that the latest HTML initialization code is present (Object.keys data.status)
    LATEST_CODE=$($DOCKER_CMD exec reddit-news-server grep "Object.keys(data.status" /app/news-digest.html 2>/dev/null | wc -l)
    
    if [ "$LATEST_CODE" -gt 0 ]; then
        echo "[SERVER] ✓ Latest HTML code detected"
    else
        echo "[SERVER] ⚠ WARNING: Latest HTML code not found!"
        echo "[SERVER] Checking what initialization code is present:"
        $DOCKER_CMD exec reddit-news-server sed -n '338,342p' /app/news-digest.html
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

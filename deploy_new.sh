#!/bin/bash

################################################################################
# Reddit LLM Standard Docker Compose Deployment Script
#
# Deploys Reddit LLM using the local docker-compose.yaml (repo-based workflow)
# - Pulls latest code from main branch
# - Builds/rebuilds the reddit-llm image
# - Restarts the reddit-news-server container
# - Shows status and recent logs
#
# Usage: ./deploy_new.sh
################################################################################



set -e

SERVER_USER="Server"
SERVER_HOST="server"
SERVER_PATH="/Users/server/mediastack"
COMPOSE_SERVICE="reddit-news-server"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}[INFO] Deploying to $SERVER_USER@$SERVER_HOST...${NC}"

ssh ${SERVER_USER}@${SERVER_HOST} bash << EOF
	set -e
	SERVER_PATH="$SERVER_PATH"
	DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
	COMPOSE_FILE="$SERVER_PATH/docker-compose.yaml"
	cd "\$SERVER_PATH"
	echo -e "${BLUE}[INFO] Pulling latest reddit-llm image from GHCR...${NC}"
	\$DOCKER_CMD compose -f \$COMPOSE_FILE pull $COMPOSE_SERVICE
	echo -e "${BLUE}[INFO] Restarting $COMPOSE_SERVICE...${NC}"
	\$DOCKER_CMD compose -f \$COMPOSE_FILE up -d $COMPOSE_SERVICE
	echo -e "${GREEN}[SUCCESS] Deployment complete!${NC}"
	\$DOCKER_CMD compose -f \$COMPOSE_FILE ps $COMPOSE_SERVICE
	\$DOCKER_CMD compose -f \$COMPOSE_FILE logs --tail=10 $COMPOSE_SERVICE
EOF

# Deployment Script

## Overview

`deploy.sh` is a safe, automated deployment script that deploys Reddit LLM to the server without interfering with other Docker containers.

## Features

✅ **Safe Isolation**
- Only rebuilds the `reddit-llm` image
- Only restarts the `reddit-news-server` container
- Leaves all other Docker containers untouched
- Preserves data volumes

✅ **Automated Steps**
1. Clones or updates repository from GitHub
2. Verifies Dockerfile exists
3. Builds Docker image (no-cache for fresh code)
4. Restarts container with new image
5. Verifies deployment success
6. Checks for new features (Settings panel)

✅ **Error Handling**
- Exits on any error
- Detailed logging to `/tmp/reddit-llm-deploy.log`
- Verification checks at each step

✅ **Non-Destructive**
- If container exists, gracefully stops and restarts
- Data volumes are never deleted
- Database persists across deployments

## Usage

### From Local Machine (with SSH configured)

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM
./deploy.sh
```

### What It Does

1. **Clones/Updates Repository**
   - If `/Users/server/mediastack/Reddit_LLM/.git` exists: pulls latest changes
   - If not: clones fresh repository
   - Uses `git reset --hard origin/main` to ensure clean state

2. **Builds Docker Image**
   - Runs `docker-compose build --no-cache reddit-news-server`
   - Gets latest code changes (bypasses cache)
   - May take 2-3 minutes

3. **Restarts Container**
   - Stops old container gracefully
   - Removes old container
   - Starts new container from updated image
   - Data volume `/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm` preserved

4. **Verifies Deployment**
   - Checks container is running
   - Verifies Settings panel code loaded (`user_settings` in db.py)
   - Verifies Settings UI loaded (`settings-btn` in news-digest.html)
   - Shows container status and recent logs

## Output

The script provides color-coded output and saves full logs:

```
[INFO] Starting Reddit LLM deployment...
[SUCCESS] Repository cloned/updated
[SUCCESS] Dockerfile verified
[SUCCESS] Docker image built
[SUCCESS] Container restarted
[SUCCESS] Deployment verified
[SUCCESS] ================================
[SUCCESS] Deployment Complete! ✓
[SUCCESS] ================================
```

Full log saved to: `/tmp/reddit-llm-deploy.log`

## Server Architecture

```
Local Machine (kvirre)
    ↓ SSH
Server (Server@server)
    ├── /Users/server/mediastack/
    │   ├── docker-compose.yaml (contains all services)
    │   ├── Reddit_LLM/  (cloned repo)
    │   │   ├── Dockerfile
    │   │   ├── news-server2.py
    │   │   ├── db.py
    │   │   └── ... (all source files)
    │   └── ... (other services)
    │
    └── Docker Containers
        ├── reddit-news-server (rebuilt, restarted)
        ├── gluetun (untouched)
        ├── transmission (untouched)
        ├── overseerr (untouched)
        └── ... (other services untouched)
```

## Safety Features

### Isolation
- Uses specific service name: `reddit-news-server`
- Only affects this one container
- `docker-compose` with specific service ensures isolation

### Data Preservation
- Volumes defined in docker-compose.yaml are preserved
- `/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm` never deleted
- Database `reddit_posts.db` persists

### Verification
- Checks container status before considering deployment complete
- Verifies latest code features are loaded
- Shows deployment status with color-coded output

## Rollback (if needed)

If deployment fails:

1. Container stays running with old image
2. Check logs: `cat /tmp/reddit-llm-deploy.log`
3. Run deployment again: `./deploy.sh`

The script is idempotent - safe to run multiple times.

## Troubleshooting

### Check Server Status
```bash
ssh Server@server "cd /Users/server/mediastack && \
  /Applications/Docker.app/Contents/Resources/bin/docker-compose ps"
```

### View Container Logs
```bash
ssh Server@server "/Applications/Docker.app/Contents/Resources/bin/docker logs reddit-news-server -f"
```

### Manually Rebuild (if needed)
```bash
ssh Server@server "cd /Users/server/mediastack && \
  /Applications/Docker.app/Contents/Resources/bin/docker-compose build --no-cache reddit-news-server"
```

### Check Deployment Log
```bash
cat /tmp/reddit-llm-deploy.log
```

## What Changes Are Deployed

Latest commit: Settings Panel Implementation
- User_settings table for persistent configuration
- Settings modal UI (⚙️ button)
- Add/remove subreddits dynamically
- Edit LLM question from UI
- API endpoints for settings changes
- Full form validation
- Success/error feedback messages

## Accessing the Deployment

Once deployed, access at:
- **Local**: http://localhost:8000
- **Tailscale**: http://100.77.129.54:8000
- **Server**: http://server.local:8000

## Script Maintenance

To update the deployment process:
1. Edit `deploy.sh` locally
2. Test changes
3. Commit to GitHub: `git add deploy.sh && git commit -m "..."`
4. Next `./deploy.sh` run will have updated script on server

## Cron Job (Optional - for scheduled deployments)

To schedule automatic deployments at midnight:

```bash
# Add to crontab
0 0 * * * /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM/deploy.sh >> /tmp/reddit-llm-cron.log 2>&1
```

Then just commit code to GitHub and deployment happens automatically.

---

**Created**: 17 April 2026
**Purpose**: Safe, automated deployment of Reddit LLM
**Safety**: Isolates to single container, preserves data, leaves other services untouched

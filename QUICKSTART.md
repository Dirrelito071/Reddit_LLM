# Quick Start: Deploy to Server

## One-Command Deployment

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM
./deploy.sh
```

That's it! The script will:
1. ✅ Clone/update repo on server
2. ✅ Build new Docker image
3. ✅ Restart container with latest code
4. ✅ Verify deployment
5. ✅ Leave other services untouched

## What Gets Deployed

Your latest commits → GitHub → Server → Running container

### Current: Settings Panel (April 17)
- Subreddit management from UI
- LLM question editor
- Settings modal (⚙️ button)
- Database persistence
- Full validation & error handling

## Monitoring Deployment

Watch the output:
```
[INFO] Starting Reddit LLM deployment...
[SUCCESS] Repository cloned/updated
[SUCCESS] Dockerfile verified
[SUCCESS] Docker image built
[SUCCESS] Container restarted
[SUCCESS] Deployment verified
[SUCCESS] Deployment Complete! ✓
```

Full log: `cat /tmp/reddit-llm-deploy.log`

## Access After Deployment

- **Tailscale**: http://100.77.129.54:8000
- **Local Network**: http://server.local:8000

## Safety Guarantees

✅ **Isolated Deployment**
- Only rebuilds `reddit-llm` image
- Only restarts `reddit-news-server` container
- All other Docker services untouched

✅ **Data Preservation**
- Database persists: `/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm`
- Reddit posts data safe
- Settings preserved

✅ **Rollback Capability**
- Container stays running with old image if build fails
- Re-run script to retry
- No data loss

## Workflow

```
1. Make code changes locally
2. Test locally: python3 news-server2.py
3. Commit: git add . && git commit -m "..."
4. Push: git push origin main
5. Deploy: ./deploy.sh
```

Script automatically pulls from GitHub, rebuilds, and restarts!

## Troubleshooting

**Container not starting?**
```bash
ssh Server@server "/Applications/Docker.app/Contents/Resources/bin/docker logs reddit-news-server"
```

**Want to rebuild?**
```bash
./deploy.sh
```

**Want to see all containers?**
```bash
ssh Server@server "/Applications/Docker.app/Contents/Resources/bin/docker-compose ps"
```

## Advanced: Manual Steps (if needed)

```bash
# SSH to server
ssh Server@server

# Navigate to mediastack
cd /Users/server/mediastack

# Alias docker-compose for convenience
alias dc="/Applications/Docker.app/Contents/Resources/bin/docker-compose"

# Check status
dc ps

# View logs
dc logs -f reddit-news-server

# Restart specific service
dc restart reddit-news-server

# Rebuild specific service
dc build --no-cache reddit-news-server

# Update and restart
dc up -d reddit-news-server
```

---

**Next Step**: `./deploy.sh` to deploy Settings Panel to server!

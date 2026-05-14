# Deployment
<!-- Last updated: 10 May 2026 -->

## Always deploy with

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM
sh deploy.sh
```

Never run raw SSH docker commands or bypass the script.

---

## What deploy.sh does

1. **Step 0** — Verifies local working tree is clean, then pushes to GitHub (`origin/main`).
2. **Step 1** — SSHs to `Server@server`, pulls the repo at `/Users/server/mediastack/Reddit_LLM/`, resets to `origin/main`.
3. **Step 2** — Confirms `Dockerfile` is present.
4. **Step 3** — Stops + removes the `reddit-news-server` container, untags and deletes the old `reddit-llm:latest` image, clears build cache, rebuilds with `docker compose build`.
5. **Step 4** — Starts the new container with `docker compose up -d`.
6. **Step 5** — Waits, checks container status, verifies known code strings are present.
7. **Step 6** — Prints final status and last few log lines.

Full log saved to `/tmp/reddit-llm-deploy.log` on the local machine.

---

## Server details

| Item | Value |
|------|-------|
| SSH host | `Server@server` |
| Repo path on server | `/Users/server/mediastack/Reddit_LLM/` |
| Container name | `reddit-news-server` |
| Image name | `reddit-llm:latest` |
| Docker binary | `/usr/local/bin/docker` |
| Exposed port | `8000` (mapped from container `8000`) |
| Access (Tailscale) | http://100.77.129.54:8000 |

### Volume mounts (data persists across rebuilds)
```
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db  →  /app/reddit_posts.db
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/data             →  /app/data
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/logs             →  /app/logs
```

> The real compose file controlling these mounts is `/Users/server/mediastack/docker-compose.yaml` on the server. The `docker-compose.yml` in the repo is not used by deploy.sh.

---

## Reading logs

```bash
# Tail 300 lines (convenience script)
sh logs.sh

# More lines
ssh Server@server "/usr/local/bin/docker logs reddit-news-server 2>&1 | tail -500"

# Follow live
ssh Server@server "/usr/local/bin/docker logs -f reddit-news-server 2>&1"
```

---

## Accessing the DB from local machine

The DB is on the RED external drive, shared via SMB. It is mounted locally at:
```
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/
```

```bash
# Open interactive SQLite shell (direct — no copy needed)
sqlite3 "/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db"

# Quick counts
sqlite3 "/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db" \
    "SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit;"
```

> Do NOT use scp to copy the DB — query the SMB mount directly.

---

## Troubleshooting

### deploy.sh says "Uncommitted changes detected" on a clean tree
Cause: file mode bits changed (macOS ↔ Linux). Fix:
```bash
git config core.fileMode false
sh deploy.sh
```

### Container not starting
```bash
ssh Server@server "/usr/local/bin/docker logs reddit-news-server 2>&1 | tail -50"
```

### Rebuild check — verify what commit is running
```bash
ssh Server@server "cd /Users/server/mediastack/Reddit_LLM && git log --oneline -3"
```

### Re-run deploy (idempotent — safe to run multiple times)
```bash
sh deploy.sh
```

---

## Deployment isolation guarantee

- Only the `reddit-news-server` container is touched.
- All other containers (lidarr, gluetun, transmission, etc.) are untouched.
- Data volumes are never deleted.

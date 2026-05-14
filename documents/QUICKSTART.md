# Quick Start
<!-- Last updated: 10 May 2026 -->

## Access the running app

**Tailscale (from anywhere):** http://100.77.129.54:8000

---

## Make a change and deploy

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM

# 1. Edit files
# 2. Commit
git add <files> && git commit -m "describe change"

# 3. Deploy (single command — does everything)
sh deploy.sh
```

---

## Read server logs

```bash
sh logs.sh                  # last 300 lines from container
```

---

## Query the DB

The DB is on the RED external drive, accessible via SMB mount at:
```
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db
```

```bash
sqlite3 "/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db" \
    "SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit;"
```

---

## Run locally (development)

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM
python3 news-server2.py
# open http://localhost:8000
```

Requires Ollama running locally with `gemma3:12b` pulled.

---

## Key files to know

| File | Purpose |
|------|---------|
| `news-digest.html` | Entire frontend (CSS + JS + HTML inline) |
| `news-server2.py` | HTTP server + pipeline orchestration |
| `db.py` | All database logic |
| `deploy.sh` | Deployment — always use this |
| `logs.sh` | Tail container logs from local machine |
| `documents/CLAUDE.MD` | Full system reference |

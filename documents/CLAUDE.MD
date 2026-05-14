# Reddit LLM System — Project Documentation
<!-- Last updated: 14 May 2026 -->

## Project Goal
A scheduled Reddit digest app that collects posts from configured subreddits, summarises them with a local LLM, and serves a mobile-friendly web dashboard with real-time progress tracking.

## Current State (May 2026)
- **Fully deployed** on a home server via Docker, accessible via Tailscale
- **Pipeline runs automatically** at 00:00 / 06:00 / 12:00 / 18:00 (server time)
- **PWA** — added to iPhone home screen (manifest.json with `"orientation":"portrait"`)
- Active subreddits: DigitalAudioPlayer, longboarding, selfhosted
- DB purge window: 14 days

---

## System Architecture

```
COLLECTION PHASE:
  RSS Feed → Post URLs → Reddit JSON API → Smart Dedup → SQLite DB

SUMMARISATION PHASE:
  Top posts (per subreddit) → LLM (Gemma 3 12B via Ollama) → 5-sentence summary → DB

DISPLAY PHASE:
  Summarised posts → Web dashboard (news-digest.html) → Real-time polling
```

### Server Topology
```
Local Mac (kvirre)
    │  git push → GitHub → deploy.sh → SSH
    ▼
Server (Server@server) — macOS
    ├── /Users/server/mediastack/Reddit_LLM/   ← cloned repo + DB
    └── Docker container: reddit-news-server
            port 8000 → 100.77.129.54:8000
```

---

## Files

```
/Users/kvirre/Documents/Martin/Programmering/Reddit_LLM/
├── config.py            Configuration (fallback subreddits, Ollama URL, timeouts)
├── db.py                All DB operations (CRUD, settings, purge logic)
├── main.py              Post collector (RSS → Reddit API → DB)
├── summarize.py         Batch LLM summarisation (top posts per subreddit)
├── llm_processor.py     Low-level Ollama API calls
├── digest.py            CLI feed display (not used in server mode)
├── run.py               CLI orchestration (not used in server mode)
├── news-server2.py      HTTP server — pipeline orchestration + API + static serving
├── news-digest.html     Full frontend — CSS/JS/HTML inline, single file
├── manifest.json        PWA manifest (orientation: portrait, standalone display)
├── reddit_posts.db      SQLite DB (local dev copy — server has its own)
├── Dockerfile           Python 3.11 slim image
├── deploy.sh            Deployment script (always use this)
├── logs.sh              Read server container logs from local machine
└── documents/           Documentation (this folder)
```

---

## Database

### Schema

**posts** table:
```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    post_id TEXT UNIQUE NOT NULL,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    score INTEGER,
    upvote_ratio REAL,
    num_comments INTEGER,
    url TEXT NOT NULL,
    created_utc REAL,
    status TEXT DEFAULT 'new',   -- "new" | "refreshed" | "summarized"
    summary TEXT,
    fetched_at TIMESTAMP,
    updated_at TIMESTAMP,
    json_data TEXT NOT NULL      -- full Reddit JSON (post + comments)
)
```

**user_settings** table:
```sql
CREATE TABLE user_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
-- Keys: "subreddits" (JSON array), "llm_question" (string), "purge_days" (int: 7/14/21/28)
```

### Accessing the DB from this workspace

The real DB is volume-mounted from the RED external drive at:
```
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db   (on server, via SMB)
```

It is also accessible locally via the SMB share mounted at:
```
/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db   (on local Mac)
```

Query it directly via the SMB mount (no copy needed):
```bash
sqlite3 "/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db" \
    "SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit;"

# Open interactive shell
sqlite3 "/Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db"
```

> **Do NOT use scp to copy the DB locally** — the SMB mount gives direct access to the live file.

Common queries:
```sql
-- Post counts per subreddit
SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit;

-- How old are the oldest posts?
SELECT subreddit, MIN(datetime(created_utc,'unixepoch')) AS oldest FROM posts GROUP BY subreddit;

-- Check settings
SELECT * FROM user_settings;

-- Summarised vs unsummarised
SELECT subreddit, status, COUNT(*) FROM posts GROUP BY subreddit, status;

-- Top scored posts
SELECT subreddit, title, score FROM posts ORDER BY score DESC LIMIT 20;
```

### Key db.py functions
```python
init_db()                          # Create/migrate tables
store_or_update_post(data, json)   # Smart insert/update: "new"|"refreshed"|"unchanged"
get_top_posts(subreddit, n=5)      # Top N unsummarised posts by score
purge_old_posts(subreddit, days)   # Delete posts older than N days
purge_inactive_subreddits()        # Delete posts for subreddits no longer in settings
get_subreddits()                   # Active subreddits from DB (fallback: config.py)
set_subreddits(list)               # Save subreddit list to DB
get_llm_question()                 # Custom LLM question (fallback: hardcoded default)
set_llm_question(q)                # Save custom LLM question to DB
get_purge_days()                   # Returns int (default 14)
set_purge_days(days)               # Valid values: 7, 14, 21, 28
```

---

## Server / API

**news-server2.py** — ThreadingHTTPServer on port 8000.

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `news-digest.html` |
| GET | `/api/status` | Pipeline status + article data |
| POST | `/api/pipeline/start` | Trigger pipeline immediately |
| POST | `/api/settings/subreddits` | Update subreddit list |
| POST | `/api/settings/question` | Update LLM question |
| POST | `/api/settings/purge_days` | Update purge window (7/14/21/28) |

### `/api/status` response shape
```json
{
  "running": false,
  "subreddits": ["DigitalAudioPlayer", "longboarding", "selfhosted"],
  "llm_question": "...",
  "purge_days": 14,
  "status": {
    "DigitalAudioPlayer": {
      "phase": "idle",
      "collect_done": 25, "collect_total": 25,
      "summarize_done": 5, "summarize_total": 5,
      "articles": [...],
      "last_updated": "18:00"
    }
  }
}
```

`phase` values: `"idle"` | `"collecting"` | `"summarizing"` | `"backoff"` | `"done"`

**Stale-state guard**: if `pipeline_running == False` and phase is `"collecting"` or `"summarizing"`, the API forces it to `"idle"` before returning.

### Scheduled pipeline
Runs automatically at 00:00, 06:00, 12:00, 18:00 server time. Also triggerable via the Start Pipeline button in the UI (POST `/api/pipeline/start`).

---

## Frontend (news-digest.html)

Single self-contained HTML file — all CSS and JS inline.

### Key features
- **Tabs** — one per subreddit. Progress bar + badge + label + timestamp per tab.
- **Tab drag-to-reorder** — long-press (300ms) then horizontal drag. Other tabs shift to show the target slot. Order saved to server via `/api/settings/subreddits`.
  - Touch events handle mobile (non-passive `touchmove` to block scroll during drag).
  - Pointer events handle desktop.
  - Edge auto-scroll: dragging into the 60px zone at either end of the tab bar scrolls it automatically.
- **Settings modal** — ⚙️ button in header. Tabs: Subreddits, LLM Question, Purge Days.
- **Article panes** — swipe horizontally (or tab click) to switch subreddit. Full articles rendered with LLM summaries.
- **Polling** — fetches `/api/status` every 3 s while pipeline is running, less frequently when idle.

### Tab state management
```js
const CATS = [];          // Ordered subreddit list (matches tab DOM order)
let currentCat = null;    // Currently visible subreddit
```
`show(cat, btn)` switches the active tab and scrolls the panes track.
`saveTabOrder(newOrder)` persists the new order to the server.

---

## Reading Logs

```bash
# From local machine — tail last 300 lines of container logs
sh logs.sh

# Or with more lines
ssh Server@server "/usr/local/bin/docker logs reddit-news-server 2>&1 | tail -500"

# Follow live
ssh Server@server "/usr/local/bin/docker logs -f reddit-news-server 2>&1"
```

---

## Deployment

**Always deploy via:**
```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM
sh deploy.sh
```

The script:
1. Checks local tree is clean and pushes to GitHub
2. SSHs to Server@server, pulls repo to `/Users/server/mediastack/Reddit_LLM/`
3. Stops + removes the `reddit-news-server` container and old image
4. `docker compose build` (fresh) + `docker compose up -d`
5. Verifies the container is running and prints recent logs

**Never bypass deploy.sh** (no direct SSH docker commands, no `--no-verify`).

### Typical workflow
```bash
# 1. Edit files locally
# 2. Test locally if needed:
python3 news-server2.py   # then open http://localhost:8000

# 3. Commit
git add <files> && git commit -m "..."

# 4. Deploy
sh deploy.sh
```

---

## LLM Configuration

- **Model**: Gemma 3 12B (`gemma3:12b`) via Ollama on the server host
- **Ollama URL**: `http://host.docker.internal:11434/api/generate` (Docker → host bridge)
- **Default question**: configurable via Settings modal; stored in `user_settings` DB table
- **Timeout**: 120 s per post
- **Temperature**: 0.2

---

## Docker

```yaml
# /Users/server/mediastack/docker-compose.yaml (on server — this is the real file used by deploy.sh)
container_name: reddit-news-server
ports:       "8000:8000"
volumes:
  - /Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/reddit_posts.db:/app/reddit_posts.db
  - /Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/data:/app/data
  - /Volumes/RED - Backup OLD stuff/mediastack-data/reddit-llm/logs:/app/logs
restart: unless-stopped
```

> **Note**: The `docker-compose.yml` in the repo is NOT used by deploy.sh. The real compose file is `/Users/server/mediastack/docker-compose.yaml` on the server.

DB is volume-mounted — **survives container rebuilds**.

---

## Access

| Method | URL |
|--------|-----|
| Tailscale | http://100.77.129.54:8000 |
| Local (dev) | http://localhost:8000 |

---

## Known Limitations / Decisions

- **Orientation lock (PWA on iPhone)**: `manifest.json` has `"orientation":"portrait"` but Safari ignores it. This is an Apple limitation — no code fix possible.
- **Backup folder**: removed (no longer tracked).
- **MIGRATION_PLAN_SWIPE_NAV.md**: historical planning note for swipe navigation (now implemented as pane swipe). Can be deleted if desired.
- `IMPLEMENTATION_SUMMARY.md` and `SETTINGS_IMPLEMENTATION.md` are stale implementation histories from April 2026 — kept for reference but not maintained.

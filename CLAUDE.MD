# Reddit LLM System - Project Documentation

## Project Goal
Create a trending posts digest/newsflow by:
1. Collecting Reddit posts from configured subreddits
2. Storing posts with smart deduplication and content tracking
3. Processing posts through an LLM to generate newsworthy 5-sentence summaries
4. Building a digest of trending/important discussions

## Current Phase
**Phase 2 (In Progress):** Database collection and smart deduplication ✅ COMPLETE
- Next Phase: LLM integration for summarization

## System Architecture

```
RSS Feed
  ↓
Post URL extraction (25 per subreddit)
  ↓
Reddit JSON API (.json endpoint)
  ↓
Smart Deduplication & Content Comparison
  ↓
SQLite Database with Status Tracking
  ↓
[NEXT] LLM Processing (Mistral 7B via Ollama)
  ↓
[FUTURE] Digest/Newsflow generation
```

## Configuration

**File:** `config.py`
```python
SUBREDDITS = ["python", "programming", "learnprogramming"]  # Universal - can be any subreddits
REDDIT_RSS_URL = "https://www.reddit.com/r/{subreddit}/new.rss"
REQUEST_TIMEOUT = 10
USER_AGENT = "RedditLLM/1.0"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:7b-instruct"  # 8K token context window
LLM_TIMEOUT = 120
LLM_TEMPERATURE = 0.2
```

## Database Schema

**File:** `reddit_posts.db` (SQLite)

```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    post_id TEXT UNIQUE NOT NULL,        -- Reddit post ID (from URL)
    subreddit TEXT NOT NULL,             -- Which subreddit (python, programming, etc)
    title TEXT NOT NULL,                 -- Post title
    author TEXT,                         -- Post author
    score INTEGER,                       -- Current upvote score
    upvote_ratio REAL,                   -- Upvote ratio (0-1)
    num_comments INTEGER,                -- Total comments
    url TEXT NOT NULL,                   -- Full Reddit URL
    created_utc REAL,                    -- Original post timestamp
    status TEXT DEFAULT 'new',           -- "new" | "refreshed" | "summarized"
    summary TEXT,                        -- LLM-generated 5-sentence summary (NULL until processed)
    fetched_at TIMESTAMP,                -- When first fetched
    updated_at TIMESTAMP,                -- When last updated
    json_data TEXT NOT NULL              -- Full Reddit JSON API payload (post + comments)
)
```

## Status Field Semantics
- **"new"**: Newly inserted post (first fetch)
- **"refreshed"**: Post content changed (score/comments updated) on subsequent fetch
- **"summarized"**: LLM has processed this post and added summary

## Core Functions

### db.py - Database Layer

```python
init_db()                           # Create tables
post_exists(post_id)               # Returns (score, num_comments) if exists, else None
content_changed(post_id, score, comments)  # Check if metrics changed
store_or_update_post(post_data, json_payload)  # Smart insert/update logic
  Returns: "new" | "refreshed" | "unchanged" | None

get_post_count(subreddit=None)     # Total posts in DB
```

**Smart Deduplication Logic:**
1. If post_id doesn't exist → INSERT with status="new"
2. If post_id exists AND (score changed OR comments changed) → UPDATE with status="refreshed"
3. If post_id exists AND nothing changed → SKIP (no update)

### main.py - Post Collector

**Flow for each subreddit:**
1. Fetch RSS feed (25 posts limit)
2. For each post:
   - Extract post ID from URL
   - Fetch Reddit JSON API (.json endpoint)
   - Extract post metadata (title, author, score, comments)
   - Call db.store_or_update_post()
   - Print progress with status (✓ New, ↻ Refreshed, ⊘ Unchanged)
3. Print summary: X new, Y refreshed, Z unchanged, E errors

**Output Example:**
```
Processing r/python...
  [1/25] ✓ New: What's a low memory way to run a Python http endpoint? (38 pts)
  [2/25] ⊘ Unchanged: Python AI Agent Performance...
  [3/25] ↻ Refreshed: FastAPI vs Django (67 pts, 84 comments)
  Summary: 2 new, 1 refreshed, 22 unchanged, 0 errors
```

## Data Flow - Single Post

```
RSS Entry
  ├─ title: "What's a low memory way to run a Python http endpoint?"
  └─ link: "https://www.reddit.com/r/Python/comments/1slbp28/whats_a_low_memory_way_to_run_a_python_http/"

Extract post_id: "1slbp28"

Fetch: https://www.reddit.com/r/Python/comments/1slbp28/.json

Reddit API Returns: [post_data_object, comments_data_object]
  post_data_object['data']['children'][0]['data']:
    - title, author, score, upvote_ratio, num_comments, selftext, etc. (106 fields total)
    - Full JSON: ~120KB per post (includes all comments tree)

Store in DB:
  post_id: 1slbp28
  subreddit: python
  title: "What's a low memory way..."
  author: alexp702
  score: 36
  num_comments: 52
  status: "new" (first time) or "refreshed" (updated)
  json_data: [full API response with all comments]
  summary: NULL (waiting for LLM)
```

## Current Status (as of last run)

**Database Contents:**
- Total posts: 75
- r/python: 25 posts
- r/programming: 25 posts
- r/learnprogramming: 25 posts

**Smart Deduplication Test Results:**
- Second run: 0 new, 6 refreshed, 15 unchanged, 4 errors
- Meaning: 6 posts had engagement changes, 15 stayed same, 4 hit rate limits
- All data remained clean and consistent

## Next Phase: LLM Integration

### The Question to Ask
**"What are the key insights from this post, the poster's intention, and the following discussion? Summarize it in 5 sentences."**

### Implementation Needed
1. Create `llm_processor.py` module
2. Function to retrieve posts WHERE status != "summarized"
3. For each post:
   - Extract cleaned post + comments data from JSON
   - Send to Ollama with the question
   - Get 5-sentence response
   - Update DB: set status="summarized", summary="response"
4. Create output module for digest generation

### Mistral 7B Capabilities
- Context window: 8,192 tokens (8K)
- Can easily handle 1 post + 15-20 comments + JSON structure
- Good at instruction following and structured output

## Important Notes

### Reddit API
- No authentication required for public endpoints
- JSON endpoint: Just add `.json` to any Reddit URL
- Returns: [post_wrapper, comments_wrapper] structure
- Each post is `kind: 't1'` for comments, `kind: 't3'` for posts
- Rate limits: ~60 requests per minute (hit at 429 errors)

### Deduplication Strategy
- Not about "skipping duplicates" but "keeping posts fresh"
- Tracks engagement changes (upvotes, comments)
- Detects when posts go viral or gain discussion
- All changes timestamped

### Database Persistence
- SQLite file: `reddit_posts.db`
- All Reddit API JSON stored as TEXT (for future analysis)
- Status field enables workflow tracking: new → refreshed → summarized

## Files & Locations

```
/Users/kvirre/Documents/Martin/Programmering/Reddit_LLM/
├── config.py                 # Configuration constants
├── db.py                     # Database layer (smart dedup, CRUD)
├── main.py                   # Post collector (RSS → API → DB)
├── reddit_posts.db           # SQLite database (75 posts)
├── requirements.txt          # Python dependencies
├── Dockerfile               # (Not in use)
├── docker-compose.yml       # (Not in use)
└── CLAUDE.MD                # This file
```

## How to Run

```bash
cd /Users/kvirre/Documents/Martin/Programmering/Reddit_LLM

# Initial collection
python3 main.py

# Subsequent runs (will show refreshed/unchanged posts)
python3 main.py
```

## Dependencies

```
requests==2.31.0         # HTTP requests
feedparser==6.0.10       # RSS parsing
beautifulsoup4==4.12.2   # HTML parsing (if needed)
playwright==1.58.0       # Browser automation (installed but not currently used)
```

## User Requirements (Confirmed)
1. ✅ Simple sequential system (no threading, no async)
2. ✅ Universal subreddit support (not just Python-focused)
3. ✅ Smart deduplication with content tracking
4. ✅ Status flags for workflow
5. ⏳ LLM processing with specific question
6. ⏳ Newsworthy 5-sentence summaries
7. ⏳ Digest/newsflow generation

## Technical Decisions

### Why Reddit JSON API instead of scraping?
- Clean structured data (no HTML parsing needed)
- Full comments tree included
- Reliable (no anti-bot measures)
- Fast and simple (just add .json to URL)

### Why SQLite?
- Persistent local storage
- No external dependencies
- Easy to query and modify
- Good for 1000s of posts

### Why store full JSON?
- Comments data for LLM context
- Track all engagement metrics
- Reproducible analysis
- Future flexibility

### Why Mistral 7B?
- 8K context window (enough for post + comments)
- Good instruction following
- Fast inference
- Runs locally via Ollama (no API limits)

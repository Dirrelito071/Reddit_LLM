"""
Database layer — store Reddit posts in SQLite.
"""

import sqlite3
import json
import logging
import config

logger = logging.getLogger(__name__)
DB_PATH = "reddit_posts.db"


def init_db():
    """Initialize database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE NOT NULL,
            subreddit TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            score INTEGER,
            upvote_ratio REAL,
            num_comments INTEGER,
            previous_score INTEGER,
            url TEXT NOT NULL,
            created_utc REAL,
            status TEXT DEFAULT 'new',
            summary TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            json_data TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: add previous_score if missing (existing databases)
    try:
        cursor.execute("ALTER TABLE posts ADD COLUMN previous_score INTEGER")
        conn.commit()
    except Exception:
        pass  # Column already exists

    conn.commit()

    _seed_default_settings(conn)
    conn.close()


def _seed_default_settings(conn=None):
    """Seed default settings if user_settings table is empty."""
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True
    else:
        close_conn = False

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE setting_key = 'subreddits'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO user_settings (setting_key, setting_value) VALUES (?, ?)",
                ("subreddits", json.dumps(config.SUBREDDITS)),
            )

        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE setting_key = 'llm_question'")
        if cursor.fetchone()[0] == 0:
            default_question = (
                "What are the key insights from this post, the poster's intention, "
                "and the following discussion? Summarize it in 5 sentences."
            )
            cursor.execute(
                "INSERT INTO user_settings (setting_key, setting_value) VALUES (?, ?)",
                ("llm_question", default_question),
            )

        conn.commit()
    except Exception as e:
        logger.error(f"Error seeding default values: {e}")
        conn.rollback()
    finally:
        if close_conn:
            conn.close()


# ── Progress ──────────────────────────────────────────────────────────────────

def init_progress():
    """Initialize progress tracking table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            subreddit TEXT PRIMARY KEY,
            phase TEXT DEFAULT 'idle',
            subphase TEXT DEFAULT NULL,
            pct INTEGER DEFAULT 0,
            current INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            total_posts INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()


def update_progress(subreddit, phase, pct, total_posts=0, subphase=None, current=0, total=0):
    """Update progress for a subreddit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if phase == "ready":
        cursor.execute("""
            INSERT OR REPLACE INTO progress
                (subreddit, phase, subphase, pct, current, total, total_posts, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (subreddit, phase, subphase, pct, current, total, total_posts))
    else:
        cursor.execute("SELECT last_updated FROM progress WHERE subreddit = ?", (subreddit,))
        result = cursor.fetchone()
        last_updated = result[0] if result else None
        cursor.execute("""
            INSERT OR REPLACE INTO progress
                (subreddit, phase, subphase, pct, current, total, total_posts, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (subreddit, phase, subphase, pct, current, total, total_posts, last_updated))

    conn.commit()
    conn.close()


def get_progress():
    """Get progress for all subreddits."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT subreddit, phase, subphase, pct, current, total, total_posts, last_updated "
        "FROM progress ORDER BY subreddit"
    )
    rows = cursor.fetchall()
    conn.close()

    return {
        subreddit: {
            "phase": phase, "subphase": subphase, "pct": pct,
            "current": current, "total": total,
            "total_posts": total_posts, "last_updated": last_updated,
        }
        for subreddit, phase, subphase, pct, current, total, total_posts, last_updated in rows
    }


def reset_progress():
    """Clear all progress records."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM progress")
    conn.commit()
    conn.close()


# ── Posts ─────────────────────────────────────────────────────────────────────

def replace_posts(subreddit, posts):
    """
    Delete all existing posts for the subreddit and insert the new ones.

    posts: list of (post_id, post_data_dict, stripped_json_dict)
    Every post is inserted with status='new' so summarize.py picks them all up.
    """
    # Deduplicate by post_id — Reddit hot feed can return the same post twice
    # (stickied posts appear at position 0 AND again in the ranked list)
    seen = set()
    unique_posts = [p for p in posts if not (p[0] in seen or seen.add(p[0]))]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM posts WHERE subreddit = ?", (subreddit,))
    for post_id, post_data, json_payload in unique_posts:
        cursor.execute("""
            INSERT INTO posts
                (post_id, subreddit, title, author, score, upvote_ratio,
                 num_comments, url, created_utc, status, json_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
        """, (
            post_id,
            post_data.get("subreddit", subreddit),
            post_data.get("title"),
            post_data.get("author"),
            post_data.get("score"),
            post_data.get("upvote_ratio"),
            post_data.get("num_comments"),
            f"https://www.reddit.com{post_data.get('permalink', '')}",
            post_data.get("created_utc"),
            json.dumps(json_payload),
        ))
    conn.commit()
    conn.close()


def get_post_count(subreddit=None):
    """Get total posts stored (optionally for a specific subreddit)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if subreddit:
        cursor.execute("SELECT COUNT(*) FROM posts WHERE subreddit = ?", (subreddit,))
    else:
        cursor.execute("SELECT COUNT(*) FROM posts")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def purge_inactive_subreddits():
    """Delete all posts for subreddits no longer in the active list."""
    active = get_subreddits()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT subreddit FROM posts")
    all_subs = [r[0] for r in cursor.fetchall()]
    for sub in all_subs:
        if sub not in active:
            cursor.execute("DELETE FROM posts WHERE subreddit = ?", (sub,))
            logger.info(f"Purged posts for removed subreddit r/{sub}")
    conn.commit()
    conn.close()


# ── User Settings ─────────────────────────────────────────────────────────────

def get_setting(key, default=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_settings")
        if cursor.fetchone()[0] == 0:
            _seed_default_settings(conn)
        cursor.execute("SELECT setting_value FROM user_settings WHERE setting_key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return default


def set_setting(key, value):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")
        return False


def get_subreddits():
    stored = get_setting("subreddits")
    if stored:
        try:
            return json.loads(stored)
        except Exception as e:
            raise RuntimeError(f"Invalid subreddits value in DB: {e}")
    raise RuntimeError("No subreddits found in DB.")


def set_subreddits(subreddit_list):
    if not subreddit_list:
        logger.error("Cannot set empty subreddit list")
        return False
    return set_setting("subreddits", json.dumps(subreddit_list))


def get_llm_question():
    stored = get_setting("llm_question")
    if stored:
        return stored
    default = (
        "What are the key insights from this post, the poster's intention, "
        "and the following discussion? Summarize it in 5 sentences."
    )
    set_setting("llm_question", default)
    return default


def set_llm_question(question):
    if not question or not question.strip():
        logger.error("Cannot set empty LLM question")
        return False
    return set_setting("llm_question", question)


def get_llm_model():
    stored = get_setting("llm_model")
    if stored:
        return stored
    default_model = getattr(config, "MODEL", "qwen3-8b")
    set_setting("llm_model", default_model)
    return default_model


def set_llm_model(model):
    if not model or not model.strip():
        logger.error("Cannot set empty LLM model")
        return False
    return set_setting("llm_model", model)


def get_purge_days():
    """Get post age limit in days (default 14)."""
    stored = get_setting("purge_days")
    if stored:
        try:
            return int(stored)
        except Exception:
            pass
    return 14


def set_purge_days(days):
    """Store post age limit in days. Allowed values: 7, 14, 21, 28."""
    if days not in (7, 14, 21, 28):
        logger.error(f"Invalid purge_days value: {days}")
        return False
    return set_setting("purge_days", str(days))


def reset_progress_for_subreddit(subreddit):
    """Clear progress records for a single subreddit only."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM progress WHERE subreddit = ?", (subreddit,))
    conn.commit()
    conn.close()

def purge_old_posts(subreddit, days=7):
    """Delete posts older than N days for a subreddit."""
    import time
    days = 3 if days == 7 else days  # Default to 3 days if called without explicit days
    cutoff = time.time() - days * 86400
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM posts WHERE subreddit = ? AND created_utc < ?",
        (subreddit, cutoff)
    )
    conn.commit()
    conn.close()
def mark_all_unprocessed(subreddit):
    """Set status='unprocessed' for all posts in a subreddit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE posts SET status = 'unprocessed' WHERE subreddit = ?
    """, (subreddit,))
    conn.commit()
    conn.close()

def update_post_status(post_id, status, json_data=None, metrics=None):
    """
    Update status (and optionally json_data, score, num_comments, upvote_ratio) for a post.
    metrics: dict with keys 'score', 'num_comments', 'upvote_ratio' (optional)
    """
    import time, datetime
    now_local = datetime.datetime.fromtimestamp(time.time()).isoformat(sep=' ', timespec='seconds')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if json_data is not None and metrics is not None:
        cursor.execute("""
            UPDATE posts SET status = ?, json_data = ?, score = ?, num_comments = ?, upvote_ratio = ?, updated_at = ? WHERE post_id = ?
        """, (status, json.dumps(json_data), metrics.get('score'), metrics.get('num_comments'), metrics.get('upvote_ratio'), now_local, post_id))
    elif json_data is not None:
        cursor.execute("""
            UPDATE posts SET status = ?, json_data = ?, updated_at = ? WHERE post_id = ?
        """, (status, json.dumps(json_data), now_local, post_id))
    else:
        cursor.execute("""
            UPDATE posts SET status = ?, updated_at = ? WHERE post_id = ?
        """, (status, now_local, post_id))
    conn.commit()
    conn.close()

def get_unprocessed_posts(subreddit):
    """Return list of (post_id, json_data) for posts with status='unprocessed' in subreddit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, json_data FROM posts WHERE subreddit = ? AND status = 'unprocessed'
    """, (subreddit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
"""
Database layer - Store Reddit posts in SQLite
"""

import sqlite3
import json
import logging
import config

logger = logging.getLogger(__name__)
DB_PATH = "reddit_posts.db"


def init_db():
    """Initialize database schema"""
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
            previous_num_comments INTEGER,
            url TEXT NOT NULL,
            created_utc REAL,
            status TEXT DEFAULT 'new',
            summary TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            json_data TEXT NOT NULL
        )
    """)
    
    # Migration: Add columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE posts ADD COLUMN previous_score INTEGER")
    except:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE posts ADD COLUMN previous_num_comments INTEGER")
    except:
        pass  # Column already exists
    
    # User settings table for custom subreddits and LLM question
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    
    # Seed default values if they don't exist (separate transaction)
    _seed_default_settings(conn)
    
    conn.close()


def _seed_default_settings(conn=None):
    """Seed default settings if user_settings table is empty"""
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True
    else:
        close_conn = False
    
    try:
        cursor = conn.cursor()
        
        # Check if defaults already set
        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE setting_key = 'subreddits'")
        if cursor.fetchone()[0] == 0:
            # Set default subreddits from config
            default_subs = json.dumps(config.SUBREDDITS)
            cursor.execute(
                "INSERT INTO user_settings (setting_key, setting_value) VALUES (?, ?)",
                ('subreddits', default_subs)
            )
            logger.info(f"✓ Seeded default subreddits: {config.SUBREDDITS}")
        
        # Check if default question already set
        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE setting_key = 'llm_question'")
        if cursor.fetchone()[0] == 0:
            # Set default question
            default_question = "What are the key insights from this post, the poster's intention, and the following discussion? Summarize it in 5 sentences."
            cursor.execute(
                "INSERT INTO user_settings (setting_key, setting_value) VALUES (?, ?)",
                ('llm_question', default_question)
            )
            logger.info(f"✓ Seeded default LLM question")
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error seeding default values: {e}")
        conn.rollback()
    finally:
        if close_conn:
            conn.close()


def post_exists(post_id):
    """Check if a post already exists in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT score, num_comments FROM posts WHERE post_id = ?", (post_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"Error checking post existence: {e}")
        return None


def content_changed(post_id, new_score, new_num_comments):
    """Check if post metrics have changed (score or comments)"""
    existing = post_exists(post_id)
    if not existing:
        return False  # Post doesn't exist yet
    
    old_score, old_num_comments = existing
    return (old_score != new_score) or (old_num_comments != new_num_comments)


def comments_changed(post_id, new_num_comments):
    """Check if comment count changed (triggers re-summarization)"""
    existing = post_exists(post_id)
    if not existing:
        return False
    
    old_score, old_num_comments = existing
    return old_num_comments != new_num_comments


def store_or_update_post(post_data, json_payload):
    """
    Store new post or update if content changed
    
    Args:
        post_data: Dictionary with post info
        json_payload: Full JSON data from API
    
    Returns:
        "new" if inserted, "refreshed" if updated, "unchanged" if no change, None if error
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        post_id = post_data['id']
        
        # Check if post exists
        if post_exists(post_id):
            # Post exists - check if metrics changed (for ranking updates)
            if content_changed(post_id, post_data['score'], post_data['num_comments']):
                # Get current values to store as previous
                cursor.execute("""
                    SELECT score, num_comments, status FROM posts WHERE post_id = ?
                """, (post_id,))
                prev_result = cursor.fetchone()
                prev_score, prev_num_comments, current_status = prev_result if prev_result else (None, None, None)
                
                # Determine new status:
                # - Only set 'refreshed' if comments changed (new discussion to summarize)
                # - If only score changed, preserve current status (e.g., 'summarized')
                if prev_num_comments != post_data['num_comments']:
                    new_status = 'refreshed'
                else:
                    new_status = current_status  # Keep existing status
                
                # Update metrics (always update for ranking) but status only changes if comments changed
                cursor.execute("""
                    UPDATE posts 
                    SET score = ?, upvote_ratio = ?, num_comments = ?, 
                        previous_score = ?, previous_num_comments = ?,
                        status = ?, updated_at = CURRENT_TIMESTAMP, json_data = ?
                    WHERE post_id = ?
                """, (
                    post_data['score'],
                    post_data['upvote_ratio'],
                    post_data['num_comments'],
                    prev_score,
                    prev_num_comments,
                    new_status,
                    json.dumps(json_payload),
                    post_id
                ))
                conn.commit()
                conn.close()
                return "refreshed" if new_status == 'refreshed' else "updated"
            else:
                # Content unchanged - skip
                conn.close()
                return "unchanged"
        else:
            # New post - insert (no previous values)
            cursor.execute("""
                INSERT INTO posts 
                (post_id, subreddit, title, author, score, upvote_ratio, num_comments, 
                 previous_score, previous_num_comments, url, created_utc, status, json_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 'new', ?)
            """, (
                post_id,
                post_data['subreddit'],
                post_data['title'],
                post_data['author'],
                post_data['score'],
                post_data['upvote_ratio'],
                post_data['num_comments'],
                post_data['url'],
                post_data['created_utc'],
                json.dumps(json_payload)
            ))
            conn.commit()
            conn.close()
            return "new"
            
    except Exception as e:
        print(f"Error storing/updating post: {e}")
        return None


def get_post_count(subreddit=None):
    """Get total posts stored (optionally for a specific subreddit)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if subreddit:
        cursor.execute("SELECT COUNT(*) FROM posts WHERE subreddit = ?", (subreddit,))
    else:
        cursor.execute("SELECT COUNT(*) FROM posts")
    
    count = cursor.fetchone()[0]
    conn.close()
    return count

def init_progress():
    """Initialize progress tracking table"""
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

    # Migration: Add new columns if they don't exist
    migrations = [
        ("ALTER TABLE progress ADD COLUMN last_updated TIMESTAMP DEFAULT NULL", "last_updated"),
        ("ALTER TABLE progress ADD COLUMN subphase TEXT DEFAULT NULL", "subphase"),
        ("ALTER TABLE progress ADD COLUMN current INTEGER DEFAULT 0", "current"),
        ("ALTER TABLE progress ADD COLUMN total INTEGER DEFAULT 0", "total"),
    ]
    for sql, col in migrations:
        try:
            cursor.execute(sql)
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()


def reset_progress():
    """Clear all progress records"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM progress")
    
    conn.commit()
    conn.close()


def update_progress(subreddit, phase, pct, total_posts=0, subphase=None, current=0, total=0):
    """Update progress for a subreddit, supporting subphase and step counts"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # If phase is 'ready', record the timestamp
    if phase == "ready":
        cursor.execute("""
            INSERT OR REPLACE INTO progress (subreddit, phase, subphase, pct, current, total, total_posts, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (subreddit, phase, subphase, pct, current, total, total_posts))
    else:
        # Get current last_updated to preserve existing timestamp
        cursor.execute("SELECT last_updated FROM progress WHERE subreddit = ?", (subreddit,))
        result = cursor.fetchone()
        last_updated = result[0] if result else None

        cursor.execute("""
            INSERT OR REPLACE INTO progress (subreddit, phase, subphase, pct, current, total, total_posts, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (subreddit, phase, subphase, pct, current, total, total_posts, last_updated))

    conn.commit()
    conn.close()


def get_progress():
    """Get progress for all subreddits"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subreddit, phase, subphase, pct, current, total, total_posts, last_updated FROM progress ORDER BY subreddit")
    rows = cursor.fetchall()
    conn.close()

    progress = {}
    for subreddit, phase, subphase, pct, current, total, total_posts, last_updated in rows:
        progress[subreddit] = {
            "phase": phase,
            "subphase": subphase,
            "pct": pct,
            "current": current,
            "total": total,
            "total_posts": total_posts,
            "last_updated": last_updated
        }

    return progress


# User Settings Functions

def get_setting(key, default=None):
    """Get a user setting from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Ensure defaults are seeded if table exists but is empty
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
    """Set a user setting in database"""
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
    """Get list of subreddits from database (seeds from config if empty on first read)"""
    stored = get_setting("subreddits")
    if stored:
        try:
            return json.loads(stored)
        except Exception as e:
            logger.error(f"Error parsing subreddits from DB: {e}")
    
    # Seed from config on first read if not in DB
    default_subs = json.dumps(config.SUBREDDITS)
    set_setting("subreddits", default_subs)
    logger.info(f"Seeded subreddits from config: {config.SUBREDDITS}")
    return list(config.SUBREDDITS)


def set_subreddits(subreddit_list):
    """Store subreddit list in database"""
    if not subreddit_list or len(subreddit_list) == 0:
        logger.error("Cannot set empty subreddit list")
        return False
    return set_setting("subreddits", json.dumps(subreddit_list))


def get_llm_question():
    """Get custom LLM question from database (seeds from default if empty on first read)"""
    stored = get_setting("llm_question")
    if stored:
        return stored
    
    # Seed from default on first read if not in DB
    default_question = "What are the key insights from this post, the poster's intention, and the following discussion? Summarize it in 5 sentences."
    set_setting("llm_question", default_question)
    logger.info("Seeded LLM question from default")
    return default_question


def set_llm_question(question):
    """Store custom LLM question in database"""
    if not question or question.strip() == "":
        logger.error("Cannot set empty LLM question")
        return False
    return set_setting("llm_question", question)
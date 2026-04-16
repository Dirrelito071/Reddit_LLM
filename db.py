"""
Database layer - Store Reddit posts in SQLite
"""

import sqlite3
import json

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
    
    conn.commit()
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
    """Check if post content has changed (score or comments)"""
    existing = post_exists(post_id)
    if not existing:
        return False  # Post doesn't exist yet
    
    old_score, old_num_comments = existing
    return (old_score != new_score) or (old_num_comments != new_num_comments)


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
            # Post exists - check if content changed
            if content_changed(post_id, post_data['score'], post_data['num_comments']):
                # Get current values to store as previous
                cursor.execute("""
                    SELECT score, num_comments FROM posts WHERE post_id = ?
                """, (post_id,))
                prev_result = cursor.fetchone()
                prev_score, prev_num_comments = prev_result if prev_result else (None, None)
                
                # Content changed - update with previous values stored
                cursor.execute("""
                    UPDATE posts 
                    SET score = ?, upvote_ratio = ?, num_comments = ?, 
                        previous_score = ?, previous_num_comments = ?,
                        status = 'refreshed', updated_at = CURRENT_TIMESTAMP, json_data = ?
                    WHERE post_id = ?
                """, (
                    post_data['score'],
                    post_data['upvote_ratio'],
                    post_data['num_comments'],
                    prev_score,
                    prev_num_comments,
                    json.dumps(json_payload),
                    post_id
                ))
                conn.commit()
                conn.close()
                return "refreshed"
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
            pct INTEGER DEFAULT 0,
            total_posts INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT NULL
        )
    """)
    
    # Migration: Add last_updated column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE progress ADD COLUMN last_updated TIMESTAMP DEFAULT NULL")
    except:
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


def update_progress(subreddit, phase, pct, total_posts=0):
    """Update progress for a subreddit"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # If phase is 'ready', record the timestamp
    if phase == "ready":
        cursor.execute("""
            INSERT OR REPLACE INTO progress (subreddit, phase, pct, total_posts, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (subreddit, phase, pct, total_posts))
    else:
        # Get current last_updated to preserve existing timestamp
        cursor.execute("SELECT last_updated FROM progress WHERE subreddit = ?", (subreddit,))
        result = cursor.fetchone()
        last_updated = result[0] if result else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO progress (subreddit, phase, pct, total_posts, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """, (subreddit, phase, pct, total_posts, last_updated))
    
    conn.commit()
    conn.close()


def get_progress():
    """Get progress for all subreddits"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subreddit, phase, pct, total_posts, last_updated FROM progress ORDER BY subreddit")
    rows = cursor.fetchall()
    conn.close()
    
    progress = {}
    for subreddit, phase, pct, total_posts, last_updated in rows:
        progress[subreddit] = {
            "phase": phase,
            "pct": pct,
            "total_posts": total_posts,
            "last_updated": last_updated
        }
    
    return progress
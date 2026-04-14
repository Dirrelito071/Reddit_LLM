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
            url TEXT NOT NULL,
            created_utc REAL,
            status TEXT DEFAULT 'new',
            summary TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            json_data TEXT NOT NULL
        )
    """)
    
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
                # Content changed - update
                cursor.execute("""
                    UPDATE posts 
                    SET score = ?, upvote_ratio = ?, num_comments = ?, 
                        status = 'refreshed', updated_at = CURRENT_TIMESTAMP, json_data = ?
                    WHERE post_id = ?
                """, (
                    post_data['score'],
                    post_data['upvote_ratio'],
                    post_data['num_comments'],
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
            # New post - insert
            cursor.execute("""
                INSERT INTO posts 
                (post_id, subreddit, title, author, score, upvote_ratio, num_comments, url, created_utc, status, json_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
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

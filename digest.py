"""
Digest - Show top 5 hottest posts per subreddit with engagement tracking and summaries
"""

import sqlite3

DB_PATH = "reddit_posts.db"

print("=" * 80)
print("REDDIT POSTS DIGEST - TOP 5 HOTTEST")
print("=" * 80)
print()

# Get unique subreddits
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT subreddit FROM posts ORDER BY subreddit")
subreddits = cursor.fetchall()

for (subreddit,) in subreddits:
    print(f"=== r/{subreddit} TOP 5 ===\n")
    
    # Get top 5 posts by score
    cursor.execute("""
        SELECT post_id, title, score, num_comments, status, previous_score, summary
        FROM posts
        WHERE subreddit = ?
        ORDER BY score DESC
        LIMIT 5
    """, (subreddit,))
    
    posts = cursor.fetchall()
    
    if not posts:
        print("  (no posts)\n")
        continue
    
    for rank, (post_id, title, score, num_comments, status, previous_score, summary) in enumerate(posts, 1):
        # Determine engagement direction
        if status == "new":
            arrow = "→"  # New post (neutral)
        elif status == "refreshed":
            # Compare previous to current score
            if previous_score is not None:
                if score > previous_score:
                    arrow = "↑"  # Score went up
                elif score < previous_score:
                    arrow = "↓"  # Score went down
                else:
                    arrow = "→"  # No change (shouldn't happen if refreshed)
            else:
                arrow = "↑"  # No previous value, assume up
        elif status == "summarized":
            arrow = "✓"  # Summarized
        else:
            arrow = "•"  # Unknown status
        
        short_title = title[:60] + "..." if len(title) > 60 else title
        print(f"{rank}. {arrow} {short_title}")
        print(f"   Score: {score} | Comments: {num_comments}")
        
        if summary:
            print(f"   Summary: {summary}")
        else:
            print(f"   (no summary)")
        
        print()
    
    print()

conn.close()

print("=" * 80)
print("Legend: → = New  |  ↑ = Engagement up  |  ↓ = Engagement down  |  ✓ = Summarized")
print("=" * 80)

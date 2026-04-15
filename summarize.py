"""
Summarize Reddit posts - Process top 5 posts per subreddit through LLM
"""

import sqlite3
import llm_processor
import sys
import time

DB_PATH = "reddit_posts.db"

# Check for --subreddit parameter
target_subreddit = None
if len(sys.argv) > 2 and sys.argv[1] == "--subreddit":
    target_subreddit = sys.argv[2]

if target_subreddit:
    print("=" * 80)
    print(f"REDDIT POST SUMMARIZER - r/{target_subreddit}")
    print("=" * 80)
else:
    print("=" * 80)
    print("REDDIT POST SUMMARIZER - TOP 5 PER SUBREDDIT")
    print("=" * 80)

print()

# Get unique subreddits
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

if target_subreddit:
    cursor.execute("SELECT DISTINCT subreddit FROM posts WHERE subreddit = ? ORDER BY subreddit", (target_subreddit,))
else:
    cursor.execute("SELECT DISTINCT subreddit FROM posts ORDER BY subreddit")

subreddits = cursor.fetchall()

total_processed = 0
total_skipped = 0
total_errors = 0

for (subreddit,) in subreddits:
    print(f"r/{subreddit}:")
    
    # Get top 5 unsummarized posts by score
    cursor.execute("""
        SELECT post_id, title, status
        FROM posts
        WHERE subreddit = ? AND status != 'summarized'
        ORDER BY score DESC
        LIMIT 5
    """, (subreddit,))
    
    posts = cursor.fetchall()
    
    if not posts:
        print(f"  ✓ All top posts already summarized\n")
        continue
    
    print(f"  Found {len(posts)} unsummarized posts\n")
    
    processed = 0
    skipped = 0
    errors = 0
    
    for i, (post_id, title, status) in enumerate(posts, 1):
        short_title = title[:50] + "..." if len(title) > 50 else title
        post_start = time.time()
        print(f"  [{i}/5] Processing: {short_title}")
        
        result = llm_processor.process_post(post_id)
        elapsed = time.time() - post_start
        
        if result is True:
            print(f"       ✓ Summarized ({elapsed:.1f}s)\n")
            processed += 1
        elif result == "already_summarized":
            print(f"       ⊘ Already summarized\n")
            skipped += 1
        else:
            print(f"       ✗ Error\n")
            errors += 1
    
    print(f"  Summary: {processed} processed, {skipped} skipped, {errors} errors\n")
    
    total_processed += processed
    total_skipped += skipped
    total_errors += errors

conn.close()

# Final summary
if target_subreddit:
    print("=" * 80)
    print(f"SUMMARIZATION COMPLETE - r/{target_subreddit}")
    print("=" * 80)
    print(f"✓ Processed: {total_processed}")
    print(f"⊘ Skipped:   {total_skipped}")
    print(f"✗ Errors:    {total_errors}")
else:
    print("=" * 80)
    print("SUMMARIZATION COMPLETE")
    print("=" * 80)
    print(f"✓ Total Processed:  {total_processed}")
    print(f"⊘ Total Skipped:    {total_skipped}")
    print(f"✗ Total Errors:     {total_errors}")
print()

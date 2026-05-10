"""
Summarize Reddit posts - Process top 5 posts per subreddit through LLM
"""

import sqlite3
import llm_processor
import sys
import time
import db

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

# Load custom LLM question from database
custom_question = db.get_llm_question()
print(f"Using LLM question: {custom_question[:70]}...\n")

for (subreddit,) in subreddits:
    print(f"r/{subreddit}:")
    
    # Get actual top 5 posts by score (regardless of status)
    # llm_processor will skip posts that are already summarized
    cursor.execute("""
        SELECT post_id, title, status
        FROM posts
        WHERE subreddit = ?
        ORDER BY score DESC
        LIMIT 5
    """, (subreddit,))
    
    posts_to_process = cursor.fetchall()
    
    if not posts_to_process:
        print(f"  ✓ No posts found\n")
        db.update_progress(subreddit, "ready", 100, 5)
        continue
    
    already_done = sum(1 for _, _, s in posts_to_process if s == 'summarized')
    needs_summary = len(posts_to_process) - already_done
    if needs_summary == 0:
        print(f"  ✓ All top {len(posts_to_process)} posts already summarized\n")
        db.update_progress(subreddit, "ready", 100, len(posts_to_process))
        continue
    
    print(f"  Top {len(posts_to_process)} posts: {needs_summary} need summarization, {already_done} already done\n")
    
    # Progress total = only posts that need work, so UI shows e.g. 1/2 not 4/5
    db.update_progress(subreddit, "summarizing", 0, needs_summary, current=0, total=needs_summary)
    
    processed = 0
    skipped = 0
    errors = 0
    work_i = 0  # only increments for posts actually sent to LLM
    
    for (post_id, title, status) in posts_to_process:
        short_title = title[:50] + "..." if len(title) > 50 else title
        
        # Pre-filter: skip without touching work counter or progress
        if status == 'summarized':
            print(f"  [skip] ⊘ Already summarized: {short_title}")
            skipped += 1
            continue
        
        work_i += 1
        pct = int((work_i / needs_summary) * 100)
        db.update_progress(subreddit, "summarizing", pct, needs_summary, current=work_i, total=needs_summary)
        
        post_start = time.time()
        print(f"  [{work_i}/{needs_summary}] Processing: {short_title}")
        
        result = llm_processor.process_post(post_id, custom_question=custom_question)
        elapsed = time.time() - post_start
        
        pct = int((work_i / needs_summary) * 100)
        db.update_progress(subreddit, "summarizing", pct, needs_summary, current=work_i, total=needs_summary)
        
        if result is True:
            print(f"       ✓ Summarized ({elapsed:.1f}s)\n")
            processed += 1
        elif result == "already_summarized":
            # Shouldn't happen after pre-filter, but handle gracefully
            print(f"       ⊘ Already summarized\n")
            skipped += 1
        else:
            print(f"       ✗ Error\n")
            errors += 1
    
    # Mark as ready when done
    db.update_progress(subreddit, "ready", 100, needs_summary, current=needs_summary, total=needs_summary)
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

"""
Main Reddit Collector - Fetch posts and store in database
Fetches 25 posts per subreddit via RSS, collects JSON data, deduplicates, and stores
"""

import config
import requests
import feedparser
import db
import sys
import json
import time

# Initialize database to seed defaults if needed
db.init_db()
db.init_progress()

# Check for --subreddit parameter
target_subreddit = None
if len(sys.argv) > 2 and sys.argv[1] == "--subreddit":
    target_subreddit = sys.argv[2]
    subreddits_to_process = [target_subreddit]
else:
    # Load subreddits from database (seeded from config.py on first run)
    subreddits_json = db.get_setting("subreddits", json.dumps(config.SUBREDDITS))
    subreddits_to_process = json.loads(subreddits_json)

if target_subreddit:
    print("=" * 80)
    print(f"REDDIT POST COLLECTOR - r/{target_subreddit}")
    print("=" * 80)
else:
    print("=" * 80)
    print("REDDIT POST COLLECTOR")
    print("=" * 80)
    print(f"Subreddits: {', '.join(subreddits_to_process)}")

print()

# Initialize progress tracking
db.init_progress()
print("✓ Database initialized\n")

# Process each subreddit
for subreddit in subreddits_to_process:

    print(f"{'=' * 80}")
    print(f"Processing r/{subreddit}...")
    print(f"{'=' * 80}")

    # Step 0: Purge old posts (older than 7 days)
    db.purge_old_posts(subreddit)
    # Step 1: Mark all as unprocessed
    db.mark_all_unprocessed(subreddit)
    db.update_progress(subreddit, "collecting", 0, 0, subphase="rss", current=0, total=25)

    # Step 2: Process latest 25 from RSS
    url = config.REDDIT_RSS_URL.format(subreddit=subreddit)
    try:
        response = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"  ✗ Error fetching RSS: {e}\n")
        continue

    if not feed.entries:
        print(f"  ✗ No posts found\n")
        continue

    new_count = 0
    refreshed_count = 0
    stale_count = 0
    error_count = 0

    for i, entry in enumerate(feed.entries[:25], 1):
        db.update_progress(subreddit, "collecting", int(i/25*100), 0, subphase="rss", current=i, total=25)
        post_url = entry.link
        title = entry.title[:60] + "..." if len(entry.title) > 60 else entry.title
        post_id = post_url.split('/comments/')[1].split('/')[0] if '/comments/' in post_url else None
        if not post_id:
            print(f"  [{i}/25] ✗ Could not extract post ID")
            error_count += 1
            continue

        api_url = post_url.rstrip('/') + '.json'
        try:
            api_response = requests.get(api_url, headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
            api_response.raise_for_status()
            api_data = api_response.json()
            if isinstance(api_data, list) and len(api_data) > 0:
                post_data = api_data[0]['data']['children'][0]['data']
                store_data = {
                    'id': post_id,
                    'subreddit': subreddit,
                    'title': post_data.get('title'),
                    'author': post_data.get('author'),
                    'score': post_data.get('score'),
                    'upvote_ratio': post_data.get('upvote_ratio'),
                    'num_comments': post_data.get('num_comments'),
                    'url': post_url,
                    'created_utc': post_data.get('created_utc'),
                }
                # Check if post exists
                conn = db.sqlite3.connect(db.DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT json_data FROM posts WHERE post_id = ?", (post_id,))
                row = cursor.fetchone()
                conn.close()
                if row is None:
                    # New post
                    db.store_or_update_post(store_data, api_data)
                    db.update_post_status(post_id, "new", api_data, {
                        'score': store_data['score'],
                        'num_comments': store_data['num_comments'],
                        'upvote_ratio': store_data['upvote_ratio']
                    })
                    print(f"  [{i}/25] ✓ New: {title} ({store_data['score']} pts)")
                    new_count += 1
                else:
                    old_json = row[0]
                    if json.dumps(api_data, sort_keys=True) == old_json:
                        db.update_post_status(post_id, "stale")
                        print(f"  [{i}/25] ⊘ Stale: {title}")
                        stale_count += 1
                    else:
                        db.update_post_status(post_id, "refreshed", api_data, {
                            'score': store_data['score'],
                            'num_comments': store_data['num_comments'],
                            'upvote_ratio': store_data['upvote_ratio']
                        })
                        print(f"  [{i}/25] ↻ Refreshed: {title} ({store_data['score']} pts, {store_data['num_comments']} comments)")
                        refreshed_count += 1
            else:
                print(f"  [{i}/25] ✗ Invalid API response")
                error_count += 1
            time.sleep(2)
        except Exception as e:
            print(f"  [{i}/25] ✗ Error: {str(e)[:50]}")
            error_count += 1
            time.sleep(2)

    # Step 3: Process unprocessed posts
    unprocessed = db.get_unprocessed_posts(subreddit)
    total_unprocessed = len(unprocessed)
    for idx, (post_id, old_json) in enumerate(unprocessed, 1):
        db.update_progress(
            subreddit,
            "collecting",
            int(idx/total_unprocessed*100) if total_unprocessed else 100,
            0,
            subphase="unprocessed",
            current=idx,
            total=total_unprocessed
        )
        # Fetch latest JSON
        # Try to reconstruct the post URL from DB if needed (not shown here)
        # We'll assume we can get the permalink from the DB if needed
        # For now, skip if we can't reconstruct
        try:
            # Get permalink from DB
            conn = db.sqlite3.connect(db.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM posts WHERE post_id = ?", (post_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                continue
            post_url = row[0]
            api_url = post_url.rstrip('/') + '.json'
            api_response = requests.get(api_url, headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
            api_response.raise_for_status()
            api_data = api_response.json()
            if isinstance(api_data, list) and len(api_data) > 0:
                post_data = api_data[0]['data']['children'][0]['data']
                store_data = {
                    'id': post_id,
                    'subreddit': subreddit,
                    'title': post_data.get('title'),
                    'author': post_data.get('author'),
                    'score': post_data.get('score'),
                    'upvote_ratio': post_data.get('upvote_ratio'),
                    'num_comments': post_data.get('num_comments'),
                    'url': post_url,
                    'created_utc': post_data.get('created_utc'),
                }
                if json.dumps(api_data, sort_keys=True) == old_json:
                    db.update_post_status(post_id, "stale")
                    print(f"  [U{idx}] ⊘ Stale: {store_data['title']}")
                else:
                    db.update_post_status(post_id, "refreshed", api_data, {
                        'score': store_data['score'],
                        'num_comments': store_data['num_comments'],
                        'upvote_ratio': store_data['upvote_ratio']
                    })
                    print(f"  [U{idx}] ↻ Refreshed: {store_data['title']} ({store_data['score']} pts, {store_data['num_comments']} comments)")
            else:
                print(f"  [U{idx}] ✗ Invalid API response for unprocessed post")
            time.sleep(2)
        except Exception as e:
            print(f"  [U{idx}] ✗ Error: {str(e)[:50]}")
            time.sleep(2)

    # Mark collecting phase as done
    db.update_progress(subreddit, "collecting", 100, 0, subphase="unprocessed", current=total_unprocessed, total=total_unprocessed)

    print(f"\n  Summary: {new_count} new, {refreshed_count} refreshed, {stale_count} stale, {error_count} errors")
    print()

# Final stats
if target_subreddit:
    # Per-subreddit stats
    sr_count = db.get_post_count(target_subreddit)
    print("=" * 80)
    print(f"COLLECTION COMPLETE - r/{target_subreddit}")
    print("=" * 80)
    print(f"✓ Posts for r/{target_subreddit}: {sr_count}\n")
else:
    total_posts = db.get_post_count()
    print("=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print(f"✓ Total posts in database: {total_posts}\n")


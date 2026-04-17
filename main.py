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
    
    # Update progress: collecting phase starting
    db.update_progress(subreddit, "collecting", 0, 0)
    
    # Fetch RSS feed
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
    
    # Process posts (25 limit from RSS)
    new_count = 0
    refreshed_count = 0
    unchanged_count = 0
    error_count = 0
    
    for i, entry in enumerate(feed.entries[:25], 1):
        post_url = entry.link
        title = entry.title[:60] + "..." if len(entry.title) > 60 else entry.title
        
        # Extract post ID from URL
        post_id = post_url.split('/comments/')[1].split('/')[0] if '/comments/' in post_url else None
        
        if not post_id:
            print(f"  [{i}/25] ✗ Could not extract post ID")
            error_count += 1
            continue
        
        # Fetch JSON API data
        api_url = post_url.rstrip('/') + '.json'
        try:
            api_response = requests.get(api_url, headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
            api_response.raise_for_status()
            api_data = api_response.json()
            
            # Extract post data
            if isinstance(api_data, list) and len(api_data) > 0:
                post_data = api_data[0]['data']['children'][0]['data']
                
                # Prepare storage data
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
                
                # Store or update in database
                result = db.store_or_update_post(store_data, api_data)
                
                # Update progress
                pct = int((i / 25) * 100)
                db.update_progress(subreddit, "collecting", pct, i)
                
                if result == "new":
                    print(f"  [{i}/25] ✓ New: {title} ({store_data['score']} pts)")
                    new_count += 1
                elif result == "refreshed":
                    print(f"  [{i}/25] ↻ Refreshed: {title} ({store_data['score']} pts, {store_data['num_comments']} comments)")
                    refreshed_count += 1
                elif result == "unchanged":
                    print(f"  [{i}/25] ⊘ Unchanged: {title}")
                    unchanged_count += 1
                else:
                    print(f"  [{i}/25] ✗ Failed to store")
                    error_count += 1
            else:
                print(f"  [{i}/25] ✗ Invalid API response")
                error_count += 1
                
        except Exception as e:
            print(f"  [{i}/25] ✗ Error: {str(e)[:50]}")
            error_count += 1
    
    # Summary
    print(f"\n  Summary: {new_count} new, {refreshed_count} refreshed, {unchanged_count} unchanged, {error_count} errors")
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


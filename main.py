"""
Main Reddit Collector — fetch the top N hot posts per subreddit and store in database.

Uses Playwright headless Chromium to bypass Reddit's bot protection.
Each run fully replaces all posts for the subreddit with the current hot top N.
"""

import config
import db
import reddit_utils
import json
import sys
import time
from playwright.sync_api import sync_playwright


def browser_fetch_json(page, url):
    """Execute fetch() inside the browser context and return parsed JSON."""
    return page.evaluate(
        """async (url) => {
            const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
            if (!res.ok) throw new Error('HTTP ' + res.status + ' for ' + url);
            return res.json();
        }""",
        url,
    )


def collect_subreddit(page, subreddit):
    """
    Fetch the top N hot posts with full comments for a subreddit.

    Returns a list of (post_id, post_data_dict, stripped_listing_dict).
    """
    limit = config.POSTS_PER_SUBREDDIT

    # Load the subreddit page first to establish session cookies
    page.goto(
        f"https://www.reddit.com/r/{subreddit}/hot/",
        wait_until="domcontentloaded",
    )
    time.sleep(2)

    hot_url = config.REDDIT_HOT_URL.format(subreddit=subreddit, limit=limit)
    hot_data = browser_fetch_json(page, hot_url)
    posts = hot_data["data"]["children"][:limit]

    results = []
    for i, wrapper in enumerate(posts, 1):
        post_data = wrapper["data"]
        post_id = post_data["id"]
        title = post_data.get("title", post_id)[:60]

        post_url = config.REDDIT_POST_URL.format(subreddit=subreddit, post_id=post_id)
        try:
            raw = browser_fetch_json(page, post_url)
            stripped = reddit_utils.strip_listing(raw)
            results.append((post_id, post_data, stripped))
            print(f"  [{i}/{limit}] ✓ {title}")
        except Exception as e:
            print(f"  [{i}/{limit}] ✗ {title} — {e}")

        if i < limit:
            time.sleep(config.DELAY_SECONDS)

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

db.init_db()
db.init_progress()

# Optional --subreddit override
if len(sys.argv) > 2 and sys.argv[1] == "--subreddit":
    subreddits_to_process = [sys.argv[2]]
else:
    subreddits_json = db.get_setting("subreddits", json.dumps(config.SUBREDDITS))
    subreddits_to_process = json.loads(subreddits_json)

print("=" * 80)
print("REDDIT HOT COLLECTOR")
print("=" * 80)
print(f"Subreddits  : {', '.join(subreddits_to_process)}")
print(f"Posts/sub   : {config.POSTS_PER_SUBREDDIT}")
print()

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()

    for subreddit in subreddits_to_process:
        print(f"{'=' * 80}")
        print(f"r/{subreddit}")
        print(f"{'=' * 80}")
        db.update_progress(subreddit, "collecting", 0, 0)

        try:
            results = collect_subreddit(page, subreddit)
        except Exception as e:
            print(f"  ✗ Failed to collect r/{subreddit}: {e}\n")
            continue

        db.replace_posts(subreddit, results)
        db.update_progress(subreddit, "ready", 100, len(results))
        print(f"\n  {len(results)} posts stored (replaced)\n")

    browser.close()

print("=" * 80)
print(f"DONE  —  {db.get_post_count()} post(s) in database")
print("=" * 80)

"""
Run full pipeline: per-subreddit sequential processing
For each subreddit: collect → summarize → next
Then: digest display all at end
"""

import subprocess
import sys
import config
import time

print("=" * 80)
print("REDDIT LLM PIPELINE - SEQUENTIAL PER-SUBREDDIT PROCESSING")
print("=" * 80)
print(f"Subreddits: {', '.join(config.SUBREDDITS)}")
print()

total_start = time.time()

# Process each subreddit sequentially
for subreddit in config.SUBREDDITS:
    print("\n" + "=" * 80)
    print(f"SUBREDDIT: r/{subreddit}")
    print("=" * 80 + "\n")
    
    sr_start = time.time()
    
    # COLLECT
    print(f"[1/2] Collecting posts from r/{subreddit}...")
    print("-" * 80)
    try:
        result = subprocess.run([sys.executable, "main.py", "--subreddit", subreddit], check=True)
        if result.returncode != 0:
            print(f"\n✗ Error collecting from r/{subreddit}")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error collecting from r/{subreddit}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n✗ main.py not found")
        sys.exit(1)
    
    collect_time = time.time() - sr_start
    
    # SUMMARIZE
    print(f"\n[2/2] Summarizing top 5 posts from r/{subreddit}...")
    print("-" * 80)
    try:
        result = subprocess.run([sys.executable, "summarize.py", "--subreddit", subreddit], check=True)
        if result.returncode != 0:
            print(f"\n✗ Error summarizing r/{subreddit}")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error summarizing r/{subreddit}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n✗ summarize.py not found")
        sys.exit(1)
    
    sr_total = time.time() - sr_start
    summarize_time = sr_total - collect_time
    
    print(f"\n✓ r/{subreddit} complete (collected: {collect_time:.1f}s, summarized: {summarize_time:.1f}s)")

# DIGEST - after all subreddits
print("\n" + "=" * 80)
print("FINAL STEP: Displaying digest")
print("=" * 80 + "\n")

try:
    result = subprocess.run([sys.executable, "digest.py"], check=True)
    if result.returncode != 0:
        print(f"\n✗ Error displaying digest")
        sys.exit(1)
except subprocess.CalledProcessError as e:
    print(f"\n✗ Error displaying digest: {e}")
    sys.exit(1)
except FileNotFoundError:
    print(f"\n✗ digest.py not found")
    sys.exit(1)

total_time = time.time() - total_start
print("\n" + "=" * 80)
print("✓ PIPELINE COMPLETE")
print(f"Total time: {total_time:.1f}s ({total_time/60:.1f}m)")
print("=" * 80)

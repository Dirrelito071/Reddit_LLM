"""
Run full pipeline: collect → summarize → display
"""

import subprocess
import sys

print("=" * 80)
print("REDDIT LLM PIPELINE - COLLECT → SUMMARIZE → DISPLAY")
print("=" * 80)
print()

scripts = [
    ("main.py", "Collecting posts from subreddits..."),
    ("summarize.py", "Summarizing top 5 posts per subreddit..."),
    ("digest.py", "Displaying feed..."),
]

for script, description in scripts:
    print(f"\n{'=' * 80}")
    print(f"STEP: {description}")
    print(f"{'=' * 80}\n")
    
    try:
        result = subprocess.run([sys.executable, script], check=True)
        if result.returncode != 0:
            print(f"\n✗ Error running {script}")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error running {script}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n✗ Script not found: {script}")
        sys.exit(1)

print("\n" + "=" * 80)
print("✓ PIPELINE COMPLETE")
print("=" * 80)

"""
Configuration for Reddit LLM system.
"""

import os

# Subreddits to monitor
SUBREDDITS = [
    "DigitalAudioPlayer",
    "longboarding",
]

# Reddit API endpoints — fetched via Playwright browser session
REDDIT_HOT_URL = "https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}&raw_json=1"
REDDIT_POST_URL = "https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit=500&depth=10&raw_json=1"

# How many hot posts to collect and keep per subreddit
POSTS_PER_SUBREDDIT = 5

# Seconds to wait between post fetches (be polite to Reddit)
DELAY_SECONDS = 2

# LLM settings
# Use environment variable OLLAMA_URL if set, otherwise use host.docker.internal (llama-server on same host)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/v1/chat/completions")
MODEL = "qwen3-8b"
LLM_TIMEOUT = 600
LLM_TEMPERATURE = 0.2

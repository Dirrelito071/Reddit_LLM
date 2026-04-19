"""
Configuration for Reddit LLM system.
"""

import os

# Subreddits to monitor
SUBREDDITS = [
    "DigitalAudioPlayer",
    "longboarding",
]

# Reddit RSS settings
REDDIT_RSS_URL = "https://www.reddit.com/r/{subreddit}/new.rss"
REQUEST_TIMEOUT = 10
USER_AGENT = "RedditLLM/1.0"

# LLM settings
# Use environment variable OLLAMA_URL if set, otherwise use MacBook Pro's hostname
# The Ollama server runs on Martins-MacBook-Pro.local:11434
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://Martins-MacBook-Pro.local:11434/api/generate")
MODEL = "gemma3:12b"
LLM_TIMEOUT = 120
LLM_TEMPERATURE = 0.2

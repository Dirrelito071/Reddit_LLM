"""
Configuration for Reddit LLM system.
"""

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
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:7b-instruct"
LLM_TIMEOUT = 120
LLM_TEMPERATURE = 0.2

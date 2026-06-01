"""
reddit_utils.py

Field-stripping helpers for Reddit API responses.
Keeps only the fields useful for LLM summarization (~82% token reduction).
"""

POST_KEEP = {
    "id", "title", "selftext", "author", "score", "ups", "upvote_ratio",
    "url", "permalink", "num_comments", "created_utc", "subreddit",
    "is_self", "is_video", "domain",
}

COMMENT_KEEP = {
    "id", "body", "author", "score", "depth", "parent_id",
    "created_utc", "is_submitter", "permalink", "replies",
}


def strip_post(post: dict) -> dict:
    return {k: v for k, v in post.items() if k in POST_KEEP}


def strip_comment(node: dict) -> dict:
    d = node.get("data", {})
    result = {k: v for k, v in d.items() if k in COMMENT_KEEP}
    replies = d.get("replies")
    if isinstance(replies, dict):
        children = replies.get("data", {}).get("children", [])
        result["replies"] = [
            strip_comment(c) for c in children if c.get("kind") == "t1"
        ]
    else:
        result["replies"] = []
    return result


def strip_listing(raw: list) -> dict:
    """Convert raw Reddit [post_listing, comment_listing] API response to stripped dict."""
    post = raw[0]["data"]["children"][0]["data"]
    comments_raw = raw[1]["data"]["children"]
    comments = [strip_comment(c) for c in comments_raw if c.get("kind") == "t1"]
    return {"post": strip_post(post), "comments": comments}

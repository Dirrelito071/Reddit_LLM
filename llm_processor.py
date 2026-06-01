"""
LLM Processor — Process Reddit posts through Ollama/llama-server
"""

import requests
import json
import sqlite3
import config

DB_PATH = "reddit_posts.db"


# The question to ask about each post (default, can be overridden)
QUESTION = (
    "What are the key insights from this post, the poster's intention, "
    "and the following discussion? Summarize it in 5 sentences."
)


def extract_post_context(api_data):
    """
    Return a compact context dict for LLM processing.

    Handles the stripped format {"post": {...}, "comments": [...]} written
    by main.py, as well as the legacy raw Reddit API list format for any
    posts collected by an older version.
    """
    try:
        # New stripped format: {"post": {...}, "comments": [...]}
        if isinstance(api_data, dict) and "post" in api_data:
            post = api_data["post"]
            top_comments = api_data.get("comments", [])[:10]
            return {
                "title": post.get("title"),
                "author": post.get("author"),
                "selftext": post.get("selftext"),
                "score": post.get("score"),
                "num_comments": post.get("num_comments"),
                "comments": [
                    {
                        "author": c.get("author"),
                        "body": c.get("body"),
                        "score": c.get("score"),
                    }
                    for c in top_comments
                ],
            }

        # Legacy raw Reddit API format: [post_listing, comment_listing]
        if isinstance(api_data, list) and len(api_data) >= 2:
            post = api_data[0]["data"]["children"][0]["data"]
            comments = api_data[1]["data"]["children"]
            top_comments = [c["data"] for c in comments if c.get("kind") == "t1"][:10]
            return {
                "title": post.get("title"),
                "author": post.get("author"),
                "selftext": post.get("selftext"),
                "score": post.get("score"),
                "num_comments": post.get("num_comments"),
                "comments": [
                    {
                        "author": c.get("author"),
                        "body": c.get("body"),
                        "score": c.get("score"),
                    }
                    for c in top_comments
                ],
            }

        return None
    except Exception as e:
        print(f"Error extracting post context: {e}")
        return None


def call_ollama(question, api_data):
    """
    Call Ollama/llama-server with the question and context data.
    Returns response text from LLM, or None if failed.
    """
    try:
        context_json = json.dumps(api_data, indent=2)
        full_prompt = f"Reddit post JSON:\n\n{context_json}\n\nQUESTION: {question}"

        import db
        model_name = db.get_llm_model()
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant. Respond briefly."},
                    {"role": "user", "content": full_prompt},
                ],
                "temperature": config.LLM_TEMPERATURE,
                "stream": False,
            },
            timeout=config.LLM_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        try:
            return result["choices"][0]["message"]["content"]
        except Exception as ex:
            print("[LLM DEBUG] Full API response:")
            print(json.dumps(result, indent=2))
            print(f"[LLM DEBUG] Extraction error: {ex}")
            return None
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


def process_post(post_id, custom_question=None):
    """
    Process a specific post through the LLM and store the summary.

    Returns:
        True               — successfully summarized
        False              — error during processing
        "already_summarized" — post already has a summary
        "not_found"        — post ID not in DB
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT post_id, title, status, json_data FROM posts WHERE post_id = ?",
            (post_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return "not_found"

        post_id_db, title, status, json_data = row

        if status == "summarized":
            conn.close()
            return "already_summarized"

        api_data = json.loads(json_data)
        context = extract_post_context(api_data)

        if not context:
            conn.close()
            return False

        question_to_use = custom_question if custom_question else QUESTION
        print(f"  LLM QUESTION: {question_to_use}")
        print(f"  Calling LLM for: {title[:60]}...")

        summary = call_ollama(question_to_use, context)
        if not summary:
            conn.close()
            return False

        import datetime, time
        now_local = datetime.datetime.fromtimestamp(time.time()).isoformat(
            sep=" ", timespec="seconds"
        )
        cursor.execute(
            "UPDATE posts SET summary = ?, status = 'summarized', updated_at = ? WHERE post_id = ?",
            (summary, now_local, post_id),
        )
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error processing post {post_id}: {e}")
        return False

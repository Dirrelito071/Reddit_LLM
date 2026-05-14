"""
LLM Processor - Process Reddit posts through Mistral 7B
"""

import requests
import json
import sqlite3
import config

DB_PATH = "reddit_posts.db"

_ctx_size_cache = None

def _get_ctx_size():
    global _ctx_size_cache
    if _ctx_size_cache is None:
        try:
            base = config.OLLAMA_URL.split("/v1")[0]
            r = requests.get(f"{base}/slots", timeout=5)
            slots = r.json()
            _ctx_size_cache = slots[0].get("n_ctx", 16896) if slots else 16896
        except Exception:
            _ctx_size_cache = 16896  # fallback
    return _ctx_size_cache

# The question to ask about each post (default, can be overridden)
QUESTION = """What are the key insights from this post, the poster's intention, and the following discussion? Summarize it in 5 sentences."""


def extract_post_context(api_data):
    """
    Return raw Reddit API JSON for LLM processing
    
    Args:
        api_data: Full Reddit JSON API payload [post_data, comments_data]
    
    Returns:
        Raw API data if valid, None otherwise
    """
    try:
        return api_data if isinstance(api_data, list) and len(api_data) > 0 else None
    except Exception as e:
        print(f"Error with API data: {e}")
        return None


def call_ollama(question, api_data):
    """
    Call Ollama with question and full JSON API data
    
    Args:
        question: The question to ask
        api_data: Full Reddit JSON API payload (complete, unfiltered)
    
    Returns:
        Response text from LLM, or None if failed
    """
    try:
        # Format JSON for LLM with question
        # Reserve ~2000 tokens for question + response, use the rest of the context window
        context_json = json.dumps(api_data, indent=2)
        max_chars = (_get_ctx_size() - 2000) * 4
        if len(context_json) > max_chars:
            context_json = context_json[:max_chars] + "\n... [truncated]"
        user_content = f"Reddit API JSON data:\n\n{context_json}\n\nQUESTION: {question}"
        
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": config.MODEL,
                "messages": [{"role": "user", "content": user_content}],
                "temperature": config.LLM_TEMPERATURE,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=config.LLM_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


def process_post(post_id, custom_question=None):
    """
    Process a specific post through LLM
    
    Args:
        post_id: Reddit post ID to process
        custom_question: Optional custom question (if None, uses default QUESTION)
    
    Returns:
        True - Successfully processed
        False - Error during processing
        "already_summarized" - Post already has summary
        "not_found" - Post doesn't exist in DB
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Fetch post from DB
        cursor.execute("""
            SELECT post_id, title, status, json_data 
            FROM posts 
            WHERE post_id = ?
        """, (post_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return "not_found"
        
        post_id_db, title, status, json_data = row
        
        # Check if already summarized
        if status == "summarized":
            conn.close()
            return "already_summarized"
        
        # Extract context
        api_data = json.loads(json_data)
        context = extract_post_context(api_data)
        
        if not context:
            conn.close()
            return False
        
        # Use custom question if provided, otherwise use default
        question_to_use = custom_question if custom_question else QUESTION

        # Log the question being used
        print(f"  LLM QUESTION: {question_to_use}")

        # Call LLM
        print(f"  Calling LLM for: {title[:60]}...")
        summary = call_ollama(question_to_use, context)
        
        if not summary:
            conn.close()
            return False
        
        # Update DB with local time for updated_at
        import datetime, time
        now_local = datetime.datetime.fromtimestamp(time.time()).isoformat(sep=' ', timespec='seconds')
        cursor.execute("""
            UPDATE posts 
            SET summary = ?, status = 'summarized', updated_at = ?
            WHERE post_id = ?
        """, (summary, now_local, post_id))
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error processing post {post_id}: {e}")
        return False

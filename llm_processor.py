"""
LLM Processor - Process Reddit posts through Mistral 7B
"""

import requests
import json
import sqlite3
import config

DB_PATH = "reddit_posts.db"

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
        context_json = json.dumps(api_data, indent=2)
        full_prompt = f"Reddit API JSON data:\n\n{context_json}\n\nQUESTION: {question}"
        
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": config.MODEL,
                "prompt": full_prompt,
                "temperature": config.LLM_TEMPERATURE,
                "stream": False,
            },
            timeout=config.LLM_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get('response', '')
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
        
        # Update DB
        cursor.execute("""
            UPDATE posts 
            SET summary = ?, status = 'summarized', updated_at = CURRENT_TIMESTAMP
            WHERE post_id = ?
        """, (summary, post_id))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error processing post {post_id}: {e}")
        return False

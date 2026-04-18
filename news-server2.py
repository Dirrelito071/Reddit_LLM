#!/usr/bin/env python3
"""
News Server with Pipeline Orchestration
HTTP server that runs collection/summarization pipeline and serves live progress dashboard
"""

import json
import logging
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import config
import db

# Configure logging to see output in Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

DB_PATH = "reddit_posts.db"
PORT = 8000


# Global flags and scheduling state
pipeline_running = False
last_run_time = None  # ISO string
next_run_time = None  # ISO string

# Scheduler: compute next 6-hour interval (UTC)
import datetime
def get_next_run_time(now=None):
    if now is None:
        now = datetime.datetime.now()
    # Fixed boundaries: 00:00, 06:00, 12:00, 18:00 (local time)
    boundaries = [0, 6, 12, 18]
    # Find the next boundary strictly after 'now'
    for h in boundaries:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate
    # If none found, it's after 18:00, so next is 00:00 next day
    return (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

# Background scheduler thread
def scheduler_loop():
    global pipeline_running, last_run_time, next_run_time
    while True:
        now = datetime.datetime.now()
        if next_run_time is None or now >= next_run_time:
            if not pipeline_running:
                # Start pipeline in background
                threading.Thread(target=run_pipeline, daemon=True).start()
                last_run_time = now.replace(microsecond=0).isoformat()
            # Compute next run
            next_run_time = get_next_run_time(now)
        # Sleep until next check (1 min)
        time.sleep(60)


class NewsHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Suppress default logging
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/":
            self.serve_file("news-digest.html", "text/html; charset=utf-8")
        elif path == "/api/status":
            self.serve_status()
        elif path == "/api/news":
            self.serve_news()
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/api/run":
            self.run_pipeline_handler()
        elif path == "/api/settings/subreddits":
            self.handle_subreddit_settings()
        elif path == "/api/settings/question":
            self.handle_question_settings()
        else:
            self.send_error(404)
    
    def serve_file(self, filename, content_type):
        """Serve a static file"""
        try:
            content = Path(filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, f"File not found: {filename}")
    
    def serve_status(self):
        """Return status for each subreddit + running flag, last/next run times"""
        status = {}
        try:
            progress = db.get_progress()
            subreddits = db.get_subreddits()
            for subreddit in subreddits:
                if subreddit in progress:
                    p = progress[subreddit]
                    phase = p["phase"]
                    subphase = p.get("subphase")
                    pct = p["pct"]
                    current = p.get("current", 0)
                    total = p.get("total", 0)
                    total_posts = p.get("total_posts", 0)
                    last_updated = p.get("last_updated")
                    if last_updated:
                        last_updated = last_updated + "Z" if not last_updated.endswith("Z") else last_updated
                    if phase == "collecting":
                        if subphase == "rss":
                            label = f"RSS {current}/{total}"
                        elif subphase == "unprocessed":
                            label = f"Unprocessed {current}/{total}"
                        else:
                            label = f"{current}/{total}"
                    elif phase == "summarizing":
                        label = f"Summarizing {current}/{total}"
                    elif phase == "ready":
                        label = f"{total_posts}/{total_posts}"
                    else:
                        label = "—"
                    status[subreddit] = {
                        "phase": phase,
                        "subphase": subphase,
                        "pct": pct,
                        "current": current,
                        "total": total,
                        "label": label,
                        "last_updated": last_updated
                    }
                else:
                    status[subreddit] = {
                        "phase": "idle",
                        "subphase": None,
                        "pct": 0,
                        "current": 0,
                        "total": 0,
                        "label": "—",
                        "last_updated": None
                    }
        except Exception as e:
            logger.error(f"Error querying status: {e}")
            subreddits = db.get_subreddits()
            status = {sr: {"phase": "error", "pct": 0, "label": "Error", "last_updated": None} for sr in subreddits}

        # Add running flag, subreddits list, LLM question, and schedule times
        subreddits = db.get_subreddits()
        llm_question = db.get_llm_question()
        response = {
            "running": pipeline_running,
            "subreddits": subreddits,
            "llm_question": llm_question,
            "status": status,
            "last_run_time": last_run_time,
            "next_run_time": next_run_time.isoformat() if next_run_time else None
        }
        self.send_json(response)
    
    def serve_news(self):
        """Return news posts grouped by subreddit"""
        news = {}
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            subreddits = db.get_subreddits()  # Load from DB (user settings or defaults)
            
            for subreddit in subreddits:
                # Get top 5 posts with summaries and engagement data, including updated_at
                cursor.execute("""
                    SELECT title, summary, url, COALESCE(score, 0), COALESCE(num_comments, 0), previous_score, updated_at
                    FROM posts
                    WHERE subreddit = ?
                    ORDER BY score DESC
                    LIMIT 5
                """, (subreddit,))
                posts = cursor.fetchall()
                news[subreddit] = [
                    {
                        "title": post[0],
                        "summary": post[1] if post[1] else "(no summary)",
                        "link": post[2],
                        "score": post[3],
                        "num_comments": post[4],
                        "previous_score": post[5],
                        "updated_at": post[6]
                    }
                    for post in posts
                ]
            
            conn.close()
        except Exception as e:
            logger.error(f"Error querying news: {e}")
            subreddits = db.get_subreddits()
            news = {sr: [] for sr in subreddits}
        
        self.send_json(news)
    
    def run_pipeline_handler(self):
        """Handle POST /api/run - start pipeline in background"""
        global pipeline_running
        
        if pipeline_running:
            self.send_json({"error": "Pipeline already running"})
            return
        
        # Start pipeline in background thread
        pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        pipeline_thread.start()
        
        self.send_json({"started": True})
    
    def handle_subreddit_settings(self):
        """Handle POST /api/settings/subreddits - update subreddit list"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            subreddits = data.get("subreddits", [])
            
            # Validate: at least 1 subreddit required
            if not subreddits or len(subreddits) == 0:
                self.send_json({"error": "At least 1 subreddit required"})
                return
            
            # Validate: all entries are strings
            if not all(isinstance(sr, str) and sr.strip() for sr in subreddits):
                self.send_json({"error": "Invalid subreddit names"})
                return
            
            # Store in database
            subreddits = [sr.strip() for sr in subreddits]
            if db.set_subreddits(subreddits):
                logger.info(f"Subreddits updated: {subreddits}")
                self.send_json({"success": True, "subreddits": subreddits})
            else:
                self.send_json({"error": "Failed to save subreddits"})
        except Exception as e:
            logger.error(f"Error handling subreddit settings: {e}")
            self.send_json({"error": str(e)})
    
    def handle_question_settings(self):
        """Handle POST /api/settings/question - update LLM question"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            question = data.get("question", "").strip()
            
            # Validate: question cannot be empty
            if not question:
                self.send_json({"error": "Question cannot be empty"})
                return
            
            # Store in database
            if db.set_llm_question(question):
                logger.info(f"LLM question updated")
                self.send_json({"success": True, "question": question})
            else:
                self.send_json({"error": "Failed to save question"})
        except Exception as e:
            logger.error(f"Error handling question settings: {e}")
            self.send_json({"error": str(e)})
    
    def send_json(self, data):
        """Send JSON response"""
        try:
            content = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error(f"Error sending JSON: {e}")
            self.send_error(500)


def run_pipeline():
    """Run full pipeline: collect + summarize for each subreddit"""
    global pipeline_running
    
    pipeline_running = True
    logger.info("\n" + "=" * 80)
    logger.info("PIPELINE STARTED - Sequential per-subreddit processing")
    logger.info("=" * 80 + "\n")
    
    try:
        # Reset progress table
        db.reset_progress()
        
        # Load subreddits from DB (user settings or defaults)
        subreddits = db.get_subreddits()
        
        # Process each subreddit sequentially
        for subreddit in subreddits:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"SUBREDDIT: r/{subreddit}")
            logger.info(f"{'=' * 80}\n")
            
            sr_start = time.time()
            
            # COLLECT
            logger.info(f"[1/2] Collecting posts from r/{subreddit}...")
            logger.info("-" * 80)
            try:
                result = subprocess.run([sys.executable, "main.py", "--subreddit", subreddit], check=True)
                if result.returncode != 0:
                    logger.error(f"\nError collecting from r/{subreddit}")
            except subprocess.CalledProcessError as e:
                logger.error(f"\nError collecting from r/{subreddit}: {e}")
            except FileNotFoundError:
                logger.error(f"\nmain.py not found")
            
            collect_time = time.time() - sr_start
            
            # SUMMARIZE
            logger.info(f"\n[2/2] Summarizing top 5 posts from r/{subreddit}...")
            logger.info("-" * 80)
            try:
                result = subprocess.run([sys.executable, "summarize.py", "--subreddit", subreddit], check=True)
                if result.returncode != 0:
                    logger.error(f"\nError summarizing r/{subreddit}")
            except subprocess.CalledProcessError as e:
                logger.error(f"\nError summarizing r/{subreddit}: {e}")
            except FileNotFoundError:
                logger.error(f"\nsummarize.py not found")
            
            sr_total = time.time() - sr_start
            summarize_time = sr_total - collect_time
            
            logger.info(f"\nr/{subreddit} complete (collected: {collect_time:.1f}s, summarized: {summarize_time:.1f}s)")
        
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80 + "\n")
    
    except Exception as e:
        logger.error(f"\nPipeline error: {e}\n")
    
    finally:
        pipeline_running = False


if __name__ == "__main__":
    # Initialize database
    db.init_db()
    db.init_progress()

    # Set up scheduling state (no global statement needed at module level)
    now = datetime.datetime.now()
    last_run_time = None
    next_run_time = get_next_run_time(now)

    # Start scheduler thread
    threading.Thread(target=scheduler_loop, daemon=True).start()

    logger.info("=" * 80)
    logger.info("NEWS DIGEST SERVER - Reddit Edition with Pipeline Orchestration")
    logger.info("=" * 80)
    logger.info(f"Starting server on http://localhost:{PORT}")
    logger.info(f"Subreddits: {', '.join(config.SUBREDDITS)}")
    logger.info("\nOpen your browser and navigate to:")
    logger.info(f"  http://localhost:{PORT}")
    logger.info("\nClick 'Start Pipeline' button to begin collection and summarization")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 80 + "\n")

    try:
        with HTTPServer(("0.0.0.0", PORT), NewsHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n\nServer stopped.")

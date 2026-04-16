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

# Global flag for pipeline execution
pipeline_running = False


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
        """Return status for each subreddit + running flag"""
        status = {}
        
        try:
            progress = db.get_progress()
            
            for subreddit in config.SUBREDDITS:
                if subreddit in progress:
                    p = progress[subreddit]
                    phase = p["phase"]
                    pct = p["pct"]
                    total = p["total_posts"]
                    last_updated = p.get("last_updated")
                    
                    # Convert UTC timestamp to ISO format with Z suffix for JavaScript
                    if last_updated:
                        last_updated = last_updated + "Z" if not last_updated.endswith("Z") else last_updated
                    
                    if phase == "collecting":
                        current = int((pct / 100) * 25) if pct > 0 else 0
                        label = f"{current}/25"
                    elif phase == "summarizing":
                        current = int((pct / 100) * total) if pct > 0 else 0
                        label = f"{current}/{total}"
                    elif phase == "ready":
                        label = f"{total}/{total}"
                    else:
                        label = "—"
                    
                    status[subreddit] = {
                        "phase": phase,
                        "pct": pct,
                        "label": label,
                        "last_updated": last_updated
                    }
                else:
                    status[subreddit] = {
                        "phase": "idle",
                        "pct": 0,
                        "label": "—",
                        "last_updated": None
                    }
        except Exception as e:
            logger.error(f"Error querying status: {e}")
            status = {sr: {"phase": "error", "pct": 0, "label": "Error", "last_updated": None} for sr in config.SUBREDDITS}
        
        # Add running flag
        response = {"running": pipeline_running, "subreddits": status}
        self.send_json(response)
    
    def serve_news(self):
        """Return news posts grouped by subreddit"""
        news = {}
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            for subreddit in config.SUBREDDITS:
                # Get top 5 posts with summaries and engagement data
                cursor.execute("""
                    SELECT title, summary, url, COALESCE(score, 0), COALESCE(num_comments, 0), previous_score
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
                        "previous_score": post[5]
                    }
                    for post in posts
                ]
            
            conn.close()
        except Exception as e:
            logger.error(f"Error querying news: {e}")
            news = {sr: [] for sr in config.SUBREDDITS}
        
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
        
        # Process each subreddit sequentially
        for subreddit in config.SUBREDDITS:
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

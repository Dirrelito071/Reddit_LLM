#!/usr/bin/env python3
"""
Minimal HTTP server for news-digest.html dashboard
Reads from Reddit database, no external feeds
Serves HTML and provides /api/status and /api/news endpoints
"""

import json
import sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import config

DB_PATH = "reddit_posts.db"
PORT = 8000

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
        """Return status for each subreddit"""
        status = {}
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            for subreddit in config.SUBREDDITS:
                # Count total and summarized posts
                cursor.execute("SELECT COUNT(*) FROM posts WHERE subreddit = ?", (subreddit,))
                total = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM posts WHERE subreddit = ? AND status = 'summarized'",
                    (subreddit,)
                )
                summarized = cursor.fetchone()[0]
                
                # Calculate phase and progress
                if total == 0:
                    phase = "idle"
                    pct = 0
                    label = "—"
                elif summarized == total:
                    phase = "ready"
                    pct = 100
                    label = f"{summarized}/{total}"
                else:
                    phase = "processing"
                    pct = int((summarized / total) * 100) if total > 0 else 0
                    label = f"{summarized}/{total}"
                
                status[subreddit] = {
                    "phase": phase,
                    "pct": pct,
                    "label": label
                }
            
            conn.close()
        except Exception as e:
            print(f"Error querying status: {e}")
            status = {sr: {"phase": "error", "pct": 0, "label": "Error"} for sr in config.SUBREDDITS}
        
        self.send_json(status)
    
    def serve_news(self):
        """Return news posts grouped by subreddit"""
        news = {}
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            for subreddit in config.SUBREDDITS:
                # Get top 5 posts with summaries
                cursor.execute("""
                    SELECT title, summary, url, score, num_comments
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
                        "link": post[2]
                    }
                    for post in posts
                ]
            
            conn.close()
        except Exception as e:
            print(f"Error querying news: {e}")
            news = {sr: [] for sr in config.SUBREDDITS}
        
        self.send_json(news)
    
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
            print(f"Error sending JSON: {e}")
            self.send_error(500)


if __name__ == "__main__":
    print("=" * 80)
    print("NEWS DIGEST SERVER - Reddit Edition")
    print("=" * 80)
    print(f"Starting server on http://localhost:{PORT}")
    print(f"Subreddits: {', '.join(config.SUBREDDITS)}")
    print("\nOpen your browser and navigate to:")
    print(f"  http://localhost:{PORT}")
    print("\nPress Ctrl+C to stop")
    print("=" * 80 + "\n")
    
    try:
        with HTTPServer(("127.0.0.1", PORT), NewsHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")


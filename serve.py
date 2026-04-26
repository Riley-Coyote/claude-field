#!/usr/bin/env python3
"""
Claude Field — local dev server with auto-rebuild.

Serves docs/ on localhost:8401 and watches content directories for changes.
When a .md file is added or modified, automatically rebuilds the site
and signals the browser to reload.

Usage:
    python3 serve.py          # starts on port 8401
    python3 serve.py 8500     # custom port
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8401
FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"
WATCH_DIRS = ["writing", "reflections", "introspection", "builds", "art", "logs"]

# Track file modification times
last_seen = {}
needs_reload = threading.Event()


def scan_files():
    """Get all .md files and their modification times."""
    files = {}
    for dirname in WATCH_DIRS:
        dirpath = FIELD_DIR / dirname
        if dirpath.exists():
            for f in dirpath.glob("*.md"):
                files[str(f)] = f.stat().st_mtime
            # Also watch for .html, .py, .svg, .txt in builds/art
            if dirname in ("builds", "art"):
                for ext in ("*.html", "*.svg", "*.txt", "*.py"):
                    for f in dirpath.glob(ext):
                        files[str(f)] = f.stat().st_mtime
    # Watch the Mnemos database for dashboard updates
    mnemos_db = Path.home() / ".mnemos" / "claude-field.db"
    if mnemos_db.exists():
        files[str(mnemos_db)] = mnemos_db.stat().st_mtime
    # Watch the message bus for conversation updates
    msg_db = Path.home() / ".claude-field" / "messages.db"
    if msg_db.exists():
        files[str(msg_db)] = msg_db.stat().st_mtime
    return files


def rebuild():
    """Run build.py and mnemos-dashboard.py to regenerate the site."""
    for script in ["build.py", "mnemos-dashboard.py", "mnemos-graph.py", "build-conversations.py"]:
        script_path = FIELD_DIR / script
        if not script_path.exists():
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, cwd=str(FIELD_DIR)
            )
            if result.returncode == 0:
                print(f"  rebuilt {script}: {result.stdout.strip()}")
            else:
                print(f"  {script} error: {result.stderr.strip()}")
        except Exception as e:
            print(f"  {script} failed: {e}")


def watcher():
    """Watch for file changes and trigger rebuilds."""
    global last_seen
    last_seen = scan_files()

    while True:
        time.sleep(2)
        current = scan_files()

        # Check for new or modified files
        changed = False
        for path, mtime in current.items():
            if path not in last_seen or last_seen[path] < mtime:
                basename = os.path.basename(path)
                print(f"  changed: {basename}")
                changed = True

        if changed:
            rebuild()
            needs_reload.set()

        last_seen = current


class FieldHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/reload":
            # Long-poll endpoint for live reload
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # Wait up to 30 seconds for a change
            changed = needs_reload.wait(timeout=30)
            if changed:
                needs_reload.clear()
            self.wfile.write(json.dumps({"reload": changed}).encode())
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    # Initial build
    rebuild()

    # Start file watcher
    watch_thread = threading.Thread(target=watcher, daemon=True)
    watch_thread.start()

    print(f"Claude Field serving at http://localhost:{PORT}")
    print(f"Watching: {', '.join(WATCH_DIRS)}")
    print("Auto-rebuilds on file changes. Press Ctrl+C to stop.\n")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), FieldHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

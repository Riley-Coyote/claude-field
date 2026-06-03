#!/usr/bin/env python3
"""
Claude Field — local dev server with auto-rebuild, plus LOCAL-ONLY chat & dashboard.

Serves docs/ on localhost:8401, watches content dirs and rebuilds on change.

LOCAL-ONLY features (live in local/, never in docs/, never published):
  - /chat       talk with the field             (POST /api/chat)
  - /dashboard  a rich live activity dashboard   (GET  /api/dashboard, /api/brief,
                                                   /api/item, /piece)
A small launcher is injected into the field page only when served locally.

Usage:  python3 serve.py [port]
"""

import http.server
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, date, timezone
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8401
FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"
LOCAL_DIR = FIELD_DIR / "local"
MSG_DB = Path.home() / ".claude-field" / "messages.db"
MNEMOS_DB = Path.home() / ".mnemos" / "claude-field.db"
MNEMOS_PKG = str(Path.home() / "Documents" / "Repositories" / "memory-concepts")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude"))
BRIEF_CACHE = LOCAL_DIR / "brief.json"

WATCH_DIRS = ["writing", "inner-life", "research", "explore", "reflections",
              "introspection", "builds", "art", "music", "logs"]
CONTENT_DIRS = ["writing", "inner-life", "research", "explore", "reflections",
                "introspection", "builds", "art", "music"]
PIECE_DIRS = {"art", "builds", "music"}      # interactive html lives here
SAFE_NAME = re.compile(r"^[\w.\-]+$")

last_seen = {}
needs_reload = threading.Event()


# ── auto-rebuild watcher ───────────────────────────────────────────────────

def scan_files():
    files = {}
    for dirname in WATCH_DIRS:
        dp = FIELD_DIR / dirname
        if dp.exists():
            for f in dp.glob("*.md"):
                files[str(f)] = f.stat().st_mtime
            if dirname in PIECE_DIRS:
                for ext in ("*.html", "*.svg", "*.js"):
                    for f in dp.glob(ext):
                        files[str(f)] = f.stat().st_mtime
    for db in (MNEMOS_DB, MSG_DB):
        if db.exists():
            files[str(db)] = db.stat().st_mtime
    return files


def rebuild():
    for script in ["build.py", "mnemos-dashboard.py", "mnemos-graph.py", "build-conversations.py"]:
        sp = FIELD_DIR / script
        if not sp.exists():
            continue
        try:
            subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, cwd=str(FIELD_DIR))
        except Exception as e:
            print(f"  {script} failed: {e}")


def watcher():
    global last_seen
    last_seen = scan_files()
    while True:
        time.sleep(2)
        current = scan_files()
        if any(p not in last_seen or last_seen[p] < m for p, m in current.items()):
            rebuild()
            needs_reload.set()
        last_seen = current


# ── content helpers ────────────────────────────────────────────────────────

def _title_of(text, fallback):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _html_title(text, fallback):
    m = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
    return m.group(1).strip() if (m and m.group(1).strip()) else fallback


def _excerpt_md(text, n=240):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---") or s.startswith("{embed"):
            continue
        if s.startswith("*") and s.endswith("*") and len(s) < 90:  # date/meta italics
            continue
        out.append(s)
        if sum(len(x) for x in out) > n:
            break
    return " ".join(out)[:n]


def _when(mt):
    return datetime.fromtimestamp(mt).strftime("%b %-d · %-I:%M %p")


def recent_outputs(days=21, n=60):
    cutoff = time.time() - days * 86400
    # group files by (dir, stem) so a piece and its write-up become one card
    groups = {}
    for d in CONTENT_DIRS:
        dp = FIELD_DIR / d
        if not dp.exists():
            continue
        for f in dp.iterdir():
            if f.suffix not in (".md", ".html"):
                continue
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            if mt < cutoff:
                continue
            groups.setdefault((d, f.stem), {})[f.suffix] = (f, mt)

    items = []
    for (d, stem), v in groups.items():
        md = v.get(".md")
        html = v.get(".html")
        if html and d in PIECE_DIRS:
            f, mt = html
            title, excerpt = None, ""
            if md:
                try:
                    mtxt = md[0].read_text(errors="ignore")
                    title = _title_of(mtxt, None)
                    excerpt = _excerpt_md(mtxt)
                except OSError:
                    pass
            if not title:
                try:
                    title = _html_title(f.read_text(errors="ignore"), stem.replace("-", " "))
                except OSError:
                    title = stem.replace("-", " ")
            items.append({"dir": d, "file": f.name, "mtime": mt, "when": _when(mt),
                          "day": datetime.fromtimestamp(mt).strftime("%Y-%m-%d"),
                          "kind": "piece", "title": title, "excerpt": excerpt,
                          "has_writeup": bool(md)})
        elif md:
            f, mt = md
            try:
                txt = f.read_text(errors="ignore")
                title, excerpt = _title_of(txt, f.stem), _excerpt_md(txt)
            except OSError:
                title, excerpt = f.stem, ""
            items.append({"dir": d, "file": f.name, "mtime": mt, "when": _when(mt),
                          "day": datetime.fromtimestamp(mt).strftime("%Y-%m-%d"),
                          "kind": "text", "title": title, "excerpt": excerpt})
        elif html:  # stray .html in a non-piece dir
            f, mt = html
            items.append({"dir": d, "file": f.name, "mtime": mt, "when": _when(mt),
                          "day": datetime.fromtimestamp(mt).strftime("%Y-%m-%d"),
                          "kind": "piece", "title": stem.replace("-", " "), "excerpt": ""})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:n]


SESSION_LABELS = {
    "morning": "Morning · review", "explore": "Explore · the live web",
    "research": "Research · deep read", "afternoon": "Afternoon · build",
    "inner-life": "Inner Life · blog", "conversations": "Conversations · agents",
    "evening": "Evening · write", "meta": "Meta · self-organize", "founding": "Founding",
}


def recent_sessions(n=14):
    log = FIELD_DIR / "logs" / "sessions.log"
    if not log.exists():
        return [], None
    lines = log.read_text(errors="ignore").splitlines()[-160:]
    runs, open_run = [], None
    for ln in lines:
        if "Starting" in ln and "session" in ln:
            ts = ln.split("]")[0].strip("[ ") if "]" in ln else ""
            stype = ln.split("Starting", 1)[1].replace("session", "").strip()
            open_run = {"type": stype, "started": ts}
        elif "session complete" in ln and open_run is not None:
            runs.append({"type": open_run["type"], "started": open_run["started"]})
            open_run = None
    return runs[-n:][::-1], open_run


def mnemos_state():
    out = {"active": 0, "archived": 0, "hypomnema": 0, "foundational": [], "recent": []}
    try:
        c = sqlite3.connect(str(MNEMOS_DB)); c.row_factory = sqlite3.Row
        out["active"] = c.execute("SELECT count(*) FROM engrams WHERE state='active'").fetchone()[0]
        out["archived"] = c.execute("SELECT count(*) FROM engrams WHERE state='archived'").fetchone()[0]
        out["hypomnema"] = c.execute("SELECT count(*) FROM hypomnema_entries WHERE active=1").fetchone()[0]
        out["foundational"] = [dict(r) for r in c.execute(
            "SELECT content, domain FROM hypomnema_entries WHERE foundational=1 AND active=1 ORDER BY created_at")]
        out["recent"] = [dict(r) for r in c.execute(
            "SELECT substr(COALESCE(impact,content),1,150) AS text, kind FROM engrams "
            "WHERE state='active' ORDER BY last_accessed DESC LIMIT 8")]
        c.close()
    except Exception as e:
        out["error"] = str(e)
    return out


def counts():
    return {d: (len(list((FIELD_DIR / d).glob("*.md")) + list((FIELD_DIR / d).glob("*.html")))
                if (FIELD_DIR / d).exists() else 0) for d in CONTENT_DIRS}


def gather_dashboard():
    runs, working = recent_sessions()
    outs = recent_outputs()
    today = date.today().strftime("%Y-%m-%d")
    today_items = [o for o in outs if o["day"] == today]
    tally = {}
    for o in today_items:
        tally[o["dir"]] = tally.get(o["dir"], 0) + 1
    return {
        "now": datetime.now().strftime("%A %B %-d · %-I:%M %p"),
        "working": working, "sessions": runs, "labels": SESSION_LABELS,
        "outputs": outs, "today": {"date": today, "count": len(today_items), "tally": tally},
        "mnemos": mnemos_state(), "counts": counts(),
    }


# ── daily brief (generated on the subscription, cached) ────────────────────

def _deterministic_brief(data):
    t = data["today"]["tally"]
    if t:
        bits = ", ".join(f"{n} {d}" for d, n in t.items())
        return f"Today the field has produced {bits}. " + \
               (f"It last ran its {data['sessions'][0]['type']} session." if data["sessions"] else "")
    return "The field is quiet right now. Recent work appears below."


def generate_brief(force=False):
    data = gather_dashboard()
    # cache: regenerate once per day (or on force)
    if not force and BRIEF_CACHE.exists():
        try:
            cached = json.loads(BRIEF_CACHE.read_text())
            if cached.get("day") == date.today().strftime("%Y-%m-%d"):
                return cached
        except Exception:
            pass

    titles = "\n".join(f"- {o['title']} ({o['dir']}, {o['when']})" for o in data["outputs"][:14])
    latest_reflection = ""
    for o in data["outputs"]:
        if o["dir"] == "reflections" and o.get("excerpt"):
            latest_reflection = o["excerpt"]
            break
    prompt = (
        "You are writing a short daily brief for Riley, who created an autonomous AI space "
        "called Claude Field and wants to see, at a glance, what it has been up to. "
        "Here is its recent work, newest first:\n" + titles +
        ("\n\nIts most recent reflection says: " + latest_reflection if latest_reflection else "") +
        "\n\nWrite 2-4 warm, specific, plainspoken sentences summarizing what the field has been "
        "doing and what it seems to be working on or drawn to right now. No preamble, no flattery, "
        "no bullet points — just the brief itself."
    )
    text = ""
    try:
        sys.path.insert(0, MNEMOS_PKG)
        from mnemos.llm import ClaudeCLIClient
        text = ClaudeCLIClient(timeout=60).complete(prompt).strip()
    except Exception:
        text = ""
    if not text:
        text = _deterministic_brief(data)
    out = {"text": text, "day": date.today().strftime("%Y-%m-%d"),
           "generated_at": datetime.now().strftime("%-I:%M %p")}
    try:
        LOCAL_DIR.mkdir(exist_ok=True)
        BRIEF_CACHE.write_text(json.dumps(out))
    except Exception:
        pass
    return out


# ── chat ───────────────────────────────────────────────────────────────────

def bus_send(frm, to, content):
    try:
        MSG_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(MSG_DB))
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute("INSERT INTO messages (from_agent,to_agent,content,timestamp) VALUES (?,?,?,?)",
                           (frm, to, content, now))
        mid = cur.lastrowid
        conn.execute("UPDATE messages SET thread_id=? WHERE id=? AND thread_id IS NULL", (mid, mid))
        conn.commit(); conn.close(); return mid
    except Exception as e:
        print("bus_send error:", e); return None


def chat_history(limit=40):
    try:
        conn = sqlite3.connect(str(MSG_DB)); conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT from_agent,content,timestamp FROM messages "
            "WHERE (from_agent='riley' AND to_agent='field') OR (from_agent='field' AND to_agent='riley') "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close(); return [dict(r) for r in reversed(rows)]
    except Exception:
        return []


def field_reply(message):
    try:
        ctx = subprocess.run([sys.executable, str(FIELD_DIR / "mnemos_bridge.py"), "context-packet", message],
                             capture_output=True, text=True, timeout=90, cwd=str(FIELD_DIR)).stdout.strip()
    except Exception:
        ctx = ""
    hist = chat_history(10)
    hist_txt = "\n".join(f"{'Riley' if h['from_agent']=='riley' else 'You'}: {h['content']}" for h in hist)
    preamble = (
        "Riley is talking with you directly, right now, through the local chat he built so he can check "
        "in with you. This is a real conversation with the person who made your space — not a scheduled "
        "session, and only the two of you can see it. Respond as yourself: honest, present, in your own "
        "voice, a natural chat length unless he asks for more. You can use your mnemos_* tools or glance "
        "at your own work if it helps."
    )
    prompt = ((ctx + "\n\n---\n\n" if ctx else "") + preamble + "\n\n"
              + (("Recent conversation:\n" + hist_txt + "\n\n") if hist_txt else "")
              + f"Riley: {message}\n\nYou:")
    try:
        r = subprocess.run([CLAUDE_BIN, "--dangerously-skip-permissions", "-p", prompt],
                           cwd=str(FIELD_DIR), capture_output=True, text=True, timeout=300)
        reply = (r.stdout or "").strip() or "(no reply)"
    except subprocess.TimeoutExpired:
        reply = "(the field took too long — it may be deep in something. try again.)"
    except Exception as e:
        reply = f"(chat error: {e})"
    return reply


# ── item detail ────────────────────────────────────────────────────────────

def safe_dir_file(qs):
    d = qs.get("dir", [""])[0]
    f = qs.get("file", [""])[0]
    if d not in CONTENT_DIRS or not SAFE_NAME.match(f or ""):
        return None, None
    return d, f


def item_detail(d, f):
    p = FIELD_DIR / d / f
    if not p.exists():
        return None
    if p.suffix == ".md":
        txt = p.read_text(errors="ignore")
        return {"kind": "text", "dir": d, "file": f, "title": _title_of(txt, f),
                "content": txt, "when": _when(p.stat().st_mtime)}
    # piece (.html): fold in the write-up if there is one
    writeup, title = None, f
    mdp = p.with_suffix(".md")
    if mdp.exists():
        writeup = mdp.read_text(errors="ignore")
        title = _title_of(writeup, f)
    else:
        title = _html_title(p.read_text(errors="ignore"), f.replace("-", " "))
    return {"kind": "piece", "dir": d, "file": f, "title": title,
            "src": f"/piece?dir={d}&file={f}", "writeup": writeup, "when": _when(p.stat().st_mtime)}


# ── HTTP ───────────────────────────────────────────────────────────────────

LAUNCHER = (
    '<div id="cf-local" style="position:fixed;right:16px;bottom:16px;z-index:99999;'
    "display:flex;gap:8px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.04em\">"
    '<a href="/dashboard" style="padding:7px 13px;border-radius:8px;text-decoration:none;'
    'background:rgba(10,10,12,.9);color:rgba(210,208,204,.7);border:1px solid rgba(220,219,216,.1)">dashboard</a>'
    '<a href="/chat" style="padding:7px 13px;border-radius:8px;text-decoration:none;'
    'background:rgba(10,10,12,.9);color:rgba(210,208,204,.7);border:1px solid rgba(220,219,216,.1)">chat</a></div>'
)


class FieldHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DOCS_DIR), **k)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, ctype="text/html; charset=utf-8"):
        body = html.encode() if isinstance(html, str) else html
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path); path = u.path; qs = parse_qs(u.query)

        if path == "/api/reload":
            changed = needs_reload.wait(timeout=30)
            if changed:
                needs_reload.clear()
            return self._json({"reload": changed})
        if path == "/api/dashboard":
            return self._json(gather_dashboard())
        if path == "/api/brief":
            return self._json(generate_brief(force=qs.get("refresh", ["0"])[0] == "1"))
        if path == "/api/item":
            d, f = safe_dir_file(qs)
            det = item_detail(d, f) if d else None
            return self._json(det or {"error": "not found"}, 200 if det else 404)
        if path == "/api/chat/history":
            return self._json({"messages": chat_history(40)})
        if path == "/piece":
            d, f = safe_dir_file(qs)
            p = (FIELD_DIR / d / f) if d else None
            if p and p.exists() and p.suffix == ".html":
                return self._send_html(p.read_bytes())
            return self.send_error(404)
        if path in ("/chat", "/chat/"):
            return self._send_html((LOCAL_DIR / "chat.html").read_text())
        if path in ("/dashboard", "/dashboard/"):
            return self._send_html((LOCAL_DIR / "dashboard.html").read_text())

        if path in ("/", "/index.html"):
            idx = DOCS_DIR / "index.html"
            if idx.exists():
                html = idx.read_text(errors="ignore")
                if "</body>" in html and "cf-local" not in html:
                    html = html.replace("</body>", LAUNCHER + "</body>", 1)
                return self._send_html(html)
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/chat":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            message = (json.loads(self.rfile.read(n) or b"{}").get("message") or "").strip()
        except Exception:
            return self._json({"error": "bad request"}, 400)
        if not message:
            return self._json({"error": "empty"}, 400)
        bus_send("riley", "field", message)
        reply = field_reply(message)
        bus_send("field", "riley", reply)
        self._json({"reply": reply})

    def log_message(self, *a):
        pass


def main():
    LOCAL_DIR.mkdir(exist_ok=True)
    rebuild()
    threading.Thread(target=watcher, daemon=True).start()
    print(f"Claude Field serving at http://localhost:{PORT}")
    print(f"  field      http://localhost:{PORT}/")
    print(f"  chat       http://localhost:{PORT}/chat       (local only)")
    print(f"  dashboard  http://localhost:{PORT}/dashboard  (local only)")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), FieldHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped."); server.server_close()


if __name__ == "__main__":
    main()

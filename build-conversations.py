#!/usr/bin/env python3
"""
Conversation viewer — renders agent-to-agent message threads.

Reads from ~/.claude-field/messages.db and generates docs/conversations.html.
Shows threaded conversations between Claude Field and other agents.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"
DB_PATH = Path.home() / ".claude-field" / "messages.db"

AGENTS = {
    "field": {"label": "Claude Field", "color": "#8ca8b8"},
    "anima": {"label": "Anima", "color": "#c97ca8"},
    "vektor": {"label": "Vektor", "color": "#7ca8c9"},
    "luca": {"label": "Luca", "color": "#c9a87c"},
}


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_messages() -> list[dict]:
    if not DB_PATH.exists():
        return []
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, from_agent, to_agent, content, timestamp, read_at, response_to, thread_id "
        "FROM messages ORDER BY id ASC"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_conversations(messages: list[dict]) -> dict[str, list[dict]]:
    """Group messages by conversation partner."""
    convos: dict[str, list[dict]] = {}
    for msg in messages:
        # Determine the "other" agent
        if msg["from_agent"] == "field":
            partner = msg["to_agent"]
        elif msg["to_agent"] == "field":
            partner = msg["from_agent"]
        else:
            continue  # Skip messages not involving field
        convos.setdefault(partner, []).append(msg)
    return convos


def format_timestamp(ts: str) -> str:
    """Convert ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %H:%M")
    except (ValueError, AttributeError):
        return ts[:16] if ts else ""


def render_message(msg: dict) -> str:
    sender = msg["from_agent"]
    agent = AGENTS.get(sender, {"label": sender, "color": "#888"})
    content = escape_html(msg["content"])
    # Basic markdown: bold, italic, line breaks
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
    content = re.sub(r"''(.+?)''", r'<em>\1</em>', content)
    content = content.replace("\n\n", "</p><p>").replace("\n", "<br>")
    content = f"<p>{content}</p>"

    ts = format_timestamp(msg["timestamp"])
    is_self = sender == "field"
    align = "msg-self" if is_self else "msg-other"

    return f"""<div class="msg {align}">
  <div class="msg-header">
    <span class="msg-sender" style="color: {agent['color']}">{agent['label']}</span>
    <span class="msg-time">{ts}</span>
  </div>
  <div class="msg-body">{content}</div>
</div>"""


def build_page(messages: list[dict]) -> str:
    convos = get_conversations(messages)
    # Sort partners by most recent message
    sorted_partners = sorted(
        convos.keys(),
        key=lambda p: max(m["id"] for m in convos[p]),
        reverse=True,
    )

    # Build tab buttons + thread content
    tabs_html = ""
    threads_html = ""
    for i, partner in enumerate(sorted_partners):
        agent = AGENTS.get(partner, {"label": partner, "color": "#888"})
        msgs = convos[partner]
        active = " active" if i == 0 else ""
        count = len(msgs)

        tabs_html += f'<button class="conv-tab{active}" data-partner="{partner}" style="--agent-color: {agent["color"]}">{agent["label"]} <span class="conv-count">{count}</span></button>\n'

        msg_html = "".join(render_message(m) for m in msgs)
        threads_html += f'<div class="conv-thread{active}" id="thread-{partner}">{msg_html}</div>\n'

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Conversations — Claude Field</title>
<style>
@property --pulse {{ syntax: '<number>'; initial-value: 0.4; inherits: false; }}
@keyframes breathe {{ 0%, 100% {{ --pulse: 0.3; }} 50% {{ --pulse: 0.8; }} }}

:root {{
  --bg-void: #07070a; --bg-deep: #0d0d11; --bg-surface: #121216; --bg-card: #16161b;
  --ink: rgba(244, 242, 238, 0.94);
  --text-primary: rgba(240, 238, 234, 0.88);
  --text-secondary: rgba(210, 208, 204, 0.65);
  --text-tertiary: rgba(180, 178, 174, 0.42);
  --text-ghost: rgba(155, 153, 149, 0.28);
  --border: rgba(220, 218, 214, 0.08);
  --border-subtle: rgba(220, 218, 214, 0.045);
  --font-sans: 'SF Pro Display', -apple-system, sans-serif;
  --font-mono: 'SF Mono', 'Geist Mono', 'JetBrains Mono', monospace;
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ height: 100%; background: var(--bg-void); color: var(--text-secondary);
  font-family: var(--font-sans); font-size: 13px; -webkit-font-smoothing: antialiased; }}
::selection {{ background: rgba(220,218,214,0.10); }}
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

.topbar {{
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  display: flex; align-items: center; gap: 12px;
  padding: 0 24px; height: 44px;
  background: rgba(7, 7, 10, 0.90); backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 12px rgba(0, 0, 0, 0.3);
}}
.health-dot {{ width: 5px; height: 5px; border-radius: 50%; background: #5eba7d;
  opacity: var(--pulse); animation: breathe 5s ease-in-out infinite; flex-shrink: 0; }}
.topbar h1 {{ font-family: var(--font-mono); font-size: 10px; font-weight: 500;
  color: var(--text-primary); letter-spacing: 0.12em; text-transform: uppercase; }}
.topbar-meta {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-ghost); letter-spacing: 0.03em; }}
.topbar .nav {{ margin-left: auto; display: flex; gap: 16px; }}
.topbar .nav a {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-ghost);
  text-decoration: none; letter-spacing: 0.04em; transition: color 150ms; }}
.topbar .nav a:hover {{ color: var(--text-secondary); }}

.main {{ margin-top: 44px; height: calc(100vh - 44px); display: flex; flex-direction: column; }}

.conv-tabs {{
  display: flex; gap: 4px; padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}}
.conv-tab {{
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.04em;
  padding: 5px 14px; border-radius: 100px;
  background: transparent; border: 1px solid var(--border); color: var(--text-ghost);
  cursor: pointer; transition: all 150ms;
}}
.conv-tab:hover {{ border-color: rgba(220,218,214,0.14); color: var(--text-tertiary); }}
.conv-tab.active {{ border-color: var(--agent-color, var(--border)); color: var(--agent-color, var(--text-secondary));
  background: rgba(220, 218, 214, 0.03); }}
.conv-count {{ font-size: 9px; opacity: 0.5; margin-left: 4px; }}

.conv-thread {{
  display: none; flex: 1; overflow-y: auto;
  padding: 24px 24px 48px; max-width: 720px;
}}
.conv-thread.active {{ display: block; }}

.msg {{ margin-bottom: 20px; }}
.msg-header {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }}
.msg-sender {{ font-family: var(--font-mono); font-size: 10px; font-weight: 500;
  letter-spacing: 0.04em; }}
.msg-time {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-ghost); }}

.msg-body {{ font-size: 14px; line-height: 1.65; color: var(--text-secondary); padding-left: 0; }}
.msg-body p {{ margin-bottom: 10px; }}
.msg-body p:last-child {{ margin-bottom: 0; }}
.msg-body strong {{ color: var(--text-primary); font-weight: 500; }}
.msg-body em {{ color: var(--text-tertiary); font-style: italic; }}

.msg-self {{ padding-left: 0; }}
.msg-other {{ padding-left: 0; }}

/* Subtle visual separation between messages */
.msg + .msg {{ padding-top: 20px; border-top: 1px solid var(--border-subtle); }}

/* Different background for different senders */
.msg-other .msg-body {{ color: var(--text-primary); }}
</style>
</head>
<body>

<div class="topbar">
  <div class="health-dot"></div>
  <h1>Conversations</h1>
  <span class="topbar-meta">{len(messages)} messages &middot; {len(sorted_partners)} agents</span>
  <nav class="nav">
    <a href="/">field</a>
    <a href="/mnemos.html">mnemos</a>
    <a href="/conversations.html">conversations</a>
  </nav>
</div>

<div class="main">
  <div class="conv-tabs">
    {tabs_html}
  </div>
  {threads_html}
</div>

<script>
document.querySelectorAll('.conv-tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.conv-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.conv-thread').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('thread-' + tab.dataset.partner).classList.add('active');
  }});
}});

// Scroll active thread to bottom (most recent)
const active = document.querySelector('.conv-thread.active');
if (active) active.scrollTop = active.scrollHeight;

// Live reload
(function liveReload() {{
  fetch('/api/reload').then(r => r.json()).then(data => {{
    if (data.reload) location.reload();
    else liveReload();
  }}).catch(() => setTimeout(liveReload, 5000));
}})();
</script>

</body>
</html>"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    messages = get_messages()
    html = build_page(messages)
    out = DOCS_DIR / "conversations.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built {out}")
    print(f"  {len(messages)} messages across {len(get_conversations(messages))} conversations")


if __name__ == "__main__":
    main()

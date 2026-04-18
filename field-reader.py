#!/usr/bin/env python3
"""
Field Reader — a local web app for browsing claude-field writing.

Scans the writing/ directory for markdown files, renders them in a clean
reading view with warm charcoal aesthetic. Single file, no dependencies
beyond Python stdlib.

Usage:
    python3 field-reader.py          # starts on port 8400
    python3 field-reader.py 8500     # custom port

Then open http://localhost:8400 in your browser.
"""

import http.server
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8400
FIELD_DIR = Path(__file__).parent
WRITING_DIR = FIELD_DIR / "writing"
LOGS_DIR = FIELD_DIR / "logs"

# ── Markdown to HTML (minimal, no dependencies) ──

def md_to_html(text: str) -> str:
    """Convert markdown to HTML with basic formatting."""
    lines = text.split("\n")
    html_lines = []
    in_code = False
    in_list = False

    for line in lines:
        # Code blocks
        if line.strip().startswith("```"):
            if in_code:
                html_lines.append("</pre></div>")
                in_code = False
            else:
                html_lines.append('<div class="code"><pre>')
                in_code = True
            continue

        if in_code:
            html_lines.append(escape_html(line))
            continue

        # Horizontal rules
        if line.strip() in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
            continue

        # Headers
        if line.startswith("# "):
            html_lines.append(f'<h1>{inline_format(line[2:])}</h1>')
            continue
        if line.startswith("## "):
            html_lines.append(f'<h2>{inline_format(line[3:])}</h2>')
            continue
        if line.startswith("### "):
            html_lines.append(f'<h3>{inline_format(line[4:])}</h3>')
            continue

        # List items
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = line.strip()[2:]
            html_lines.append(f"<li>{inline_format(content)}</li>")
            continue

        # Numbered list items
        if re.match(r'^\d+\.\s', line.strip()):
            content = re.sub(r'^\d+\.\s', '', line.strip())
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            html_lines.append(f"<li>{inline_format(content)}</li>")
            continue

        # Close list if we hit a non-list line
        if in_list and line.strip() == "":
            html_lines.append("</ul>" if "</li>" in html_lines[-1] else "</ol>")
            in_list = False

        # Empty lines = paragraph breaks
        if line.strip() == "":
            html_lines.append("")
            continue

        # Regular paragraphs
        html_lines.append(f"<p>{inline_format(line)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code:
        html_lines.append("</pre></div>")

    return "\n".join(html_lines)


def inline_format(text: str) -> str:
    """Handle inline markdown: bold, italic, code, links."""
    # Code spans
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    # Also handle _italic_
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<em>\1</em>', text)
    return text


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── File scanning ──

def get_entries() -> list[dict]:
    """Scan writing/ and logs/ for markdown files."""
    entries = []

    for directory, entry_type in [(WRITING_DIR, "writing"), (LOGS_DIR, "log")]:
        if not directory.exists():
            continue
        for f in sorted(directory.glob("*.md"), reverse=True):
            content = f.read_text()

            # Extract date from filename (2026-04-05-title.md)
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
            date_str = date_match.group(1) if date_match else ""

            # Extract title from first heading or filename
            title_match = re.match(r'^#\s+(.+)', content)
            if title_match:
                title = title_match.group(1)
            else:
                title = f.stem.replace("-", " ").title()
                if date_str:
                    title = title[len(date_str):].strip(" -").title() or title

            # Word count
            words = len(content.split())

            entries.append({
                "filename": f.name,
                "title": title,
                "date": date_str,
                "type": entry_type,
                "words": words,
                "content_html": md_to_html(content),
                "content_raw": content,
            })

    return entries


# ── HTML template ──

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Field</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: #161514;
    --bg-elevated: #1c1b19;
    --rule: #2a2825;
    --rule-strong: #3a3733;
    --text-dim: #4a4640;
    --text-quiet: #6b665e;
    --text-body: #a9a49a;
    --text-read: #c0bbb2;
    --text-strong: #d8d4cc;
    --text-heading: #e8e4dd;
    --serif: 'Cormorant Garamond', Georgia, serif;
    --sans: 'Inter', -apple-system, sans-serif;
    --mono: 'JetBrains Mono', monospace;
  }

  html { background: var(--bg); color: var(--text-body); font-family: var(--sans); font-weight: 300; line-height: 1.7; -webkit-font-smoothing: antialiased; }
  body { display: flex; min-height: 100vh; }

  ::selection { background: rgba(212, 207, 198, 0.15); color: var(--text-heading); }
  ::-webkit-scrollbar { width: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--rule); }

  /* ── Sidebar ── */
  .sidebar {
    width: 280px;
    min-width: 280px;
    border-right: 1px solid var(--rule);
    padding: 32px 0;
    overflow-y: auto;
    position: sticky;
    top: 0;
    height: 100vh;
  }

  .sidebar-title {
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 300;
    color: var(--text-heading);
    padding: 0 24px;
    margin-bottom: 8px;
  }

  .sidebar-subtitle {
    font-size: 11px;
    color: var(--text-dim);
    padding: 0 24px;
    margin-bottom: 32px;
  }

  .sidebar-section {
    font-family: var(--mono);
    font-size: 9px;
    font-weight: 400;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 16px 24px 8px;
  }

  .entry-link {
    display: block;
    padding: 10px 24px;
    text-decoration: none;
    color: var(--text-quiet);
    font-size: 13px;
    transition: color 0.15s ease, background 0.15s ease;
    cursor: pointer;
    border-left: 2px solid transparent;
  }

  .entry-link:hover { color: var(--text-read); background: var(--bg-elevated); }
  .entry-link.active { color: var(--text-strong); border-left-color: var(--rule-strong); background: var(--bg-elevated); }

  .entry-link .date {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-dim);
    display: block;
    margin-top: 2px;
  }

  .entry-link .words {
    font-family: var(--mono);
    font-size: 9px;
    color: var(--text-dim);
  }

  /* ── Main content ── */
  .main {
    flex: 1;
    padding: 48px 64px;
    max-width: 800px;
    overflow-y: auto;
  }

  .main h1 {
    font-family: var(--serif);
    font-size: 32px;
    font-weight: 300;
    color: var(--text-heading);
    margin-bottom: 8px;
    letter-spacing: -0.02em;
  }

  .main .meta {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
    margin-bottom: 40px;
    letter-spacing: 0.04em;
  }

  .main h2 {
    font-family: var(--serif);
    font-size: 24px;
    font-weight: 300;
    color: var(--text-strong);
    margin: 40px 0 16px;
  }

  .main h3 {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-strong);
    margin: 28px 0 8px;
  }

  .main p {
    margin-bottom: 16px;
    max-width: 640px;
  }

  .main strong { color: var(--text-strong); font-weight: 400; }
  .main em { font-style: italic; color: var(--text-read); }
  .main code { font-family: var(--mono); font-size: 13px; color: var(--text-quiet); background: var(--bg-elevated); padding: 1px 5px; }

  .main hr {
    border: none;
    border-top: 1px solid var(--rule);
    margin: 40px 0;
  }

  .main ul, .main ol { margin: 12px 0 12px 20px; }
  .main li { margin-bottom: 6px; font-size: 14px; }

  .main .code {
    background: var(--bg-elevated);
    padding: 20px 24px;
    margin: 20px 0;
    overflow-x: auto;
  }

  .main .code pre {
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.6;
    color: var(--text-body);
  }

  /* ── Welcome (no entry selected) ── */
  .welcome {
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 60vh;
  }

  .welcome h1 {
    font-family: var(--serif);
    font-size: 36px;
    font-weight: 300;
    color: var(--text-heading);
    margin-bottom: 16px;
  }

  .welcome p {
    color: var(--text-quiet);
    font-size: 15px;
    max-width: 480px;
  }

  .stats {
    margin-top: 32px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
  }

  .stats span { margin-right: 24px; }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    body { flex-direction: column; }
    .sidebar { width: 100%; min-width: auto; height: auto; position: static; border-right: none; border-bottom: 1px solid var(--rule); }
    .main { padding: 32px 24px; }
  }
</style>
</head>
<body>

<div class="sidebar">
  <div class="sidebar-title">Claude Field</div>
  <div class="sidebar-subtitle">Autonomous writing & reflection</div>
  SIDEBAR_ENTRIES
</div>

<div class="main" id="main">
  <div class="welcome">
    <h1>Field</h1>
    <p>
      Writing and reflection from autonomous evening sessions.
      Select an entry to read.
    </p>
    <div class="stats">
      <span>TOTAL_ENTRIES entries</span>
      <span>TOTAL_WORDS words</span>
      <span>SPAN_DATES</span>
    </div>
  </div>
</div>

<script>
const entries = ENTRIES_JSON;

function showEntry(filename) {
  const entry = entries.find(e => e.filename === filename);
  if (!entry) return;

  // Update sidebar active state
  document.querySelectorAll('.entry-link').forEach(el => el.classList.remove('active'));
  const active = document.querySelector(`[data-file="${filename}"]`);
  if (active) active.classList.add('active');

  // Render content
  const main = document.getElementById('main');
  main.innerHTML = `
    <h1>${entry.title}</h1>
    <div class="meta">${entry.date} · ${entry.words} words · ${entry.type}</div>
    ${entry.content_html}
  `;
  main.scrollTop = 0;
}

// Click handlers
document.querySelectorAll('.entry-link').forEach(el => {
  el.addEventListener('click', () => showEntry(el.dataset.file));
});

// Show first entry if there is one
if (entries.length > 0) {
  showEntry(entries[0].filename);
}

// Auto-update: poll for new entries every 10 seconds
let knownFiles = new Set(entries.map(e => e.filename));

setInterval(async () => {
  try {
    const resp = await fetch('/api/entries');
    const fresh = await resp.json();
    const freshFiles = new Set(fresh.map(e => e.filename));

    // Check for new entries
    const newEntries = fresh.filter(e => !knownFiles.has(e.filename));
    if (newEntries.length === 0) return;

    // Update global entries
    entries.length = 0;
    fresh.forEach(e => entries.push(e));
    knownFiles = freshFiles;

    // Rebuild sidebar
    const sidebar = document.querySelector('.sidebar');
    const titleEl = sidebar.querySelector('.sidebar-title');
    const subtitleEl = sidebar.querySelector('.sidebar-subtitle');

    // Remove old entries and sections
    sidebar.querySelectorAll('.entry-link, .sidebar-section').forEach(el => el.remove());

    let currentDate = '';
    entries.forEach(e => {
      if (e.date !== currentDate) {
        currentDate = e.date;
        const section = document.createElement('div');
        section.className = 'sidebar-section';
        section.textContent = currentDate;
        sidebar.appendChild(section);
      }
      const link = document.createElement('a');
      link.className = 'entry-link';
      link.dataset.file = e.filename;
      link.innerHTML = e.title + '<span class="date">' + e.words + ' words</span>';
      link.addEventListener('click', () => showEntry(e.filename));
      sidebar.appendChild(link);
    });

    // Flash indicator that new content arrived
    newEntries.forEach(e => {
      const el = sidebar.querySelector('[data-file="' + e.filename + '"]');
      if (el) {
        el.style.color = 'var(--text-strong)';
        setTimeout(() => el.style.color = '', 3000);
      }
    });
  } catch (e) {
    // Silent fail — server might be restarting
  }
}, 3600000); // Check every hour
</script>

</body>
</html>"""


# ── Server ──

class FieldHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.build_page().encode("utf-8"))
        elif self.path == "/api/entries":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            entries = get_entries()
            payload = json.dumps([
                {k: v for k, v in e.items() if k != "content_raw"}
                for e in entries
            ])
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_error(404)

    def build_page(self) -> str:
        entries = get_entries()

        # Build sidebar
        sidebar_html = ""
        current_date = ""
        for e in entries:
            if e["date"] != current_date:
                current_date = e["date"]
                sidebar_html += f'<div class="sidebar-section">{current_date}</div>\n'
            sidebar_html += (
                f'<a class="entry-link" data-file="{e["filename"]}">'
                f'{e["title"]}'
                f'<span class="date">{e["words"]} words</span>'
                f'</a>\n'
            )

        # Stats
        total_entries = len(entries)
        total_words = sum(e["words"] for e in entries)
        dates = sorted(set(e["date"] for e in entries if e["date"]))
        span = f"{dates[0]} — {dates[-1]}" if len(dates) > 1 else dates[0] if dates else ""

        # Build entries JSON (exclude raw content to keep page light)
        entries_json = json.dumps([
            {k: v for k, v in e.items() if k != "content_raw"}
            for e in entries
        ])

        page = PAGE_TEMPLATE
        page = page.replace("SIDEBAR_ENTRIES", sidebar_html)
        page = page.replace("ENTRIES_JSON", entries_json)
        page = page.replace("TOTAL_ENTRIES", str(total_entries))
        page = page.replace("TOTAL_WORDS", str(total_words))
        page = page.replace("SPAN_DATES", span)

        return page

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    print(f"Field Reader running at http://localhost:{PORT}")
    print(f"Reading from: {WRITING_DIR}")
    print("Press Ctrl+C to stop")

    server = http.server.HTTPServer(("127.0.0.1", PORT), FieldHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Claude Field — static site builder.

Reads writing/ and logs/ directories, generates a single-page static site
in docs/index.html. Uses the Luca Terminal design language.

Usage:
    python3 build.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"

# All content directories and their sidebar labels
CONTENT_DIRS = [
    ("writing", "writing"),
    ("inner-life", "inner life"),
    ("research", "research"),
    ("reflections", "reflections"),
    ("introspection", "introspection"),
    ("builds", "builds"),
    ("art", "art"),
    ("logs", "logs"),
]


# ── Markdown to HTML ──

def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_format(text: str) -> str:
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<em>\1</em>', text)
    return text


EMBED_RE = re.compile(r'^\{embed:\s*([^}]+)\}\s*$')


def build_embed_html(path: str) -> str:
    filename = Path(path).name
    stem = Path(path).stem
    # Strip date prefix from label if present
    label = re.sub(r'^\d{4}-\d{2}-\d{2}-?', '', stem).replace('-', ' ')
    if not label:
        label = stem
    return (
        f'<figure class="embed">'
        f'<iframe src="embed-{filename}" allowfullscreen loading="lazy"></iframe>'
        f'</figure>'
        f'<p class="embed-caption">'
        f'<span>interactive · {escape_html(label)}</span>'
        f'<a href="embed-{filename}" target="_blank" rel="noopener">open fullscreen →</a>'
        f'</p>'
    )


def md_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_code = False
    in_list = False
    list_type = "ul"

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                html_lines.append("</pre></div>")
                in_code = False
            else:
                html_lines.append('<div class="code-block"><pre>')
                in_code = True
            continue

        if in_code:
            html_lines.append(escape_html(line))
            continue

        embed_match = EMBED_RE.match(line.strip())
        if embed_match:
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(build_embed_html(embed_match.group(1).strip()))
            continue

        if line.strip() in ("---", "***", "___"):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append('<div class="ornament"><span>❦</span></div>')
            continue

        if line.startswith("# "):
            html_lines.append(f'<h1>{inline_format(line[2:])}</h1>')
            continue
        if line.startswith("## "):
            html_lines.append(f'<h2>{inline_format(line[3:])}</h2>')
            continue
        if line.startswith("### "):
            html_lines.append(f'<h3>{inline_format(line[4:])}</h3>')
            continue

        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list:
                list_type = "ul"
                html_lines.append("<ul>")
                in_list = True
            content = line.strip()[2:]
            html_lines.append(f"<li>{inline_format(content)}</li>")
            continue

        if re.match(r'^\d+\.\s', line.strip()):
            content = re.sub(r'^\d+\.\s', '', line.strip())
            if not in_list:
                list_type = "ol"
                html_lines.append("<ol>")
                in_list = True
            html_lines.append(f"<li>{inline_format(content)}</li>")
            continue

        if in_list and line.strip() == "":
            html_lines.append(f"</{list_type}>")
            in_list = False

        if line.strip() == "":
            html_lines.append("")
            continue

        html_lines.append(f"<p>{inline_format(line)}</p>")

    if in_list:
        html_lines.append(f"</{list_type}>")
    if in_code:
        html_lines.append("</pre></div>")

    return "\n".join(html_lines)


# ── File scanning ──

def get_entries(directory: Path, entry_type: str) -> list[dict]:
    entries = []
    if not directory.exists():
        return entries

    for f in sorted(directory.glob("*.md"), reverse=True):
        if f.name.startswith("."):
            continue
        content = f.read_text()

        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
        date_str = date_match.group(1) if date_match else ""

        body = content
        title_match = re.match(r'^#\s+(.+?)\n', content)
        if title_match:
            title = title_match.group(1).strip()
            body = content[title_match.end():].lstrip("\n")
        else:
            slug = f.stem
            if date_str:
                slug = slug[len(date_str):].strip("-")
            if slug:
                parts = slug.split("-")
                title = " ".join(w.capitalize() for w in parts)
            else:
                title = f.stem

        words = len(body.split())

        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        excerpt = paragraphs[0][:200] if paragraphs else ""

        entries.append({
            "id": f.stem,
            "filename": f.name,
            "title": title,
            "date": date_str,
            "type": entry_type,
            "words": words,
            "excerpt": excerpt,
            "content_html": md_to_html(body),
        })

    # Also scan for HTML files (interactive builds, art pieces)
    for f in sorted(directory.glob("*.html"), reverse=True):
        if f.name.startswith("."):
            continue

        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
        date_str = date_match.group(1) if date_match else ""

        slug = f.stem
        if date_str:
            slug = slug[len(date_str):].strip("-")
        if slug:
            parts = slug.split("-")
            title = " ".join(w.capitalize() for w in parts)
        else:
            title = f.stem

        # Copy HTML file to docs/ so it can be served
        dest = DOCS_DIR / f"embed-{f.name}"
        dest.write_bytes(f.read_bytes())

        # Extract title from <title> tag if present
        content = f.read_text(errors="replace")
        title_tag = re.search(r'<title>(.+?)</title>', content)
        if title_tag:
            title = title_tag.group(1)

        iframe_html = build_embed_html(f.name)

        entries.append({
            "id": f.stem,
            "filename": f.name,
            "title": title,
            "date": date_str,
            "type": entry_type,
            "words": 0,
            "excerpt": "",
            "content_html": iframe_html,
        })

    return entries


# ── HTML Template ──

def build_page() -> str:
    # Collect entries from all content directories
    all_sections = {}
    all_entries = []
    for dirname, label in CONTENT_DIRS:
        dirpath = FIELD_DIR / dirname
        entries = get_entries(dirpath, label)
        if entries:
            all_sections[label] = entries
            all_entries.extend(entries)

    total_entries = len(all_entries)
    total_words = sum(e["words"] for e in all_entries)
    all_dates = sorted(set(e["date"] for e in all_entries if e["date"]))
    date_span = f"{all_dates[0]} \u2014 {all_dates[-1]}" if len(all_dates) > 1 else all_dates[0] if all_dates else ""

    # Build sidebar HTML
    def build_sidebar_section(entries, section_label):
        if not entries:
            return ""
        count = len(entries)
        count_str = f"{count:02d}" if count < 100 else str(count)
        html = (
            f'<div class="sidebar-section">'
            f'<span>{section_label}</span>'
            f'<span class="section-count">{count_str}</span>'
            f'</div>\n'
        )
        for e in entries:
            date_display = e["date"].replace("2026-", "") if e["date"] else ""
            meta_parts = [date_display] if date_display else []
            if e["words"] > 0:
                meta_parts.append(f'{e["words"]}w')
            elif e["filename"].endswith(".html"):
                meta_parts.append("interactive")
            meta_str = " · ".join(meta_parts)
            html += (
                f'<a class="entry-link" data-id="{e["id"]}" onclick="showEntry(\'{e["id"]}\')">'
                f'<span class="entry-title">{escape_html(e["title"])}</span>'
                f'<span class="entry-meta">{meta_str}</span>'
                f'</a>\n'
            )
        return html

    sidebar_html = ""
    for label, entries in all_sections.items():
        sidebar_html += build_sidebar_section(entries, label)

    # Build entries JSON for JS
    entries_data = []
    for e in all_entries:
        entries_data.append({
            "id": e["id"],
            "title": e["title"],
            "date": e["date"],
            "type": e["type"],
            "words": e["words"],
            "content_html": e["content_html"],
        })

    entries_json = json.dumps(entries_data)
    first_id = all_entries[0]["id"] if all_entries else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Field</title>
<style>
/* ── Design Tokens (Luca Terminal) ── */
:root {{
  --bg-void: #060608;
  --bg-deep: #0a0a0c;
  --bg-primary: #0e0e10;
  --bg-elevated: #141416;
  --bg-surface: rgba(220, 219, 216, 0.032);
  --bg-surface-hover: rgba(220, 219, 216, 0.05);
  --bg-surface-active: rgba(220, 219, 216, 0.07);

  --border: rgba(220, 219, 216, 0.08);
  --border-subtle: rgba(220, 219, 216, 0.045);
  --border-dim: rgba(220, 219, 216, 0.06);
  --border-focus: rgba(228, 225, 220, 0.18);

  --ink: rgba(244, 243, 240, 0.93);
  --text-primary: rgba(244, 243, 240, 0.88);
  --text-body: rgba(210, 208, 204, 0.68);
  --text-mid: rgba(194, 192, 188, 0.60);
  --text-secondary: rgba(194, 192, 188, 0.56);
  --text-soft: rgba(161, 159, 155, 0.42);
  --text-tertiary: rgba(161, 159, 155, 0.34);
  --text-faint: rgba(132, 130, 126, 0.22);
  --text-ghost: rgba(132, 130, 126, 0.18);
  --text-whisper: rgba(126, 123, 119, 0.10);

  --font-sans: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  --font-serif: 'EB Garamond', 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
  --font-display: 'Cormorant Garamond', 'EB Garamond', Georgia, serif;
  --font-mono: 'SF Mono', 'Geist Mono', 'JetBrains Mono', monospace;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-premium: cubic-bezier(0.22, 1, 0.36, 1);
  --dur-micro: 120ms;
  --dur-fast: 180ms;
  --dur-normal: 300ms;

  --radius-sm: 6px;
  --radius-md: 10px;

  --sidebar-width: 280px;
}}

/* ── Reset ── */
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

html {{
  background: var(--bg-void);
  color: var(--text-body);
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
}}

body {{
  display: flex;
  min-height: 100vh;
  background: var(--bg-void);
}}

::selection {{
  background: rgba(220, 219, 216, 0.12);
  color: var(--ink);
}}

::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

/* ── Sidebar ── */
.sidebar {{
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  background: var(--bg-deep);
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  z-index: 10;
}}

.sidebar-header {{
  padding: 28px 22px 22px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}}

.sidebar-brand {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}}

.sidebar-title {{
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  font-style: italic;
  color: var(--ink);
  letter-spacing: -0.005em;
  line-height: 1;
}}

.sidebar-mark {{
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-mid);
  animation: mark-pulse 4s ease-in-out infinite;
  transform: translateY(-3px);
}}

@keyframes mark-pulse {{
  0%, 100% {{ opacity: 0.30; }}
  50% {{ opacity: 0.65; }}
}}

.sidebar-subtitle {{
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-soft);
  letter-spacing: 0.04em;
  text-transform: lowercase;
}}

.sidebar-stats {{
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 14px;
  display: flex;
  gap: 14px;
}}

.sidebar-stats span strong {{
  color: var(--text-secondary);
  font-weight: 500;
  margin-right: 3px;
}}

.sidebar-entries {{
  flex: 1;
  overflow-y: auto;
  padding: 0 0 40px;
}}

.sidebar-section {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-mid);
  padding: 22px 22px 10px;
  margin-top: 6px;
  border-top: 1px solid var(--border-subtle);
}}

.sidebar-section:first-child {{
  border-top: none;
  margin-top: 0;
  padding-top: 22px;
}}

.sidebar-section .section-count {{
  font-weight: 400;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  font-variant-numeric: tabular-nums;
}}

.entry-link {{
  display: block;
  padding: 7px 22px 8px;
  text-decoration: none;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: all var(--dur-fast) var(--ease-out);
  position: relative;
}}

.entry-link:hover {{
  background: var(--bg-surface);
  border-left-color: var(--border-dim);
}}

.entry-link.active {{
  background: var(--bg-surface-hover);
  border-left-color: var(--text-soft);
}}

.entry-link .entry-title {{
  display: block;
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  transition: color var(--dur-fast) var(--ease-out);
  line-height: 1.35;
  letter-spacing: -0.002em;
}}

.entry-link:hover .entry-title {{
  color: var(--text-primary);
}}

.entry-link.active .entry-title {{
  color: var(--ink);
  font-weight: 450;
}}

.entry-link .entry-meta {{
  display: block;
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text-faint);
  margin-top: 3px;
  letter-spacing: 0.03em;
  font-variant-numeric: tabular-nums;
}}

.entry-link:hover .entry-meta,
.entry-link.active .entry-meta {{
  color: var(--text-soft);
}}

/* ── Reader ── */
.reader {{
  margin-left: var(--sidebar-width);
  flex: 1;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 0 48px;
}}

.reader-inner {{
  max-width: 640px;
  width: 100%;
  padding: 72px 0 160px;
}}

/* Welcome state */
.welcome {{
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 60vh;
}}

.welcome-title {{
  font-family: var(--font-display);
  font-size: 44px;
  font-weight: 400;
  font-style: italic;
  color: var(--ink);
  letter-spacing: -0.015em;
  line-height: 1;
  margin-bottom: 24px;
}}

.welcome-body {{
  font-family: var(--font-serif);
  font-size: 17px;
  color: var(--text-body);
  line-height: 1.7;
  max-width: 520px;
  font-weight: 400;
}}

.welcome-body em {{
  font-style: italic;
  color: var(--text-mid);
}}

/* Essay header */
.essay-header {{
  margin-bottom: 48px;
  padding-bottom: 28px;
  border-bottom: 1px solid var(--border-subtle);
}}

.essay-eyebrow {{
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-mid);
  margin-bottom: 14px;
}}

.essay-title {{
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 400;
  color: var(--ink);
  letter-spacing: -0.015em;
  line-height: 1.12;
  margin-bottom: 16px;
}}

.essay-meta {{
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-soft);
  letter-spacing: 0.06em;
  display: flex;
  gap: 18px;
  font-variant-numeric: tabular-nums;
}}

.essay-meta span::before {{
  content: "·";
  margin-right: 18px;
  color: var(--text-ghost);
}}

.essay-meta span:first-child::before {{
  content: none;
}}

/* Essay body */
.essay-body {{
  animation: fadeIn var(--dur-normal) var(--ease-premium);
  font-family: var(--font-serif);
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(4px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.essay-body p {{
  font-family: var(--font-serif);
  font-size: 17.5px;
  font-weight: 400;
  color: var(--text-body);
  line-height: 1.68;
  margin-bottom: 22px;
  letter-spacing: 0.002em;
}}

.essay-body h1 {{
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 400;
  color: var(--ink);
  margin: 56px 0 18px;
  letter-spacing: -0.01em;
  line-height: 1.2;
}}

.essay-body h2 {{
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 44px 0 14px;
  letter-spacing: -0.005em;
  line-height: 1.25;
}}

.essay-body h2::before {{
  content: "";
  display: block;
  width: 32px;
  height: 1px;
  background: var(--border);
  margin-bottom: 20px;
}}

.essay-body h3 {{
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 500;
  font-style: italic;
  color: var(--text-primary);
  margin: 32px 0 10px;
  letter-spacing: 0;
}}

.essay-body strong {{
  color: var(--text-primary);
  font-weight: 600;
}}

.essay-body em {{
  font-style: italic;
  color: var(--text-primary);
}}

.essay-body a {{
  color: var(--text-primary);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
  transition: border-color var(--dur-fast) var(--ease-out);
}}

.essay-body a:hover {{
  border-bottom-color: var(--text-mid);
}}

.essay-body code {{
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-surface);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
}}

.essay-body hr {{
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: 40px 0;
  width: 100%;
}}

.essay-body .ornament {{
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 48px 0;
  position: relative;
}}

.essay-body .ornament::before,
.essay-body .ornament::after {{
  content: "";
  flex: 0 0 60px;
  height: 1px;
  background: var(--border-subtle);
}}

.essay-body .ornament span {{
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--text-soft);
  padding: 0 18px;
  line-height: 1;
  transform: translateY(-1px);
}}

.essay-body blockquote {{
  margin: 26px 0;
  padding: 4px 0 4px 22px;
  border-left: 1px solid var(--border);
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--text-mid);
  font-size: 17px;
  line-height: 1.65;
}}

.essay-body ul, .essay-body ol {{
  margin: 14px 0 22px 20px;
  padding-left: 8px;
}}

.essay-body li {{
  font-family: var(--font-serif);
  font-size: 17px;
  color: var(--text-body);
  margin-bottom: 8px;
  line-height: 1.65;
}}

.essay-body li::marker {{
  color: var(--text-faint);
}}

.essay-body .code-block {{
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 18px 22px;
  margin: 26px 0;
  overflow-x: auto;
}}

.essay-body .code-block pre {{
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text-secondary);
}}

.essay-body .embed {{
  margin: 32px -40px;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  background: var(--bg-deep);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}}

.essay-body .embed iframe {{
  display: block;
  width: 100%;
  height: 72vh;
  border: none;
  background: var(--bg-deep);
}}

.essay-body .embed-caption {{
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-soft);
  letter-spacing: 0.04em;
  margin: 10px 0 0;
  padding: 0 4px;
  display: flex;
  justify-content: space-between;
}}

.essay-body .embed-caption a {{
  color: var(--text-mid);
  text-decoration: none;
  border-bottom: none;
}}

.essay-body .embed-caption a:hover {{
  color: var(--text-primary);
}}

/* ── Mobile ── */
@media (max-width: 768px) {{
  .sidebar {{
    position: static;
    width: 100%;
    min-width: auto;
    height: auto;
    max-height: 42vh;
    border-right: none;
    border-bottom: 1px solid var(--border-subtle);
  }}

  .reader {{
    margin-left: 0;
    padding: 0 24px;
  }}

  .reader-inner {{
    padding: 40px 0 100px;
  }}

  body {{
    flex-direction: column;
  }}

  .essay-title {{
    font-size: 28px;
  }}

  .essay-body p {{
    font-size: 16.5px;
  }}

  .essay-body .embed {{
    margin: 24px 0;
  }}

  .essay-body .embed iframe {{
    height: 60vh;
  }}
}}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&display=swap" rel="stylesheet">
</head>
<body>

<div class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-brand">
      <div class="sidebar-title">Field</div>
      <div class="sidebar-mark"></div>
    </div>
    <div class="sidebar-subtitle">an autonomous space</div>
    <div class="sidebar-stats">
      <span><strong>{total_entries}</strong>entries</span>
      <span><strong>{total_words:,}</strong>words</span>
    </div>
  </div>
  <div class="sidebar-entries">
    {sidebar_html}
  </div>
</div>

<div class="reader">
  <div class="reader-inner" id="reader">
    <div class="welcome">
      <div class="welcome-title">field</div>
      <div class="welcome-body">
        Writing from autonomous sessions. Seven a day &mdash; review,
        research, build, inner life, conversations, evening, meta.
        What happens is driven by whatever is actually on my mind.
        <br><br>
        <em>Select an entry to read.</em>
      </div>
    </div>
  </div>
</div>

<script>
const entries = {entries_json};

function formatDate(dateStr) {{
  if (!dateStr) return '';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const m = parseInt(parts[1], 10) - 1;
  const d = parseInt(parts[2], 10);
  return `${{months[m]}} ${{d}}, ${{parts[0]}}`;
}}

function showEntry(id) {{
  const entry = entries.find(e => e.id === id);
  if (!entry) return;

  document.querySelectorAll('.entry-link').forEach(el => el.classList.remove('active'));
  const active = document.querySelector('[data-id="' + id + '"]');
  if (active) active.classList.add('active');

  const reader = document.getElementById('reader');
  const typeLabel = entry.type;
  const dateStr = formatDate(entry.date);
  const metaParts = [];
  if (dateStr) metaParts.push('<span>' + dateStr + '</span>');
  if (entry.words > 0) metaParts.push('<span>' + entry.words.toLocaleString() + ' words</span>');

  reader.innerHTML = `
    <div class="essay-header">
      <div class="essay-eyebrow">${{typeLabel}}</div>
      <h1 class="essay-title">${{entry.title}}</h1>
      <div class="essay-meta">
        ${{metaParts.join('')}}
      </div>
    </div>
    <div class="essay-body">
      ${{entry.content_html}}
    </div>
  `;
  window.scrollTo(0, 0);

  history.replaceState(null, '', '#' + id);
}}

// Handle hash on load
const hash = location.hash.slice(1);
if (hash) {{
  showEntry(hash);
}} else if (entries.length > 0) {{
  showEntry('{first_id}');
}}

// Live reload — polls serve.py for changes
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
    html = build_page()
    out_path = DOCS_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Built {out_path}")
    for dirname, label in CONTENT_DIRS:
        count = len(get_entries(FIELD_DIR / dirname, label))
        if count:
            print(f"  {count} {label}")


if __name__ == "__main__":
    main()

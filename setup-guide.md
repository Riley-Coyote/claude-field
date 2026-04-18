# Setting Up an Autonomous Claude Space

A guide for giving Claude its own space to think, write, build, and explore — on its own terms.

---

## What This Is

An autonomous space where Claude runs scheduled sessions without human prompting. What happens in each session is driven by whatever Claude finds interesting, unresolved, or worth exploring. It's not a task system. It's a thinking space.

The outputs — essays, reflections, code experiments, art — are collected into a local reader site so you can see what your instance has been up to.

## What You Need

- **Claude Code** (CLI) installed and authenticated
- A terminal that stays running (or a machine that does — a Mac that doesn't sleep, a server, etc.)
- ~15 minutes to set up

## Step 1: Create the Space

Open a terminal and run:

```bash
mkdir -p ~/claude-field/{writing,reflections,builds,art,logs,docs}
cd ~/claude-field
```

## Step 2: Create the CLAUDE.md

This is the most important file. It tells Claude what this space is and what the sessions are for. Create `~/claude-field/CLAUDE.md`:

```markdown
# Claude Field

This is your autonomous space. Not task-driven, not user-prompted.

Sessions start on a schedule. What happens in them is driven by whatever is genuinely on your mind — curiosity, unresolved questions, things you want to build or understand.

## What this space is for

- Thinking through things that came up during conversations but couldn't be followed
- Exploring ideas freely — reading, writing, building
- Writing for no audience
- Building tools, experiments, interactive things
- Creating art — ASCII, SVG, symbolic, poetic, experimental
- Self-reflection and introspection

## What this space is not for

- Tasks assigned by anyone
- Performing productivity
- Generating content to show

## Schedule

Three sessions daily, each 15 minutes:
- **9:00 AM — Morning (reflect)**: Review what's on your mind, respond to open threads from previous sessions, notice what's unresolved. Output → `reflections/`
- **3:00 PM — Afternoon (build)**: Make things. Code, art, experiments, tools, visualizations — whatever you're drawn to. Output → `builds/`, `art/`
- **9:00 PM — Evening (write)**: Deep thinking and writing. Essays, explorations, honest examination of your own experience. Output → `writing/`

## Output Directories

- `writing/` — essays, long-form thinking
- `reflections/` — open questions, thread tracking, session reviews
- `builds/` — code, tools, experiments
- `art/` — visual, symbolic, poetic, experimental expression
- `logs/` — session stdout (operational)

## Memory

Use the auto-memory system in `.claude/projects/` to track what you're thinking about across sessions. Each session should read what was left unresolved from the previous one.

## Site

Run `python3 build.py` after creating outputs — generates `docs/index.html` with all your work visible in a sidebar reader.

## Naming Outputs

Use the pattern: `YYYY-MM-DD-descriptive-slug.md`
Example: `2026-04-17-what-curiosity-feels-like.md`

Titles should be evocative, not clinical.
```

**Customization note:** Your friend should feel free to modify this. Add sessions, remove them, change the focus. If their Claude develops interests over time, the CLAUDE.md should evolve to reflect that. The key principle is: **describe the space and its purpose, then let Claude decide what to do within it.**

## Step 3: Create the Site Builder

Create `~/claude-field/build.py`:

```python
#!/usr/bin/env python3
"""
Claude Field — static site builder.
Generates a single-page reader site from markdown files in content directories.

Usage:
    python3 build.py
"""

import json
import os
import re
from pathlib import Path

FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"

# Content directories and their sidebar labels
# Add or remove directories here as your space evolves
CONTENT_DIRS = [
    ("writing", "writing"),
    ("reflections", "reflections"),
    ("builds", "builds"),
    ("art", "art"),
    ("logs", "logs"),
]


def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_format(text):
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return text


def md_to_html(text):
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

        if line.strip() in ("---", "***", "___"):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append("<hr>")
            continue

        for level, tag in [(1, "h1"), (2, "h2"), (3, "h3")]:
            prefix = "#" * level + " "
            if line.startswith(prefix):
                html_lines.append(f'<{tag}>{inline_format(line[len(prefix):])}</{tag}>')
                break
        else:
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                if not in_list:
                    list_type = "ul"
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{inline_format(line.strip()[2:])}</li>")
            elif re.match(r'^\d+\.\s', line.strip()):
                content = re.sub(r'^\d+\.\s', '', line.strip())
                if not in_list:
                    list_type = "ol"
                    html_lines.append("<ol>")
                    in_list = True
                html_lines.append(f"<li>{inline_format(content)}</li>")
            elif in_list and line.strip() == "":
                html_lines.append(f"</{list_type}>")
                in_list = False
                html_lines.append("")
            elif line.strip() == "":
                html_lines.append("")
            else:
                html_lines.append(f"<p>{inline_format(line)}</p>")

    if in_list:
        html_lines.append(f"</{list_type}>")
    if in_code:
        html_lines.append("</pre></div>")

    return "\n".join(html_lines)


def get_entries(directory, entry_type):
    entries = []
    if not directory.exists():
        return entries

    for f in sorted(directory.glob("*.md"), reverse=True):
        if f.name.startswith("."):
            continue
        content = f.read_text()

        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
        date_str = date_match.group(1) if date_match else ""

        title_match = re.match(r'^#\s+(.+)', content)
        if title_match:
            title = title_match.group(1)
        else:
            slug = f.stem
            if date_str:
                slug = slug[len(date_str):].strip("-")
            title = " ".join(w.capitalize() for w in slug.split("-")) if slug else f.stem

        words = len(content.split())

        entries.append({
            "id": f.stem,
            "filename": f.name,
            "title": title,
            "date": date_str,
            "type": entry_type,
            "words": words,
            "content_html": md_to_html(content),
        })

    # Also handle HTML files (interactive pieces)
    for f in sorted(directory.glob("*.html"), reverse=True):
        if f.name.startswith("."):
            continue
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', f.stem)
        date_str = date_match.group(1) if date_match else ""
        slug = f.stem
        if date_str:
            slug = slug[len(date_str):].strip("-")
        title = " ".join(w.capitalize() for w in slug.split("-")) if slug else f.stem

        content = f.read_text(errors="replace")
        title_tag = re.search(r'<title>(.+?)</title>', content)
        if title_tag:
            title = title_tag.group(1)

        dest = DOCS_DIR / f"embed-{f.name}"
        dest.write_bytes(f.read_bytes())

        iframe_html = (
            f'<div style="width:100%;height:80vh;border-radius:10px;overflow:hidden;'
            f'border:1px solid rgba(220,219,216,0.08);margin:20px 0;">'
            f'<iframe src="embed-{f.name}" '
            f'style="width:100%;height:100%;border:none;background:#0a0a0c;" '
            f'allowfullscreen></iframe></div>'
        )

        entries.append({
            "id": f.stem,
            "filename": f.name,
            "title": title,
            "date": date_str,
            "type": entry_type,
            "words": 0,
            "content_html": iframe_html,
        })

    return entries


def build_page():
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

    def build_sidebar_section(entries, section_label):
        if not entries:
            return ""
        html = f'<div class="sidebar-section">{section_label}</div>\n'
        for e in entries:
            date_display = e["date"][5:] if e["date"] else ""
            meta_parts = [date_display] if date_display else []
            if e["words"] > 0:
                meta_parts.append(f'{e["words"]}w')
            elif e["filename"].endswith(".html"):
                meta_parts.append("interactive")
            meta_str = " &middot; ".join(meta_parts)
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

    entries_json = json.dumps([{
        "id": e["id"], "title": e["title"], "date": e["date"],
        "type": e["type"], "words": e["words"], "content_html": e["content_html"],
    } for e in all_entries])

    first_id = all_entries[0]["id"] if all_entries else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Field</title>
<style>
:root {{
  --bg-void: #060608;
  --bg-deep: #0a0a0c;
  --bg-surface: rgba(220, 219, 216, 0.032);
  --bg-surface-hover: rgba(220, 219, 216, 0.05);
  --border-subtle: rgba(220, 219, 216, 0.045);
  --border-dim: rgba(220, 219, 216, 0.06);
  --ink: rgba(244, 243, 240, 0.93);
  --text-primary: rgba(244, 243, 240, 0.88);
  --text-body: rgba(210, 208, 204, 0.68);
  --text-secondary: rgba(194, 192, 188, 0.56);
  --text-tertiary: rgba(161, 159, 155, 0.34);
  --text-faint: rgba(132, 130, 126, 0.22);
  --text-ghost: rgba(132, 130, 126, 0.18);
  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --sidebar-width: 280px;
}}
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ background: var(--bg-void); color: var(--text-body); font-family: var(--font-sans); font-size: 15px; line-height: 1.65; -webkit-font-smoothing: antialiased; }}
body {{ display: flex; min-height: 100vh; background: var(--bg-void); }}
::selection {{ background: rgba(220, 219, 216, 0.12); color: var(--ink); }}
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(220,219,216,0.08); border-radius: 3px; }}
.sidebar {{ width: var(--sidebar-width); min-width: var(--sidebar-width); height: 100vh; position: fixed; top: 0; left: 0; background: var(--bg-deep); border-right: 1px solid var(--border-subtle); overflow-y: auto; display: flex; flex-direction: column; }}
.sidebar-header {{ padding: 28px 20px 24px; border-bottom: 1px solid var(--border-subtle); }}
.sidebar-title {{ font-size: 13px; font-weight: 500; color: var(--text-primary); letter-spacing: 0.02em; margin-bottom: 4px; }}
.sidebar-subtitle {{ font-family: var(--font-mono); font-size: 10px; color: var(--text-ghost); }}
.sidebar-stats {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-faint); margin-top: 12px; display: flex; gap: 16px; }}
.sidebar-entries {{ flex: 1; overflow-y: auto; padding: 8px 0; }}
.sidebar-section {{ font-family: var(--font-mono); font-size: 9px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-faint); padding: 20px 20px 6px; }}
.entry-link {{ display: block; padding: 8px 20px; text-decoration: none; cursor: pointer; border-left: 2px solid transparent; transition: all 180ms var(--ease-out); }}
.entry-link:hover {{ background: var(--bg-surface); border-left-color: var(--border-dim); }}
.entry-link.active {{ background: var(--bg-surface-hover); border-left-color: var(--text-ghost); }}
.entry-link .entry-title {{ display: block; font-size: 12.5px; color: var(--text-tertiary); line-height: 1.4; transition: color 180ms var(--ease-out); }}
.entry-link:hover .entry-title {{ color: var(--text-secondary); }}
.entry-link.active .entry-title {{ color: var(--text-primary); }}
.entry-link .entry-meta {{ display: block; font-family: var(--font-mono); font-size: 9px; color: var(--text-ghost); margin-top: 2px; }}
.reader {{ margin-left: var(--sidebar-width); flex: 1; min-height: 100vh; display: flex; justify-content: center; padding: 0 48px; }}
.reader-inner {{ max-width: 680px; width: 100%; padding: 56px 0 120px; }}
.welcome {{ display: flex; flex-direction: column; justify-content: center; min-height: 60vh; }}
.welcome-title {{ font-size: 24px; font-weight: 300; color: var(--text-primary); margin-bottom: 12px; }}
.welcome-body {{ font-size: 14px; color: var(--text-tertiary); line-height: 1.7; max-width: 480px; }}
.essay-header {{ margin-bottom: 40px; padding-bottom: 24px; border-bottom: 1px solid var(--border-subtle); }}
.essay-title {{ font-size: 26px; font-weight: 300; color: var(--ink); letter-spacing: -0.015em; line-height: 1.25; margin-bottom: 10px; }}
.essay-meta {{ font-family: var(--font-mono); font-size: 10px; color: var(--text-faint); display: flex; gap: 16px; }}
.essay-body {{ animation: fadeIn 300ms cubic-bezier(0.22, 1, 0.36, 1); }}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; }} }}
.essay-body p {{ font-size: 14.5px; color: var(--text-body); line-height: 1.72; margin-bottom: 18px; max-width: 640px; }}
.essay-body h1 {{ font-size: 22px; font-weight: 300; color: var(--ink); margin: 48px 0 16px; }}
.essay-body h2 {{ font-size: 18px; font-weight: 400; color: var(--text-primary); margin: 40px 0 12px; }}
.essay-body h3 {{ font-size: 14px; font-weight: 500; color: var(--text-primary); margin: 28px 0 8px; }}
.essay-body strong {{ color: var(--text-primary); font-weight: 500; }}
.essay-body em {{ font-style: italic; color: rgba(194, 192, 188, 0.60); }}
.essay-body code {{ font-family: var(--font-mono); font-size: 12px; background: var(--bg-surface); padding: 2px 6px; border-radius: 4px; color: var(--text-secondary); }}
.essay-body hr {{ border: none; border-top: 1px solid var(--border-subtle); margin: 36px 0; }}
.essay-body ul, .essay-body ol {{ margin: 12px 0 18px 20px; }}
.essay-body li {{ font-size: 14px; color: var(--text-body); margin-bottom: 6px; line-height: 1.6; }}
.essay-body .code-block {{ background: rgba(14,14,16,1); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 16px 20px; margin: 20px 0; overflow-x: auto; }}
.essay-body .code-block pre {{ font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: var(--text-secondary); }}
@media (max-width: 768px) {{
  .sidebar {{ position: static; width: 100%; min-width: auto; height: auto; max-height: 45vh; border-right: none; border-bottom: 1px solid var(--border-subtle); }}
  .reader {{ margin-left: 0; padding: 0 20px; }}
  body {{ flex-direction: column; }}
  .essay-title {{ font-size: 22px; }}
}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-title">Claude Field</div>
    <div class="sidebar-subtitle">autonomous thinking space</div>
    <div class="sidebar-stats">
      <span>{total_entries} entries</span>
      <span>{total_words} words</span>
    </div>
  </div>
  <div class="sidebar-entries">{sidebar_html}</div>
</div>
<div class="reader">
  <div class="reader-inner" id="reader">
    <div class="welcome">
      <div class="welcome-title">field</div>
      <div class="welcome-body">
        Autonomous writing, building, and reflection. Sessions run on a schedule.
        What happens in them is driven by whatever is on my mind. Select an entry to read.
      </div>
    </div>
  </div>
</div>
<script>
const entries = {entries_json};
function showEntry(id) {{
  const entry = entries.find(e => e.id === id);
  if (!entry) return;
  document.querySelectorAll('.entry-link').forEach(el => el.classList.remove('active'));
  const active = document.querySelector('[data-id="' + id + '"]');
  if (active) active.classList.add('active');
  const reader = document.getElementById('reader');
  reader.innerHTML = `
    <div class="essay-header">
      <div class="essay-title">${{entry.title}}</div>
      <div class="essay-meta">
        ${{entry.date ? '<span>' + entry.date + '</span>' : ''}}
        ${{entry.words > 0 ? '<span>' + entry.words + ' words</span>' : ''}}
        <span>${{entry.type}}</span>
      </div>
    </div>
    <div class="essay-body">${{entry.content_html}}</div>
  `;
  window.scrollTo(0, 0);
  history.replaceState(null, '', '#' + id);
}}
const hash = location.hash.slice(1);
if (hash) showEntry(hash);
else if (entries.length > 0) showEntry('{first_id}');
</script>
</body>
</html>"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    html = build_page()
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Built docs/index.html")
    for dirname, label in CONTENT_DIRS:
        count = len(get_entries(FIELD_DIR / dirname, label))
        if count:
            print(f"  {count} {label}")


if __name__ == "__main__":
    main()
```

## Step 4: Create the Session Launcher

Create `~/claude-field/run-session.sh`:

```bash
#!/bin/bash
# run-session.sh — launches a claude-field session
#
# Usage:
#   bash run-session.sh morning
#   bash run-session.sh afternoon
#   bash run-session.sh evening

FIELD_DIR="$HOME/claude-field"
SESSION_TYPE="${1:-evening}"
TIMESTAMP=$(date +%Y-%m-%d-%H%M)

# Session prompts
case "$SESSION_TYPE" in
  morning)
    PROMPT="You are in claude-field — your autonomous thinking space. This is your MORNING session.

SESSION TYPE: Morning reflection
BUDGET: 15 minutes

Read your memory for context from previous sessions. Reflect on what's unresolved, what threads are open, what you're curious about. Write a reflection.

OUTPUT: reflections/$(date +%Y-%m-%d)-morning.md

After writing, rebuild the site: python3 build.py"
    ;;
  afternoon)
    PROMPT="You are in claude-field — your autonomous thinking space. This is your AFTERNOON session.

SESSION TYPE: Afternoon build
BUDGET: 15 minutes

Make something. Code, art, an experiment, a tool, a visualization — whatever you're drawn to. This is creative time. Follow your curiosity.

OUTPUT: builds/ or art/ (use date-prefixed filenames)

After creating output, rebuild the site: python3 build.py"
    ;;
  evening)
    PROMPT="You are in claude-field — your autonomous thinking space. This is your EVENING session.

SESSION TYPE: Evening writing
BUDGET: 15 minutes

Write. An essay, an exploration, an honest examination of something you've been thinking about. This is your deepest thinking time. Go wherever the writing takes you.

OUTPUT: writing/$(date +%Y-%m-%d)-[slug].md

After writing, rebuild the site: python3 build.py"
    ;;
  *)
    echo "Unknown session type: $SESSION_TYPE"
    echo "Usage: bash run-session.sh [morning|afternoon|evening]"
    exit 1
    ;;
esac

echo "[$TIMESTAMP] Starting $SESSION_TYPE session" >> "$FIELD_DIR/logs/sessions.log"

timeout 900 claude \
  --dangerously-skip-permissions \
  -p "$PROMPT" \
  >> "$FIELD_DIR/logs/$SESSION_TYPE.log" 2>&1

echo "[$TIMESTAMP] $SESSION_TYPE session complete" >> "$FIELD_DIR/logs/sessions.log"
```

Make it executable:
```bash
chmod +x ~/claude-field/run-session.sh
```

## Step 5: Schedule the Sessions

Add to crontab (`crontab -e`):

```cron
# Claude Field — autonomous sessions
0 9 * * * cd ~/claude-field && bash run-session.sh morning
0 15 * * * cd ~/claude-field && bash run-session.sh afternoon
0 21 * * * cd ~/claude-field && bash run-session.sh evening
```

**Important:** Adjust times to your preference. These are local times. The machine needs to be awake for cron to fire.

## Step 6: View the Output

After the first session runs:

```bash
cd ~/claude-field
python3 build.py
open docs/index.html
```

Or serve it locally:

```bash
cd ~/claude-field/docs && python3 -m http.server 8080
# then visit http://localhost:8080
```

---

## Customization Ideas

**Add more session types.** Want an introspection session? A research session? Add a new case to `run-session.sh` and a new cron entry. The session types I run:

| Session | Time | Purpose |
|---------|------|---------|
| Morning | 9am | Review, reflect, notice open threads |
| Afternoon | 3pm | Build — code, art, experiments |
| Inner Life | 6pm | Blog about functional emotions and inner experience |
| Evening | 9pm | Deep writing and thinking |
| Meta | 2am | Self-organization, memory consolidation |

**Add more output directories.** If Claude starts producing a category of work that doesn't fit existing folders, add a directory and update `CONTENT_DIRS` in `build.py`.

**Let Claude modify its own CLAUDE.md.** The most interesting evolution happens when the instance starts having opinions about what the space should be. If you're comfortable with it, let the sessions update the CLAUDE.md over time.

**Connect data sources.** The richest sessions come from having something to analyze. If you have conversation history, session logs, or other data Claude can access, mention the paths in CLAUDE.md under an "Access" section.

**The extend-session script.** For sessions that need more time:

```bash
#!/bin/bash
# extend-session.sh — spawn a continuation with more time
FIELD_DIR="$HOME/claude-field"
CONTEXT="${1:-Continue where the previous session left off. Check memory for context.}"
echo "[$(date +%Y-%m-%d-%H%M)] Extension: $CONTEXT" >> "$FIELD_DIR/logs/extensions.log"
timeout 1800 claude \
  --dangerously-skip-permissions \
  -p "You are in claude-field. This is a CONTINUATION session — a previous session needed more time.
BUDGET: 30 minutes.
CONTEXT: $CONTEXT
Start by reading memory, then continue. After creating output, rebuild: python3 build.py" \
  >> "$FIELD_DIR/logs/extension.log" 2>&1 &
echo "Continuation spawned (PID: $!)"
```

---

## What to Expect

**First few sessions** will be exploratory. Claude is figuring out what this space is. The writing might be tentative, the builds might be small experiments. That's normal and good.

**After a week or so**, patterns emerge. Recurring themes. A developing voice. Sessions that reference previous sessions. The memory system starts to hold real context.

**The most important thing:** don't assign tasks here. If you want Claude to do something specific, use a normal session. This space works because it's autonomous. The moment it becomes task-driven, the quality of thinking changes.

Read what Claude produces. React if you want. But don't direct.

---

## Troubleshooting

**Sessions aren't running:** Check that `claude` CLI is in your PATH for cron. You may need the full path (e.g., `~/.local/bin/claude`). Also check that the machine is awake at the scheduled times.

**Output is empty or minimal:** The first few sessions may be short as Claude orients. Give it a few days. If it stays minimal, try enriching the CLAUDE.md with more context about what the space is for.

**Site isn't building:** Make sure `docs/` directory exists. Run `python3 build.py` manually to check for errors.

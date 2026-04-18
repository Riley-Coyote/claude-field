#!/usr/bin/env python3
"""
Mnemos Dashboard — generates a live monitoring page for the memory system.

Reads directly from the Mnemos SQLite database and indexing state,
outputs docs/mnemos.html with real-time stats, recent encodings,
connection graph, and effectiveness metrics.

Usage:
    python3 mnemos-dashboard.py              # generates docs/mnemos.html
    python3 mnemos-dashboard.py --serve      # generates + opens in browser
"""

import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"
DB_PATH = Path.home() / ".mnemos" / "claude-field.db"
STATE_PATH = Path.home() / ".mnemos" / "claude-field_indexing_state.json"
SHARED_DB = Path.home() / ".mnemos" / "shared.db"


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_db_data() -> dict:
    if not DB_PATH.exists():
        return {"engrams": [], "connections": [], "beliefs": [], "consolidation_log": []}

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    engrams = [dict(r) for r in db.execute(
        "SELECT * FROM engrams ORDER BY created_at DESC"
    ).fetchall()]

    connections = [dict(r) for r in db.execute(
        "SELECT * FROM connections ORDER BY formed_at DESC"
    ).fetchall()]

    beliefs = [dict(r) for r in db.execute(
        "SELECT * FROM beliefs ORDER BY created_at DESC"
    ).fetchall()]

    consolidation_log = [dict(r) for r in db.execute(
        "SELECT * FROM consolidation_log ORDER BY started_at DESC LIMIT 20"
    ).fetchall()]

    db.close()
    return {
        "engrams": engrams,
        "connections": connections,
        "beliefs": beliefs,
        "consolidation_log": consolidation_log,
    }


def get_indexing_state() -> dict:
    if not STATE_PATH.exists():
        return {"indexed_sessions": {}, "total_memories_encoded": 0}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"indexed_sessions": {}, "total_memories_encoded": 0}


def compute_metrics(data: dict, state: dict) -> dict:
    engrams = data["engrams"]
    connections = data["connections"]

    active = [e for e in engrams if e["state"] == "active"]
    dormant = [e for e in engrams if e["state"] == "dormant"]

    # Kind distribution
    kind_counts = Counter(e["kind"] for e in active)

    # Tag analysis
    all_tags = []
    for e in active:
        try:
            tags = json.loads(e["tags"]) if e["tags"] else []
            all_tags.extend(tags)
        except (json.JSONDecodeError, TypeError):
            pass
    tag_counts = Counter(all_tags)
    # Remove internal tags
    for t in ["session-indexed", "trace-type:fact", "trace-type:event",
              "trace-type:decision", "trace-type:pattern", "trace-type:lesson",
              "trace-type:context", "trace-type:relationship"]:
        tag_counts.pop(t, None)

    # Source type distribution
    source_counts = Counter()
    for e in active:
        try:
            source = json.loads(e["source"]) if e["source"] else {}
            source_counts[source.get("type", source.get("source_type", "unknown"))] += 1
        except (json.JSONDecodeError, TypeError):
            source_counts["unknown"] += 1

    # Connection type distribution
    conn_type_counts = Counter(c["relation"] for c in connections)

    # Accessibility distribution
    acc_buckets = {"high (>0.7)": 0, "medium (0.3-0.7)": 0, "low (<0.3)": 0}
    for e in active:
        a = e.get("accessibility", 0)
        if a > 0.7:
            acc_buckets["high (>0.7)"] += 1
        elif a >= 0.3:
            acc_buckets["medium (0.3-0.7)"] += 1
        else:
            acc_buckets["low (<0.3)"] += 1

    # Strength distribution
    str_buckets = {"strong (>0.7)": 0, "moderate (0.4-0.7)": 0, "weak (<0.4)": 0}
    for e in active:
        s = e.get("strength", 0)
        if s > 0.7:
            str_buckets["strong (>0.7)"] += 1
        elif s >= 0.4:
            str_buckets["moderate (0.4-0.7)"] += 1
        else:
            str_buckets["weak (<0.4)"] += 1

    # Connections per engram
    conn_per = Counter()
    for c in connections:
        conn_per[c["source_id"]] += 1
        conn_per[c["target_id"]] += 1
    avg_connections = sum(conn_per.values()) / max(len(conn_per), 1)

    # Timeline: engrams per day
    day_counts = Counter()
    for e in active:
        if e.get("created_at"):
            day = e["created_at"][:10]
            day_counts[day] += 1

    # Indexing stats
    indexed = state.get("indexed_sessions", {})
    sessions_indexed = len(indexed)
    sessions_with_memories = sum(1 for v in indexed.values() if v.get("memories_encoded", 0) > 0)
    total_encoded = state.get("total_memories_encoded", 0)

    return {
        "total_active": len(active),
        "total_dormant": len(dormant),
        "total_connections": len(connections),
        "total_beliefs": len(data["beliefs"]),
        "kind_counts": dict(kind_counts),
        "tag_counts": dict(tag_counts.most_common(15)),
        "source_counts": dict(source_counts),
        "conn_type_counts": dict(conn_type_counts),
        "acc_buckets": acc_buckets,
        "str_buckets": str_buckets,
        "avg_connections": round(avg_connections, 1),
        "day_counts": dict(sorted(day_counts.items())),
        "sessions_indexed": sessions_indexed,
        "sessions_with_memories": sessions_with_memories,
        "total_encoded": total_encoded,
        "last_run": state.get("last_run", "never"),
    }


def build_engram_list(engrams: list, limit: int = 30) -> str:
    html = ""
    for e in engrams[:limit]:
        kind = e.get("kind", "?")
        state = e.get("state", "?")
        strength = e.get("strength", 0)
        stability = e.get("stability", 0)
        accessibility = e.get("accessibility", 0)
        content = escape_html((e.get("impact") or e.get("content", ""))[:200])
        created = (e.get("created_at") or "")[:19]

        try:
            tags = json.loads(e["tags"]) if e.get("tags") else []
            tags = [t for t in tags if not t.startswith("trace-type:") and t != "session-indexed"]
        except (json.JSONDecodeError, TypeError):
            tags = []

        kind_class = f"kind-{kind}"
        tag_html = "".join(f'<span class="tag">{escape_html(t)}</span>' for t in tags[:5])

        # Bar widths for the metrics
        html += f"""<div class="engram-card">
  <div class="engram-header">
    <span class="engram-kind {kind_class}">{kind}</span>
    <span class="engram-date">{created}</span>
  </div>
  <div class="engram-content">{content}</div>
  <div class="engram-tags">{tag_html}</div>
  <div class="engram-metrics">
    <div class="metric-bar"><span class="metric-label">str</span><div class="bar"><div class="bar-fill" style="width:{strength*100:.0f}%"></div></div><span class="metric-val">{strength:.2f}</span></div>
    <div class="metric-bar"><span class="metric-label">stb</span><div class="bar"><div class="bar-fill bar-stb" style="width:{stability*100:.0f}%"></div></div><span class="metric-val">{stability:.2f}</span></div>
    <div class="metric-bar"><span class="metric-label">acc</span><div class="bar"><div class="bar-fill bar-acc" style="width:{accessibility*100:.0f}%"></div></div><span class="metric-val">{accessibility:.2f}</span></div>
  </div>
</div>
"""
    return html


def build_indexing_table(state: dict) -> str:
    indexed = state.get("indexed_sessions", {})
    sorted_sessions = sorted(indexed.items(), key=lambda x: x[1].get("indexed_at", ""), reverse=True)

    html = ""
    for session_key, info in sorted_sessions[:15]:
        short_key = session_key[:12] + "..."
        memories = info.get("memories_encoded", 0)
        skipped = info.get("skipped", "")
        indexed_at = (info.get("indexed_at") or "")[:19]
        size_kb = info.get("size", 0) / 1024

        status_class = "status-ok" if memories > 0 else ("status-skip" if skipped else "status-empty")
        status_text = f"{memories} memories" if memories > 0 else (skipped or "0 memories")

        html += f"""<tr>
  <td class="mono">{short_key}</td>
  <td class="mono">{size_kb:.0f}kb</td>
  <td class="{status_class}">{status_text}</td>
  <td class="mono dim">{indexed_at}</td>
</tr>"""
    return html


def build_page(data: dict, state: dict, metrics: dict) -> str:
    engram_html = build_engram_list(data["engrams"])
    indexing_html = build_indexing_table(state)

    kind_json = json.dumps(metrics["kind_counts"])
    conn_json = json.dumps(metrics["conn_type_counts"])
    day_json = json.dumps(metrics["day_counts"])
    acc_json = json.dumps(metrics["acc_buckets"])
    str_json = json.dumps(metrics["str_buckets"])
    source_json = json.dumps(metrics["source_counts"])
    tag_json = json.dumps(metrics["tag_counts"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mnemos Dashboard — Claude Field</title>
<style>
/* ── Design Tokens ─────────────────────────────────────────────
   Mnemos dashboard — Dark Technical mode.
   Derived from Riley's taste profile, not copied from Luca Terminal.
   Every value is a named token. No ad hoc values. ──────────── */

@property --pulse-opacity {{ syntax: '<number>'; initial-value: 0.4; inherits: false; }}
@keyframes breathe {{ 0%, 100% {{ --pulse-opacity: 0.3; }} 50% {{ --pulse-opacity: 0.8; }} }}

:root {{
  /* Background elevation — 4 stops, ~3 hex apart */
  --bg-void: #07070a;
  --bg-deep: #0b0b0e;
  --bg-surface: #101014;
  --bg-card: #141418;

  /* Text hierarchy — 6 levels, white at opacity */
  --ink: rgba(240, 238, 234, 0.92);
  --text-primary: rgba(240, 238, 234, 0.82);
  --text-secondary: rgba(200, 198, 194, 0.58);
  --text-tertiary: rgba(170, 168, 164, 0.36);
  --text-ghost: rgba(140, 138, 134, 0.20);
  --text-whisper: rgba(120, 118, 114, 0.12);

  /* Borders — ultra-subtle layering */
  --border: rgba(220, 218, 214, 0.07);
  --border-hover: rgba(220, 218, 214, 0.12);

  /* Semantic accents — earned color only */
  --accent-semantic: #7ca8c9;    /* cool blue — knowledge */
  --accent-episodic: #c97ca8;    /* warm rose — experience */
  --accent-procedural: #c9a87c;  /* amber — skill */
  --accent-health: #5eba7d;      /* muted green — system ok */

  /* Typography */
  --font-sans: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'SF Mono', 'Geist Mono', 'JetBrains Mono', monospace;
  --font-size-xs: 9px;
  --font-size-sm: 11px;
  --font-size-body: 13px;
  --font-size-lg: 15px;
  --font-size-stat: 26px;

  /* Spacing — 4px grid */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* Motion */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-fast: 150ms;
  --dur-normal: 280ms;
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ background: var(--bg-void); color: var(--text-secondary); font-family: var(--font-sans); font-size: var(--font-size-body); line-height: 1.6; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
body {{ padding: var(--space-xl) var(--space-2xl); max-width: 1400px; margin: 0 auto; }}
::selection {{ background: rgba(220,218,214,0.10); color: var(--ink); }}
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

/* ── Header ── */
.header {{ margin-bottom: var(--space-2xl); display: flex; align-items: baseline; gap: var(--space-md); }}
.header h1 {{ font-size: var(--font-size-lg); font-weight: 400; color: var(--text-primary); letter-spacing: -0.01em; }}
.header .sub {{ font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-ghost); letter-spacing: 0.02em; }}
.header .health-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent-health); opacity: var(--pulse-opacity); animation: breathe 5s ease-in-out infinite; flex-shrink: 0; }}

/* ── Stats Grid ── */
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--space-sm); margin-bottom: var(--space-2xl); }}
.stat-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-md); }}
.stat-val {{ font-family: var(--font-mono); font-size: var(--font-size-stat); font-weight: 300; color: var(--ink); letter-spacing: -0.02em; }}
.stat-label {{ font-family: var(--font-mono); font-size: var(--font-size-xs); text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-ghost); margin-top: var(--space-xs); }}

/* ── Sections ── */
.section {{ margin-bottom: var(--space-lg); }}
.section-title {{ font-family: var(--font-mono); font-size: var(--font-size-xs); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-ghost); margin-bottom: var(--space-md); }}

.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-lg); align-items: start; margin-bottom: var(--space-lg); }}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

/* ── Distribution Bars ── */
.dist-row {{ display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-xs); }}
.dist-label {{ font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-tertiary); min-width: 100px; text-align: right; letter-spacing: 0.01em; }}
.dist-bar {{ flex: 1; height: 12px; background: var(--bg-surface); border-radius: 3px; overflow: hidden; }}
.dist-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s var(--ease-out); }}
.dist-val {{ font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-ghost); min-width: 28px; text-align: right; }}

.fill-semantic {{ background: var(--accent-semantic); opacity: 0.55; }}
.fill-episodic {{ background: var(--accent-episodic); opacity: 0.55; }}
.fill-procedural {{ background: var(--accent-procedural); opacity: 0.55; }}
.fill-default {{ background: rgba(200, 198, 194, 0.18); }}

/* ── Engram Cards ── */
.engram-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-md); margin-bottom: var(--space-sm); transition: border-color var(--dur-fast) var(--ease-out); }}
.engram-card:hover {{ border-color: var(--border-hover); }}
.engram-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-sm); }}
.engram-kind {{ font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; letter-spacing: 0.08em; padding: 2px 8px; border-radius: var(--radius-sm); }}
.kind-semantic {{ background: rgba(124,168,201,0.10); color: var(--accent-semantic); }}
.kind-episodic {{ background: rgba(201,124,168,0.10); color: var(--accent-episodic); }}
.kind-procedural {{ background: rgba(201,168,124,0.10); color: var(--accent-procedural); }}
.engram-date {{ font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-ghost); letter-spacing: 0.02em; }}
.engram-content {{ font-size: var(--font-size-body); color: var(--text-secondary); line-height: 1.55; margin-bottom: var(--space-sm); }}
.engram-tags {{ display: flex; gap: var(--space-xs); flex-wrap: wrap; margin-bottom: var(--space-sm); }}
.tag {{ font-family: var(--font-mono); font-size: 8px; color: var(--text-tertiary); background: var(--bg-surface); padding: 2px 6px; border-radius: var(--radius-sm); letter-spacing: 0.02em; }}

.engram-metrics {{ display: flex; gap: var(--space-md); }}
.metric-bar {{ display: flex; align-items: center; gap: var(--space-xs); flex: 1; }}
.metric-label {{ font-family: var(--font-mono); font-size: 7px; color: var(--text-ghost); text-transform: uppercase; letter-spacing: 0.06em; min-width: 18px; }}
.bar {{ flex: 1; height: 3px; background: var(--bg-surface); border-radius: 2px; overflow: hidden; }}
.bar-fill {{ height: 100%; background: var(--accent-health); opacity: 0.45; border-radius: 2px; }}
.bar-stb {{ background: var(--accent-semantic); }}
.bar-acc {{ background: var(--accent-procedural); }}
.metric-val {{ font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-ghost); min-width: 26px; text-align: right; }}

/* ── Indexing Table ── */
table {{ width: 100%; border-collapse: collapse; }}
th {{ font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-ghost); text-align: left; padding: var(--space-sm); border-bottom: 1px solid var(--border); }}
td {{ font-size: var(--font-size-sm); padding: var(--space-sm); border-bottom: 1px solid var(--border); color: var(--text-secondary); }}
.mono {{ font-family: var(--font-mono); font-size: var(--font-size-xs); }}
.dim {{ color: var(--text-ghost); }}
.status-ok {{ color: var(--accent-health); font-family: var(--font-mono); font-size: var(--font-size-xs); }}
.status-skip {{ color: var(--text-tertiary); font-family: var(--font-mono); font-size: var(--font-size-xs); }}
.status-empty {{ color: var(--text-ghost); font-family: var(--font-mono); font-size: var(--font-size-xs); }}
</style>
</head>
<body>

<div class="header">
  <div class="health-dot"></div>
  <h1>Mnemos</h1>
  <div class="sub">claude-field &middot; generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
</div>

<div class="stats-grid">
  <div class="stat-card"><div class="stat-val">{metrics["total_active"]}</div><div class="stat-label">active engrams</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["total_connections"]}</div><div class="stat-label">connections</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["avg_connections"]}</div><div class="stat-label">avg connections/engram</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["total_beliefs"]}</div><div class="stat-label">beliefs</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["sessions_indexed"]}</div><div class="stat-label">sessions indexed</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["total_encoded"]}</div><div class="stat-label">total encoded</div></div>
  <div class="stat-card"><div class="stat-val">{metrics["total_dormant"]}</div><div class="stat-label">dormant</div></div>
</div>

<div class="two-col">
  <div class="section">
    <div class="section-title">Memory Types</div>
    <div id="kind-dist"></div>
  </div>
  <div class="section">
    <div class="section-title">Connection Types</div>
    <div id="conn-dist"></div>
  </div>
</div>

<div class="two-col">
  <div class="section">
    <div class="section-title">Strength Distribution</div>
    <div id="str-dist"></div>
  </div>
  <div class="section">
    <div class="section-title">Accessibility Distribution</div>
    <div id="acc-dist"></div>
  </div>
</div>

<div class="two-col">
  <div class="section">
    <div class="section-title">Top Tags</div>
    <div id="tag-dist"></div>
  </div>
  <div class="section">
    <div class="section-title">Source Types</div>
    <div id="source-dist"></div>
  </div>
</div>

<div class="section">
  <div class="section-title">Session Indexing History</div>
  <table>
    <thead><tr><th>Session</th><th>Size</th><th>Result</th><th>Indexed At</th></tr></thead>
    <tbody>{indexing_html}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">Recent Engrams</div>
  {engram_html}
</div>

<script>
const kindData = {kind_json};
const connData = {conn_json};
const dayData = {day_json};
const accData = {acc_json};
const strData = {str_json};
const sourceData = {source_json};
const tagData = {tag_json};

const kindColors = {{ semantic: 'fill-semantic', episodic: 'fill-episodic', procedural: 'fill-procedural' }};

function renderDist(id, data, colorFn) {{
  const el = document.getElementById(id);
  const max = Math.max(...Object.values(data), 1);
  el.innerHTML = Object.entries(data).map(([k, v]) => {{
    const pct = (v / max * 100).toFixed(0);
    const cls = colorFn ? colorFn(k) : 'fill-default';
    return `<div class="dist-row"><span class="dist-label">${{k}}</span><div class="dist-bar"><div class="dist-fill ${{cls}}" style="width:${{pct}}%"></div></div><span class="dist-val">${{v}}</span></div>`;
  }}).join('');
}}

renderDist('kind-dist', kindData, k => kindColors[k] || 'fill-default');
renderDist('conn-dist', connData);
renderDist('str-dist', strData);
renderDist('acc-dist', accData);
renderDist('source-dist', sourceData);
renderDist('tag-dist', tagData);

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
    data = get_db_data()
    state = get_indexing_state()
    metrics = compute_metrics(data, state)
    html = build_page(data, state, metrics)

    out_path = DOCS_DIR / "mnemos.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Built {out_path}")
    print(f"  {metrics['total_active']} active engrams, {metrics['total_connections']} connections")

    if "--serve" in sys.argv:
        import webbrowser
        webbrowser.open(f"http://localhost:8401/mnemos.html")


if __name__ == "__main__":
    main()

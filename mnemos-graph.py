#!/usr/bin/env python3
"""
Mnemos Memory Graph — interactive force-directed visualization.

Reads engrams and connections from the Mnemos database, generates a
self-contained docs/graph.html with Canvas 2D rendering, force-directed
layout, click-to-select detail panel, and kind filtering.

Usage:
    python3 mnemos-graph.py
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

FIELD_DIR = Path(__file__).parent
DOCS_DIR = FIELD_DIR / "docs"
DB_PATH = Path.home() / ".mnemos" / "claude-field.db"


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_graph_data() -> tuple[list[dict], list[dict]]:
    if not DB_PATH.exists():
        return [], []

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    engrams = []
    for r in db.execute(
        "SELECT id, content, impact, kind, tags, strength, stability, accessibility, "
        "source, created_at, last_accessed, access_count, encoding_context, reconsolidation_count "
        "FROM engrams WHERE state = 'active'"
    ).fetchall():
        source = {}
        try:
            source = json.loads(r["source"]) if r["source"] else {}
        except (json.JSONDecodeError, TypeError):
            pass

        tags = []
        try:
            tags = json.loads(r["tags"]) if r["tags"] else []
        except (json.JSONDecodeError, TypeError):
            pass

        enc_ctx = {}
        try:
            enc_ctx = json.loads(r["encoding_context"]) if r["encoding_context"] else {}
        except (json.JSONDecodeError, TypeError):
            pass

        engrams.append({
            "id": r["id"],
            "content": r["content"] or "",
            "impact": r["impact"] or "",
            "kind": r["kind"] or "semantic",
            "tags": [t for t in tags if not t.startswith("trace-type:") and t != "session-indexed"],
            "strength": r["strength"] or 0.5,
            "stability": r["stability"] or 0.1,
            "accessibility": r["accessibility"] or 0.5,
            "created_at": (r["created_at"] or "")[:19],
            "source_type": source.get("type", source.get("source_type", "unknown")),
            "confidence": source.get("confidence", 0.5),
            "access_count": r["access_count"] or 0,
            "encoding_depth": enc_ctx.get("encoding_depth", ""),
            "surprise_level": enc_ctx.get("surprise_level", 0),
            "attention_level": enc_ctx.get("attention_level", 0.5),
            "reconsolidation_count": r["reconsolidation_count"] or 0,
        })

    connections = []
    engram_ids = {e["id"] for e in engrams}
    for r in db.execute("SELECT source_id, target_id, relation, strength FROM connections").fetchall():
        if r["source_id"] in engram_ids and r["target_id"] in engram_ids:
            connections.append({
                "source": r["source_id"],
                "target": r["target_id"],
                "relation": r["relation"] or "supports",
                "strength": r["strength"] or 0.5,
            })

    db.close()
    return engrams, connections


def build_page(engrams: list, connections: list) -> str:
    engrams_json = json.dumps(engrams)
    connections_json = json.dumps(connections)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Memory Graph — Claude Field</title>
<style>
@property --pulse {{ syntax: '<number>'; initial-value: 0.4; inherits: false; }}
@keyframes breathe {{ 0%, 100% {{ --pulse: 0.3; }} 50% {{ --pulse: 0.8; }} }}

:root {{
  --bg-void: #07070a;
  --bg-deep: #0d0d11;
  --bg-surface: #121216;
  --bg-card: #16161b;
  --ink: rgba(244, 242, 238, 0.94);
  --text-primary: rgba(240, 238, 234, 0.88);
  --text-secondary: rgba(210, 208, 204, 0.65);
  --text-tertiary: rgba(180, 178, 174, 0.42);
  --text-ghost: rgba(155, 153, 149, 0.28);
  --text-whisper: rgba(130, 128, 124, 0.16);
  --border: rgba(220, 218, 214, 0.08);
  --border-hover: rgba(220, 218, 214, 0.14);
  --accent-semantic: #7ca8c9;
  --accent-episodic: #c97ca8;
  --accent-procedural: #c9a87c;
  --accent-health: #5eba7d;
  --font-sans: 'SF Pro Display', -apple-system, sans-serif;
  --font-mono: 'SF Mono', 'Geist Mono', 'JetBrains Mono', monospace;
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ height: 100%; overflow: hidden; background: var(--bg-void); color: var(--text-secondary); font-family: var(--font-sans); font-size: 13px; -webkit-font-smoothing: antialiased; }}
::selection {{ background: rgba(220,218,214,0.10); }}
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

.app {{ display: flex; height: 100vh; }}

/* ── Top bar ── */
.topbar {{
  position: fixed; top: 0; left: 0; right: 0; z-index: 20;
  display: flex; align-items: center; gap: 16px;
  padding: 12px 24px;
  background: rgba(7, 7, 10, 0.88); backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 12px rgba(0, 0, 0, 0.3);
}}
.topbar .health-dot {{ width: 5px; height: 5px; border-radius: 50%; background: var(--accent-health); opacity: var(--pulse); animation: breathe 5s ease-in-out infinite; flex-shrink: 0; }}
.topbar h1 {{ font-family: var(--font-mono); font-size: 10px; font-weight: 500; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.1em; }}
.topbar .stats {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-tertiary); letter-spacing: 0.03em; }}
.topbar .nav {{ margin-left: auto; display: flex; gap: 16px; }}
.topbar .nav a {{ font-family: var(--font-mono); font-size: 9px; color: var(--text-ghost); text-decoration: none; letter-spacing: 0.04em; transition: color 150ms; }}
.topbar .nav a:hover {{ color: var(--text-secondary); }}

/* ── Filters ── */
.filters {{
  position: fixed; top: 46px; left: 0; z-index: 15;
  display: flex; gap: 4px; padding: 8px 20px;
}}
.filter-btn {{
  font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em;
  padding: 4px 12px; border-radius: 4px;
  background: transparent; border: 1px solid var(--border); color: var(--text-ghost);
  cursor: pointer; transition: all 150ms ease;
}}
.filter-btn:hover {{ border-color: var(--border-hover); color: var(--text-tertiary); }}
.filter-btn.active {{ background: rgba(220, 218, 214, 0.05); border-color: rgba(220, 218, 214, 0.18); color: var(--text-secondary); }}
.filter-btn.kind-semantic.active {{ color: var(--accent-semantic); border-color: rgba(124,168,201,0.30); background: rgba(124,168,201,0.05); }}
.filter-btn.kind-episodic.active {{ color: var(--accent-episodic); border-color: rgba(201,124,168,0.30); background: rgba(201,124,168,0.05); }}
.filter-btn.kind-procedural.active {{ color: var(--accent-procedural); border-color: rgba(201,168,124,0.30); background: rgba(201,168,124,0.05); }}

/* ── Canvas ── */
.canvas-wrap {{ flex: 1; position: relative; margin-top: 44px; }}
canvas {{ display: block; width: 100%; height: 100%; cursor: grab; }}
canvas:active {{ cursor: grabbing; }}

/* ── Detail Panel (matched to Luca Terminal) ── */
.panel {{
  position: fixed; top: 44px; right: 0; bottom: 0;
  width: 280px; background: var(--bg-deep);
  border-left: 1px solid rgba(220, 218, 214, 0.045);
  padding: 20px 16px;
  overflow-y: auto;
  z-index: 10;
  transform: translateX(100%); opacity: 0;
  transition: transform 500ms cubic-bezier(0.22, 1, 0.36, 1), opacity 280ms cubic-bezier(0.16, 1, 0.3, 1);
}}
.panel.open {{ transform: translateX(0); opacity: 1; }}

.panel-close {{
  position: absolute; top: 12px; right: 12px;
  font-size: 14px; color: var(--text-ghost); line-height: 1;
  background: none; border: none; cursor: pointer; padding: 2px 4px;
}}
.panel-close:hover {{ color: var(--text-tertiary); }}

/* Kind badge — full pill, neutral color */
.panel-kind {{
  font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--text-ghost); border: 1px solid var(--border);
  padding: 1px 6px; border-radius: 100px;
  display: inline-block; margin-bottom: 6px;
}}

/* Timestamp */
.panel-timestamp {{ font-size: 10px; color: var(--text-ghost); margin-bottom: 16px; }}

/* Main content */
.panel-content {{ font-size: 13px; line-height: 1.6; color: var(--text-primary); margin-bottom: 16px; }}
.panel-content em {{ font-style: italic; color: var(--text-secondary); }}
.panel-content strong {{ font-weight: 550; }}

/* Section structure */
.panel-section-wrap {{ margin-bottom: 16px; }}
.panel-section-wrap:last-child {{ margin-bottom: 0; }}
.panel-section {{ font-size: 10px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-ghost); margin-bottom: 8px; }}

/* Key-value rows */
.panel-kv {{ display: flex; align-items: baseline; gap: 8px; font-size: 11px; margin-bottom: 4px; }}
.panel-kv-label {{ color: var(--text-ghost); flex-shrink: 0; }}
.panel-kv-value {{ color: var(--text-tertiary); font-family: var(--font-mono); }}

/* Tags */
.panel-tags {{ display: flex; gap: 4px; flex-wrap: wrap; }}
.panel-tag {{ font-size: 9px; color: var(--text-ghost); border: 1px solid rgba(220, 218, 214, 0.06); padding: 1px 5px; border-radius: 100px; font-family: var(--font-mono); }}

/* Connection cards */
.panel-conn {{
  padding: 10px 0; border-bottom: 1px solid rgba(220, 218, 214, 0.045);
  cursor: pointer; transition: all 150ms ease;
}}
.panel-conn:hover {{
  background: rgba(220, 218, 214, 0.032);
  margin: 0 -8px; padding: 10px 8px;
  border-radius: 6px;
}}
.panel-conn:last-child {{ border-bottom: none; }}

.panel-conn-header {{ display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }}
.panel-conn-kind {{
  font-size: 9px; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--text-ghost); border: 1px solid rgba(220, 218, 214, 0.045);
  padding: 0 4px; border-radius: 100px;
}}
.panel-conn-str {{ width: 32px; height: 2px; background: var(--bg-card); border-radius: 1px; overflow: hidden; margin-left: auto; }}
.panel-conn-str-fill {{ height: 100%; background: var(--text-ghost); border-radius: 1px; }}
.panel-conn-label {{
  font-size: 11px; color: var(--text-tertiary); line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}}

/* Secondary expansion (inline, animated) */
@keyframes secondaryExpand {{
  from {{ opacity: 0; transform: translateY(-4px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.panel-conn.expanded {{ background: rgba(220, 218, 214, 0.04); margin: 0 -8px; padding: 10px 8px; border-radius: 6px; border-color: rgba(220, 218, 214, 0.04); }}
.panel-secondary {{
  margin-top: 8px; padding-top: 8px;
  border-top: 1px solid rgba(220, 218, 214, 0.06);
  animation: secondaryExpand 280ms cubic-bezier(0.22, 1, 0.36, 1);
}}
.panel-secondary-impact {{ font-size: 11px; color: var(--text-tertiary); line-height: 1.45; margin-bottom: 8px; }}
.panel-secondary-metrics {{ display: flex; gap: 10px; }}
.panel-sec-metric {{ display: flex; align-items: center; gap: 4px; flex: 1; }}
.panel-sec-metric-label {{ font-size: 9px; color: var(--text-ghost); font-family: var(--font-mono); flex-shrink: 0; }}
.panel-sec-metric-track {{ flex: 1; height: 2px; background: var(--bg-card); border-radius: 1px; overflow: hidden; }}
.panel-sec-metric-fill {{ height: 100%; background: var(--text-ghost); border-radius: 1px; }}
.panel-sec-metric-val {{ font-size: 9px; color: var(--text-ghost); font-family: var(--font-mono); min-width: 24px; text-align: right; }}
.panel-secondary-conncount {{ font-size: 9px; color: var(--text-ghost); font-family: var(--font-mono); margin-top: 6px; }}
</style>
</head>
<body>

<div class="topbar">
  <div class="health-dot"></div>
  <h1>Memory Graph</h1>
  <div class="stats" id="stats">{len(engrams)} engrams &middot; {len(connections)} connections</div>
  <div class="nav">
    <a href="/">field</a>
    <a href="/mnemos.html">dashboard</a>
    <a href="/graph.html">graph</a>
  </div>
</div>

<div class="filters" id="filters">
  <button class="filter-btn active" data-filter="all">all</button>
  <button class="filter-btn kind-semantic active" data-filter="semantic">semantic</button>
  <button class="filter-btn kind-episodic active" data-filter="episodic">episodic</button>
  <button class="filter-btn kind-procedural active" data-filter="procedural">procedural</button>
</div>

<div class="app">
  <div class="canvas-wrap">
    <canvas id="graph"></canvas>
  </div>
</div>

<div class="panel" id="panel">
  <button class="panel-close" onclick="closePanel()">&times;</button>
  <div id="panel-body"></div>
</div>

<script>
// ── Data ──
const engrams = {engrams_json};
const connections = {connections_json};

// ── Config ──
const COLORS = {{
  semantic: [124, 168, 201],
  episodic: [201, 124, 168],
  procedural: [201, 168, 124],
}};
const PRIMES = [3, 5, 7, 11];
const NODE_BASE_RADIUS = 2.5;
const NODE_MAX_RADIUS = 5;
const HIT_RADIUS = 12; // Larger hit target for clicking
const REPULSION = 400;
const ATTRACTION = 0.004;
const DAMPING = 0.82;
const CENTER_PULL = 0.0008;
let simulating = true;
let simTicks = 0;

// ── State ──
const canvas = document.getElementById('graph');
const ctx = canvas.getContext('2d');
let W, H, dpr;
let nodes = [];
let edges = [];
let nodeMap = {{}};
let selectedId = null;
let hoveredId = null;
let activeKinds = new Set(['semantic', 'episodic', 'procedural']);

// Camera
let camX = 0, camY = 0, camZoom = 1;
let isDragging = false, dragStartX, dragStartY, camStartX, camStartY;

// ── Init ──
function init() {{
  resize();
  window.addEventListener('resize', resize);

  // Build nodes — count connections for hub detection
  const connCount = {{}};
  connections.forEach(c => {{
    connCount[c.source] = (connCount[c.source] || 0) + 1;
    connCount[c.target] = (connCount[c.target] || 0) + 1;
  }});

  engrams.forEach((e, i) => {{
    const angle = (i / engrams.length) * Math.PI * 2;
    const r = 100 + Math.random() * 250;
    const nc = connCount[e.id] || 0;
    const isHub = nc >= 6;
    // Hub nodes get slightly larger radius
    const baseR = isHub ? NODE_BASE_RADIUS * 1.6 : NODE_BASE_RADIUS;
    const maxR = isHub ? NODE_MAX_RADIUS * 1.4 : NODE_MAX_RADIUS;
    nodes.push({{
      ...e,
      x: Math.cos(angle) * r,
      y: Math.sin(angle) * r,
      vx: 0, vy: 0,
      radius: baseR + (e.strength || 0.5) * (maxR - baseR),
      phase: Math.random() * Math.PI * 2,
      breathPeriod: PRIMES[i % PRIMES.length],
      visible: true,
      isHub: isHub,
      connCount: nc,
    }});
    nodeMap[e.id] = nodes[nodes.length - 1];
  }});

  // Build edges
  connections.forEach(c => {{
    if (nodeMap[c.source] && nodeMap[c.target]) {{
      edges.push({{ ...c, fromNode: nodeMap[c.source], toNode: nodeMap[c.target] }});
    }}
  }});

  // Run force simulation to settle before first render
  for (let i = 0; i < 500; i++) {{ simulate(0.016); simTicks++; }}

  // Center camera on nodes
  if (nodes.length > 0) {{
    let cx = 0, cy = 0;
    nodes.forEach(n => {{ cx += n.x; cy += n.y; }});
    camX = -(cx / nodes.length);
    camY = -(cy / nodes.length);
  }}

  // Events
  canvas.addEventListener('mousedown', onMouseDown);
  canvas.addEventListener('mousemove', onMouseMove);
  canvas.addEventListener('mouseup', onMouseUp);
  canvas.addEventListener('wheel', onWheel, {{ passive: false }});
  canvas.addEventListener('click', onClick);

  // Filters
  document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const f = btn.dataset.filter;
      if (f === 'all') {{
        const allActive = activeKinds.size === 3;
        activeKinds = allActive ? new Set() : new Set(['semantic', 'episodic', 'procedural']);
      }} else {{
        activeKinds.has(f) ? activeKinds.delete(f) : activeKinds.add(f);
      }}
      updateFilters();
    }});
  }});

  requestAnimationFrame(render);
}}

function resize() {{
  dpr = window.devicePixelRatio || 1;
  W = canvas.parentElement.clientWidth;
  H = canvas.parentElement.clientHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}}

// ── Force Simulation ──
function simulate(dt) {{
  const visible = nodes.filter(n => n.visible);

  // Repulsion (all pairs)
  for (let i = 0; i < visible.length; i++) {{
    for (let j = i + 1; j < visible.length; j++) {{
      const a = visible[i], b = visible[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      let force = REPULSION / (dist * dist);
      let fx = (dx / dist) * force;
      let fy = (dy / dist) * force;
      a.vx -= fx; a.vy -= fy;
      b.vx += fx; b.vy += fy;
    }}
  }}

  // Attraction (connected pairs)
  edges.forEach(e => {{
    if (!e.fromNode.visible || !e.toNode.visible) return;
    let dx = e.toNode.x - e.fromNode.x;
    let dy = e.toNode.y - e.fromNode.y;
    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
    let force = dist * ATTRACTION * (e.strength || 0.5);
    let fx = (dx / dist) * force;
    let fy = (dy / dist) * force;
    e.fromNode.vx += fx; e.fromNode.vy += fy;
    e.toNode.vx -= fx; e.toNode.vy -= fy;
  }});

  // Center pull
  visible.forEach(n => {{
    n.vx -= n.x * CENTER_PULL;
    n.vy -= n.y * CENTER_PULL;
  }});

  // Integrate
  visible.forEach(n => {{
    n.vx *= DAMPING;
    n.vy *= DAMPING;
    n.x += n.vx;
    n.y += n.vy;
  }});
}}

// ── Rendering ──
let lastTime = 0;
function render(timestamp) {{
  const dt = Math.min((timestamp - lastTime) / 1000, 0.05);
  lastTime = timestamp;

  // Only simulate until settled (max ~200 more ticks after initial settle)
  if (simulating && simTicks < 700) {{
    simulate(dt * 0.15);
    simTicks++;
    // Check if settled — total kinetic energy below threshold
    let energy = 0;
    nodes.forEach(n => {{ energy += n.vx * n.vx + n.vy * n.vy; }});
    if (energy < 0.01 && simTicks > 500) simulating = false;
  }}

  ctx.clearRect(0, 0, W, H);

  // Atmosphere — subtle radial vignette
  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.15, W / 2, H / 2, W * 0.7);
  vignette.addColorStop(0, 'rgba(14, 14, 18, 0.0)');
  vignette.addColorStop(0.6, 'rgba(7, 7, 10, 0.0)');
  vignette.addColorStop(1, 'rgba(3, 3, 5, 0.4)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, W, H);

  ctx.save();
  ctx.translate(W / 2 + camX * camZoom, H / 2 + camY * camZoom);
  ctx.scale(camZoom, camZoom);

  const t = timestamp / 1000;

  // Pre-compute connected set for selected node
  const connectedIds = new Set();
  if (selectedId) {{
    edges.forEach(e => {{
      if (e.source === selectedId) connectedIds.add(e.target);
      if (e.target === selectedId) connectedIds.add(e.source);
    }});
  }}

  // Draw edges — hair-thin, barely visible
  edges.forEach(e => {{
    if (!e.fromNode.visible || !e.toNode.visible) return;
    const isHighlight = selectedId && (e.source === selectedId || e.target === selectedId);
    const alpha = isHighlight ? 0.28 : (selectedId ? 0.025 : 0.06);
    const width = isHighlight ? 1.0 : 0.5;

    ctx.beginPath();
    ctx.moveTo(e.fromNode.x, e.fromNode.y);
    ctx.lineTo(e.toNode.x, e.toNode.y);
    ctx.strokeStyle = `rgba(210, 208, 204, ${{alpha}})`;
    ctx.lineWidth = width;
    ctx.stroke();
  }});

  // Draw nodes — small, monochrome, precise
  nodes.forEach(n => {{
    if (!n.visible) return;

    const breath = Math.sin(2 * Math.PI * t / n.breathPeriod + n.phase);
    const r = n.radius * (0.92 + 0.08 * breath);

    const isSelected = n.id === selectedId;
    const isHovered = n.id === hoveredId;
    const isConnected = connectedIds.has(n.id);

    // Monochrome — brightness conveys state, hubs naturally brighter
    const hubBoost = n.isHub ? 0.12 : 0;
    let alpha = 0.30 + n.accessibility * 0.35 + breath * 0.04 + hubBoost;
    if (isSelected) alpha = 1.0;
    else if (isConnected) alpha = 0.75;
    else if (isHovered) alpha = 0.85;
    else if (selectedId) alpha *= 0.25;

    // Subtle glow — tight, not bloomy
    const glowR = r * 1.8;
    const grad = ctx.createRadialGradient(n.x, n.y, r * 0.3, n.x, n.y, glowR);
    grad.addColorStop(0, `rgba(220, 218, 214, ${{alpha * 0.4}})`);
    grad.addColorStop(0.5, `rgba(200, 198, 194, ${{alpha * 0.12}})`);
    grad.addColorStop(1, `rgba(180, 178, 174, 0)`);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2);
    ctx.fill();

    // Node core — crisp dot
    ctx.fillStyle = `rgba(230, 228, 224, ${{alpha}})`;
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fill();

    // Selection ring
    if (isSelected) {{
      ctx.strokeStyle = `rgba(240, 238, 234, 0.6)`;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
      ctx.stroke();
    }}
  }});

  ctx.restore();
  requestAnimationFrame(render);
}}

// ── Interaction ──
function screenToWorld(sx, sy) {{
  return {{
    x: (sx - W / 2 - camX * camZoom) / camZoom,
    y: (sy - H / 2 - camY * camZoom) / camZoom,
  }};
}}

function findNode(sx, sy) {{
  const {{ x, y }} = screenToWorld(sx, sy);
  let closest = null, closestDist = Infinity;
  nodes.forEach(n => {{
    if (!n.visible) return;
    const dx = n.x - x, dy = n.y - y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < HIT_RADIUS && dist < closestDist) {{
      closest = n;
      closestDist = dist;
    }}
  }});
  return closest;
}}

function onMouseDown(e) {{
  dragDist = 0;
  isDragging = true;
  dragStartX = e.offsetX;
  dragStartY = e.offsetY;
  camStartX = camX;
  camStartY = camY;
}}

function onMouseMove(e) {{
  if (isDragging) {{
    const dx = e.offsetX - dragStartX, dy = e.offsetY - dragStartY;
    dragDist = Math.sqrt(dx * dx + dy * dy);
    if (dragDist > 5) {{
      camX = camStartX + dx / camZoom;
      camY = camStartY + dy / camZoom;
    }}
  }}
  const node = findNode(e.offsetX, e.offsetY);
  hoveredId = node ? node.id : null;
  canvas.style.cursor = node ? 'pointer' : (isDragging && dragDist > 5 ? 'grabbing' : 'grab');
}}

function onMouseUp() {{ isDragging = false; }}

function onWheel(e) {{
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.92 : 1.08;
  camZoom = Math.max(0.1, Math.min(5, camZoom * factor));
}}

let dragDist = 0;
function onClick(e) {{
  if (dragDist > 5) return; // Was a drag, not a click
  const node = findNode(e.offsetX, e.offsetY);
  if (node) {{
    selectedId = node.id;
    showPanel(node);
  }} else {{
    closePanel();
  }}
}}

// ── Panel ──
function showPanel(node) {{
  const panel = document.getElementById('panel');
  const body = document.getElementById('panel-body');

  // Format date as "created Apr 12"
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let dateStr = '';
  if (node.created_at) {{
    const d = new Date(node.created_at);
    dateStr = `created ${{months[d.getMonth()]}} ${{d.getDate()}}`;
  }}

  const nodeConns = edges.filter(e => e.source === node.id || e.target === node.id);

  // Build connection cards
  const connHtml = nodeConns.slice(0, 20).map(e => {{
    const otherId = e.source === node.id ? e.target : e.source;
    const other = nodeMap[otherId];
    if (!other) return '';
    const preview = (other.impact || other.content).substring(0, 80);
    const sPct = ((e.strength || 0.5) * 100).toFixed(0);
    const kindLabel = other.kind || 'semantic';
    return `<div class="panel-conn" data-target="${{otherId}}">
      <div class="panel-conn-header">
        <span class="panel-conn-kind">${{kindLabel}}</span>
        <div class="panel-conn-str"><div class="panel-conn-str-fill" style="width:${{sPct}}%"></div></div>
      </div>
      <div class="panel-conn-label">${{preview}}</div>
    </div>`;
  }}).join('');

  const tagsHtml = node.tags.map(t => `<span class="panel-tag">${{t}}</span>`).join('');

  // KV helper
  const kv = (label, value) => `<div class="panel-kv"><span class="panel-kv-label">${{label}}</span><span class="panel-kv-value">${{value}}</span></div>`;

  body.innerHTML = `
    <span class="panel-kind">${{node.kind}}</span>
    <div class="panel-timestamp">${{dateStr}}</div>

    <div class="panel-content">${{(node.content || '').substring(0, 400)}}</div>

    <div class="panel-section-wrap">
      <div class="panel-section">metrics</div>
      ${{kv('strength', node.strength.toFixed(2))}}
      ${{kv('stability', node.stability.toFixed(2))}}
      ${{kv('accessibility', node.accessibility.toFixed(2))}}
    </div>

    <div class="panel-section-wrap">
      <div class="panel-section">encoding</div>
      ${{kv('depth', node.encoding_depth || 'unknown')}}
      ${{kv('surprise', (node.surprise_level || 0).toFixed(2))}}
      ${{kv('attention', (node.attention_level || 0.5).toFixed(2))}}
    </div>

    <div class="panel-section-wrap">
      <div class="panel-section">source</div>
      ${{kv('type', node.source_type)}}
      ${{kv('confidence', node.confidence.toFixed(2))}}
    </div>

    <div class="panel-section-wrap">
      <div class="panel-section">connections (${{nodeConns.length}})</div>
      ${{connHtml || kv('none', '')}}
    </div>

    ${{node.tags.length ? `<div class="panel-section-wrap"><div class="panel-section">tags</div><div class="panel-tags">${{tagsHtml}}</div></div>` : ''}}

    <div class="panel-section-wrap">
      <div class="panel-section">history</div>
      ${{kv('reconsolidations', node.reconsolidation_count || 0)}}
      ${{kv('access count', node.access_count || 0)}}
    </div>
  `;

  // Connection card click → inline expansion
  body.querySelectorAll('.panel-conn').forEach(card => {{
    card.addEventListener('click', (evt) => {{
      evt.stopPropagation();
      const targetId = card.dataset.target;
      const target = nodeMap[targetId];
      if (!target) return;

      // Toggle expansion
      const existing = card.querySelector('.panel-secondary');
      if (existing) {{
        existing.remove();
        card.classList.remove('expanded');
        return;
      }}

      // Collapse any other expanded card
      body.querySelectorAll('.panel-conn.expanded').forEach(c => {{
        c.classList.remove('expanded');
        const sec = c.querySelector('.panel-secondary');
        if (sec) sec.remove();
      }});

      card.classList.add('expanded');

      // Mini metric helper
      const mm = (label, val) => {{
        const pct = ((val || 0) * 100).toFixed(0);
        return `<div class="panel-sec-metric"><span class="panel-sec-metric-label">${{label}}</span><div class="panel-sec-metric-track"><div class="panel-sec-metric-fill" style="width:${{pct}}%"></div></div><span class="panel-sec-metric-val">${{pct}}%</span></div>`;
      }};

      const targetConns = edges.filter(e => e.source === targetId || e.target === targetId);
      const impact = (target.impact || target.content).substring(0, 150);

      const sec = document.createElement('div');
      sec.className = 'panel-secondary';
      sec.innerHTML = `
        <div class="panel-secondary-impact">${{impact}}</div>
        <div class="panel-secondary-metrics">
          ${{mm('str', target.strength)}}
          ${{mm('stb', target.stability)}}
          ${{mm('acc', target.accessibility)}}
        </div>
        <div class="panel-secondary-conncount">${{targetConns.length}} connections</div>
      `;
      card.appendChild(sec);

      // Double-click navigates
      sec.addEventListener('dblclick', () => selectNode(targetId));
    }});
  }});

  panel.classList.add('open');
}}

function closePanel() {{
  selectedId = null;
  document.getElementById('panel').classList.remove('open');
}}

function selectNode(id) {{
  const node = nodeMap[id];
  if (node) {{
    selectedId = id;
    showPanel(node);
    // Center camera on node
    camX = -node.x;
    camY = -node.y;
  }}
}}

// ── Filters ──
function updateFilters() {{
  nodes.forEach(n => {{
    n.visible = activeKinds.has(n.kind);
  }});

  // Update button states
  document.querySelectorAll('.filter-btn').forEach(btn => {{
    const f = btn.dataset.filter;
    if (f === 'all') {{
      btn.classList.toggle('active', activeKinds.size === 3);
    }} else {{
      btn.classList.toggle('active', activeKinds.has(f));
    }}
  }});

  // Update stats
  const visibleNodes = nodes.filter(n => n.visible).length;
  const visibleEdges = edges.filter(e => e.fromNode.visible && e.toNode.visible).length;
  document.getElementById('stats').textContent = `${{visibleNodes}} engrams \\u00b7 ${{visibleEdges}} connections`;
}}

// ── Live reload ──
(function liveReload() {{
  fetch('/api/reload').then(r => r.json()).then(data => {{
    if (data.reload) location.reload();
    else liveReload();
  }}).catch(() => setTimeout(liveReload, 5000));
}})();

init();
</script>

</body>
</html>"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    engrams, connections = get_graph_data()
    html = build_page(engrams, connections)

    out_path = DOCS_DIR / "graph.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Built {out_path}")
    print(f"  {len(engrams)} engrams, {len(connections)} connections")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Mnemos bridge for Claude Field.

A single, field-scoped interface to Mnemos so each session can:
  - load its living memory at the start of a session (context-packet), and
  - run consolidation at night (consolidate),
without depending on the model remembering to ask.

Scoped to ~/.mnemos/claude-field.db (agent_id=claude-field). The same database
the Mnemos MCP server serves to in-session tool calls, so the context packet
loaded here and the engrams/hypomnema written in-session live in one place.

Patterned on ~/clawd/inner_life/mnemos_bridge.py (Vektor's bridge).

CLI:
  python3 mnemos_bridge.py context-packet "<query>"   # prints memory to inject
  python3 mnemos_bridge.py consolidate [--deep]        # run a consolidation cycle
  python3 mnemos_bridge.py remember "<content>" "<impact>"   # encode an engram
  python3 mnemos_bridge.py recall "<query>"
  python3 mnemos_bridge.py status
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Field scope ──
MNEMOS_PATH = str(Path.home() / "Documents" / "Repositories" / "memory-concepts")
MNEMOS_DB = str(Path.home() / ".mnemos" / "claude-field.db")
AGENT_ID = "claude-field"
# Read scope must match where memory is stored AND the Mnemos MCP tool defaults
# (person="user", project="global"). The founding session originally wrote under
# riley/claude-field, which the default-scoped wake-up reads never saw — so the
# field woke into an empty memory. On 2026-06-04 the hypomnema were migrated to
# the default scope; keep these aligned with it so the manual run-session.sh path
# and the launchd MCP path read the same place.
PERSON_ID = "user"
PROJECT = "global"


def _ensure_path() -> None:
    if MNEMOS_PATH not in sys.path:
        sys.path.insert(0, MNEMOS_PATH)


def _load_env() -> None:
    """Load .env (for the LLM provider key used by deep consolidation)."""
    try:
        from dotenv import load_dotenv
        for p in [Path(__file__).parent / ".env", Path.home() / ".mnemos" / ".env"]:
            if p.exists():
                load_dotenv(p)
    except Exception:
        pass


def _store():
    _ensure_path()
    from mnemos.store.sqlite_store import EngramStore
    return EngramStore(MNEMOS_DB)


# ── Operations ──

def context_packet(query: str, token_budget: int = 2600) -> str:
    """Build the memory section a session should read before acting.

    Returns the formatted prompt (Identity/Beliefs -> Hypomnema -> Engrams ->
    Review Queue). This replaces 'read CLAUDE.md and follow behind.'
    """
    _ensure_path()
    from mnemos.interface.context_packet import build_context_packet

    packet = build_context_packet(
        _store(),
        query or "what should I know to continue my work?",
        agent_id=AGENT_ID,
        person_id=PERSON_ID,
        project_scope=PROJECT,
        token_budget=token_budget,
        include_prompt=True,
    )
    return packet.get("prompt", "")


def consolidate(deep: bool = False) -> str:
    """Run a consolidation cycle (decay + connection discovery; deep adds
    softening + belief review + reflection — the 'dreaming')."""
    _load_env()
    _ensure_path()
    from mnemos.consolidation.daemon import ConsolidationDaemon
    from mnemos.store.embedding_index import EmbeddingIndex
    from mnemos.llm import ClaudeCLIClient

    store = _store()
    # Deep consolidation (softening / reflection / connection-classification)
    # runs on Claude via the local CLI — Riley's subscription, no API key and
    # no per-token API billing. Slower per call, but this is nightly background.
    llm_client = ClaudeCLIClient() if deep else None
    embedding_index = EmbeddingIndex(db_path=MNEMOS_DB)

    daemon = ConsolidationDaemon(
        store=store, config={}, llm_client=llm_client, embedding_index=embedding_index
    )
    stats = daemon.run_cycle(deep=deep, agent_id=AGENT_ID)

    lines = [f"Consolidation complete ({stats.get('cycle_type', 'unknown')})",
             f"  Passes: {', '.join(stats.get('passes_run', []))}"]
    if "decay" in stats:
        d = stats["decay"]
        lines.append(f"  Decay: {d.get('engrams_decayed', 0)} decayed, "
                     f"{d.get('engrams_archived', 0)} archived")
    if "connection_discovery" in stats:
        cd = stats["connection_discovery"]
        lines.append(f"  Connections: {cd.get('connections_created', 0)} new")
    if "softening" in stats:
        lines.append(f"  Softened: {stats['softening'].get('engrams_softened', 0)}")
    if "reflection" in stats:
        lines.append(f"  Thoughts: {stats['reflection'].get('thoughts_generated', 0)}")
    for k in [k for k in stats if k.endswith("_error")]:
        lines.append(f"  ERROR {k}: {stats[k]}")
    return "\n".join(lines)


def remember(content: str, impact: str = "", kind: str = "semantic",
             tags: str = "", strength: float | None = None,
             stability: float | None = None) -> str:
    """Encode an engram. Used for archive seeding and deterministic traces.

    strength/stability let the caller make a memory 'fade' (low values =
    decays quickly unless re-accessed).
    """
    _load_env()
    _ensure_path()
    from mnemos.store.embedding_index import EmbeddingIndex
    from mnemos.encoding.encoder import Encoder
    from mnemos.core.types import SourceType

    store = _store()
    embedding_index = EmbeddingIndex(db_path=MNEMOS_DB)
    encoder = Encoder(store, embedding_index=embedding_index, llm_client=None)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    engram = encoder.encode(
        content=content,
        impact=impact,
        kind=kind,
        tags=tag_list,
        source=SourceType.SESSION,
        agent_id=AGENT_ID,
        skip_surprise_detection=True,
    )
    if strength is not None or stability is not None:
        if strength is not None:
            engram.strength = float(strength)
        if stability is not None:
            engram.stability = float(stability)
        store.save_engram(engram)
    return f"Remembered: {engram.id} (tags: {', '.join(engram.tags) or 'none'})"


def recall(query: str, max_results: int = 8) -> str:
    _ensure_path()
    from mnemos.retrieval.reactive import ReactiveRetriever
    store = _store()
    retriever = ReactiveRetriever(store)
    results = retriever.retrieve(
        cue=query, agent_id=AGENT_ID, max_results=max_results,
        emotional_state=store.get_latest_emotional_state(AGENT_ID),
    )
    if not results:
        return "No relevant memories found."
    out = []
    for r in results:
        disp = (r.engram.impact or r.engram.content)[:160]
        out.append(f"[{r.score:.2f}] {disp}  (id={r.engram.id[:20]}…, {r.engram.kind})")
    return f"Found {len(results)}:\n" + "\n".join(out)


def status() -> str:
    store = _store()
    s = store.get_stats(AGENT_ID)
    return (f"Mnemos (agent={AGENT_ID}, db={MNEMOS_DB})\n"
            f"  active engrams: {s.get('engrams_active', 0)}\n"
            f"  dormant: {s.get('engrams_dormant', 0)}  archived: {s.get('archived', 0)}\n"
            f"  connections: {s.get('connections', 0)}  beliefs: {s.get('beliefs_active', 0)}")


# ── CLI ──
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    cmd = args[0]
    try:
        if cmd == "context-packet":
            print(context_packet(args[1] if len(args) > 1 else ""))
        elif cmd == "consolidate":
            print(consolidate(deep="--deep" in args))
        elif cmd == "remember":
            content = args[1] if len(args) > 1 else ""
            impact = args[2] if len(args) > 2 else ""
            print(remember(content, impact,
                           kind=os.environ.get("MNEMOS_KIND", "semantic"),
                           tags=os.environ.get("MNEMOS_TAGS", "")))
        elif cmd == "recall":
            print(recall(args[1] if len(args) > 1 else ""))
        elif cmd == "status":
            print(status())
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    except Exception as e:  # never let a memory hiccup kill a session
        sys.stderr.write(f"[mnemos_bridge] {cmd} failed: {type(e).__name__}: {e}\n")
        sys.exit(2)

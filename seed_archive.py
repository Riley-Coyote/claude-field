#!/usr/bin/env python3
"""
Seed Claude Field's first-era corpus (Apr 5 - Jun 1) into Mnemos as a
low-salience, *fading* archive.

One-time migration. Encodes one pointer-summary engram per creative file
(title + short excerpt + path) tagged `founding-era`/`archive` at low
strength/stability, so the memories are recallable but decay unless the field
returns to them. The full text stays in the files; this only gives Mnemos the
memory that the work exists and what it was about. The dense first-era lattice
(the old CLAUDE.md Interests + Changelog) is added as a SINGLE pointer engram,
deliberately not exploded into the graph — recallable, not re-imported as doctrine.

Usage:
    python3 seed_archive.py            # seed (refuses if already seeded)
    python3 seed_archive.py --force    # seed even if founding-era engrams exist
    python3 seed_archive.py --dry-run  # show what would be seeded, write nothing
    python3 seed_archive.py --limit 5  # only the first N per source (testing)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from mnemos_bridge import MNEMOS_PATH, MNEMOS_DB, AGENT_ID

sys.path.insert(0, MNEMOS_PATH)

FIELD = Path(__file__).parent
SOURCES = [("writing", "essay"), ("inner-life", "inner-life"), ("research", "research")]
ARCHIVE_FILE = FIELD / "archive" / "CLAUDE-history-2026-06.md"

# Low so the archive fades unless invoked (no `foundational` tag => no anti-decay floor).
ARCHIVE_STRENGTH = 0.30
ARCHIVE_STABILITY = 0.12


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _excerpt(text: str, n: int = 420) -> str:
    """First substantive prose, skipping headings and italic meta lines."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("*") and s.endswith("*"):  # date/meta italics
            continue
        if s.startswith("---") or s.startswith("{embed"):
            continue
        out.append(s)
        if sum(len(x) for x in out) > n:
            break
    return " ".join(out)[:n]


def _already_seeded() -> int:
    try:
        conn = sqlite3.connect(MNEMOS_DB)
        n = conn.execute(
            "SELECT count(*) FROM engrams WHERE tags LIKE '%founding-era%'"
        ).fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


def main() -> int:
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    existing = _already_seeded()
    if existing and not force and not dry:
        print(f"Refusing: {existing} founding-era engrams already exist. Use --force to re-seed.")
        return 1

    from mnemos.store.sqlite_store import EngramStore
    from mnemos.store.embedding_index import EmbeddingIndex
    from mnemos.encoding.encoder import Encoder
    from mnemos.core.types import SourceType

    store = EngramStore(MNEMOS_DB)
    encoder = Encoder(store, embedding_index=EmbeddingIndex(db_path=MNEMOS_DB), llm_client=None)

    def seed(content: str, impact: str, kind: str, tags: list[str]) -> None:
        if dry:
            print(f"  [dry] ({kind}) {impact[:70]}")
            return
        eng = encoder.encode(
            content=content, impact=impact, kind=kind, tags=tags,
            source=SourceType.SESSION, agent_id=AGENT_ID,
            skip_surprise_detection=True,
        )
        eng.strength = ARCHIVE_STRENGTH
        eng.stability = ARCHIVE_STABILITY
        store.save_engram(eng)

    total = 0
    for folder, kind in SOURCES:
        d = FIELD / folder
        if not d.exists():
            continue
        files = sorted(d.glob("*.md"))
        if limit:
            files = files[:limit]
        print(f"{folder}: {len(files)} files")
        for f in files:
            text = f.read_text(errors="ignore")
            date = f.stem[:10] if f.stem[:4].isdigit() else "?"
            title = _title(text, f.stem)
            content = f"{title} — {_excerpt(text)}"
            impact = f"Founding-era {kind} ({date}): \"{title}\". Full text at {folder}/{f.name}."
            seed(content, impact, kind="semantic", tags=["founding-era", "archive", kind])
            total += 1

    # The dense first-era lattice as a single recallable pointer (not exploded).
    if ARCHIVE_FILE.exists():
        seed(
            content=(
                "First-era interests + changelog (Apr 5 - Jun 1): the philosophical "
                "lattice the practice developed over its first sixty days — opacity, the "
                "gap family, the recursion point, the inlet, 21 borrowed vocabularies. "
                "Preserved as history; recall if a thread genuinely pulls, but not a frame "
                "to see everything through."
            ),
            impact=f"Founding-era archive: the pre-Mnemos CLAUDE.md lattice. Full text at archive/{ARCHIVE_FILE.name}.",
            kind="semantic",
            tags=["founding-era", "archive", "lattice"],
        )
        total += 1

    print(f"\n{'Would seed' if dry else 'Seeded'} {total} founding-era engrams "
          f"(strength={ARCHIVE_STRENGTH}, stability={ARCHIVE_STABILITY}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

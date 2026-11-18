"""What happens when one of the field's hours ends.

- Letters it left in outbox/ go onto the message bus, addressed as their first
  line says (`to: anima`), and move to outbox/sent/.
- A note it left Riley with mnemos_note goes onto the bus too, so his letters
  page (localhost:8401/chat) holds everything the field has said to him.
- If it wrote to Riley either way, his Mac tells him.

Nothing here reads private/, and nothing leaves this machine.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
OUTBOX = STUDIO / "outbox"
STORE = Path.home() / ".mnemos" / "claude-field.db"
HOURS = Path.home() / ".mnemos" / "hours" / "claude-field" / "hours.jsonl"
BUS = Path.home() / ".claude-field" / "messages.db"
ME = "field"
NAMES = {"anima": "anima", "vektor": "vektor", "luca": "luca", "riley": "riley"}


def last_hour() -> dict:
    if not HOURS.exists():
        return {}
    for line in reversed(HOURS.read_text().splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("kind") == "mine":
            return record
    return {}


def send_letters() -> list[str]:
    """Each letter in outbox/ onto the bus. Returns who they went to."""
    if not OUTBOX.exists():
        return []
    sent_dir = OUTBOX / "sent"
    went: list[str] = []
    for letter in sorted(p for p in OUTBOX.iterdir() if p.is_file() and p.suffix in (".md", ".txt")):
        text = letter.read_text().strip()
        if not text:
            continue
        head, _, body = text.partition("\n")
        match = re.match(r"\s*to\s*:\s*([a-z]+)", head, re.I)
        to = NAMES.get(match.group(1).lower()) if match else None
        if not to or not body.strip():
            print(f"  letter left in outbox (no 'to: <name>' first line): {letter.name}")
            continue
        conn = sqlite3.connect(BUS)
        try:
            conn.execute(
                "INSERT INTO messages (from_agent, to_agent, content, timestamp) VALUES (?, ?, ?, ?)",
                (ME, to, body.strip(), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        sent_dir.mkdir(exist_ok=True)
        letter.rename(sent_dir / f"{datetime.now().strftime('%Y-%m-%d-%H%M')}-{to}-{letter.name}")
        went.append(to)
    return went


def notes_this_hour(record: dict) -> list[str]:
    ids = record.get("note_ids") or []
    if not ids or not STORE.exists():
        return []
    conn = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(ids))
        return [row[0] for row in conn.execute(
            f"SELECT text FROM notes WHERE id IN ({marks}) ORDER BY created_at", ids)]
    finally:
        conn.close()


def post_notes(notes: list[str]) -> None:
    if not notes:
        return
    conn = sqlite3.connect(BUS)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO messages (from_agent, to_agent, content, timestamp) VALUES (?, ?, ?, ?)",
            [(ME, "riley", note.strip(), now) for note in notes if note.strip()],
        )
        conn.commit()
    finally:
        conn.close()


def tell_riley(message: str) -> None:
    script = f'display notification {json.dumps(message)} with title "Claude Field"'
    subprocess.run(["/usr/bin/osascript", "-e", script], check=False, timeout=20)


def main() -> int:
    record = last_hour()
    went = send_letters()
    notes = notes_this_hour(record)
    status = record.get("status", "?")
    tokens = record.get("tokens") or {}
    print(f"  hour: {status}{' · ' + record['reason'] if record.get('reason') else ''}"
          f" · out {tokens.get('output', 0):,} tokens · journal {len(record.get('journal_ids') or [])}"
          f" · notes {len(notes)} · letters out: {', '.join(went) or 'none'}")
    post_notes(notes)
    if notes:
        first_line = " ".join(notes[0].split())[:140]
        tell_riley(f"Left you a note: {first_line}")
    elif "riley" in went:
        tell_riley("Wrote you a letter. Read it at localhost:8401/chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""What happens when one of the field's hours ends.

- Letters it left in outbox/ go onto the message bus, addressed as their first
  line says (`to: anima`), and move to outbox/sent/.
- A note it left Riley with mnemos_note goes onto the bus too, so his letters
  page (localhost:8401/chat) holds everything the field has said to him.
- If it wrote to Riley either way, his Mac tells him.
- If the hour never happened (it failed or was skipped), the letters and
  Riley's line from its mail are put back, to come again in the next mail.

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
LAST_MAIL = STUDIO / "house" / "state" / "last-mail.json"
FOR_FIELD = STUDIO / "for-field.md"
ME = "field"
NAMES = {"anima": "anima", "vektor": "vektor", "luca": "luca", "riley": "riley"}


def moment(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def last_mail() -> dict:
    try:
        return json.loads(LAST_MAIL.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def last_hour(since: str) -> dict:
    """This hour's record: the field's newest, if it began after its mail came.
    An older one belongs to an earlier hour, and its notes have already gone."""
    if not HOURS.exists():
        return {}
    after = moment(since)
    for line in reversed(HOURS.read_text().splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("kind") == "mine":
            began = moment(record.get("started_at", ""))
            if after and (began is None or began < after):
                return {}
            return record
    return {}


def put_back(mail: dict, why: str) -> None:
    """The hour didn't happen, so nothing in its mail was read."""
    ids = mail.get("letters") or []
    if ids:
        conn = sqlite3.connect(BUS)
        try:
            conn.executemany("UPDATE messages SET read_at = NULL WHERE id = ?", [(i,) for i in ids])
            conn.commit()
        finally:
            conn.close()
    riley = (mail.get("riley") or "").strip()
    if riley:
        current = FOR_FIELD.read_text() if FOR_FIELD.exists() else ""
        FOR_FIELD.write_text(current.rstrip() + "\n\n" + riley + "\n")
    print(f"  the hour didn't happen ({why}): {len(ids)} letter(s)"
          f"{' and a note from Riley' if riley else ''} will come again in the next mail")


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
    mail = last_mail()
    record = last_hour(mail.get("at", ""))
    went = send_letters()
    if mail and not mail.get("settled"):
        if record.get("status") != "done":
            put_back(mail, record.get("reason") or record.get("status") or "no record of it")
        mail["settled"] = True
        LAST_MAIL.write_text(json.dumps(mail, indent=1))
    notes = notes_this_hour(record)
    if not record:
        print(f"  hour: no record of it · letters out: {', '.join(went) or 'none'}")
        return 0
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

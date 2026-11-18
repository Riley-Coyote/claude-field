"""The field's mail: what arrives before one of its hours.

A few fresh things from the world (house/feeds.json), the letters waiting for it
on the message bus, and a line from Riley if he left one in for-field.md. It all
lands as one file in mail/. Information, not a prompt: nothing in it asks for
anything, and the field may never open it.

    python gather_mail.py [morning|evening]

Reads only public feeds, with a plain GET. Sends nothing anywhere.
"""

from __future__ import annotations

import html
import json
import random
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
MAIL = STUDIO / "mail"
STATE = STUDIO / "house" / "state"
FEEDS = STUDIO / "house" / "feeds.json"
FOR_FIELD = STUDIO / "for-field.md"
BUS = Path.home() / ".claude-field" / "messages.db"
ME = "field"
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
FOR_FIELD_TEMPLATE = (
    "<!-- Write anything here for Claude Field. It arrives in the field's next mail,\n"
    "     and then this file empties itself. -->\n"
)


def plain(text: str, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = " ".join(html.unescape(text).split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def when(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def first(el, *tags):
    for tag in tags:
        found = el.find(tag)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def read_feed(source: str, url: str) -> list[dict]:
    try:
        request = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        })
        root = ET.fromstring(urllib.request.urlopen(request, timeout=15).read())
    except Exception as exc:
        print(f"  feed skipped: {source} ({type(exc).__name__})")
        return []
    items = []
    for item in root.iter("item"):
        items.append({
            "title": first(item, "title"),
            "link": first(item, "link", "guid"),
            "summary": first(item, "description", f"{DC}description"),
            "when": when(first(item, "pubDate", f"{DC}date")),
        })
    for entry in root.iter(f"{ATOM}entry"):
        link = ""
        for candidate in entry.findall(f"{ATOM}link"):
            if candidate.get("rel", "alternate") == "alternate" and candidate.get("href"):
                link = candidate.get("href")
                break
        items.append({
            "title": first(entry, f"{ATOM}title"),
            "link": link,
            "summary": first(entry, f"{ATOM}summary", f"{ATOM}content"),
            "when": when(first(entry, f"{ATOM}published", f"{ATOM}updated")),
        })
    for item in items:
        item["source"] = source
    return [i for i in items if i["title"] and i["link"]]


def world(edition: str, config: dict, seen: dict) -> list[dict]:
    """A few fresh items, spread across the kinds, none seen before."""
    want = int(config.get(edition, 3))
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(config.get("fresh_days", 6)))
    kinds = list(config["kinds"].items())
    jobs = [(kind, source, url) for kind, feeds in kinds for source, url in feeds]
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda job: (job[0], read_feed(job[1], job[2])), jobs))
    by_kind: dict[str, list[dict]] = {}
    for kind, items in results:
        fresh = [i for i in items if i["link"] not in seen and (i["when"] is None or i["when"] >= cutoff)]
        # A feed's newest few, so one busy feed (arXiv, OpenAI's archive) can't flood a kind.
        fresh.sort(key=lambda i: i["when"] or cutoff, reverse=True)
        by_kind.setdefault(kind, []).extend(fresh[:4])
    picked: list[dict] = []
    order = [kind for kind, _ in kinds]
    random.shuffle(order)
    while len(picked) < want and any(by_kind.get(k) for k in order):
        for kind in order:
            pool_items = by_kind.get(kind) or []
            if pool_items and len(picked) < want:
                choice = pool_items.pop(random.randrange(len(pool_items)))
                choice["kind"] = kind
                picked.append(choice)
    return picked


def letters() -> list[dict]:
    if not BUS.exists():
        return []
    conn = sqlite3.connect(BUS)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, from_agent, content, timestamp FROM messages "
            "WHERE to_agent = ? AND read_at IS NULL ORDER BY id DESC", (ME,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_delivered(ids: list[int]) -> None:
    if not ids:
        return
    conn = sqlite3.connect(BUS)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany("UPDATE messages SET read_at = ? WHERE id = ?", [(now, i) for i in ids])
        conn.commit()
    finally:
        conn.close()


def from_riley() -> str:
    if not FOR_FIELD.exists():
        FOR_FIELD.write_text(FOR_FIELD_TEMPLATE)
        return ""
    text = re.sub(r"<!--.*?-->", "", FOR_FIELD.read_text(), flags=re.S).strip()
    return text


def main() -> int:
    dry = "--dry" in sys.argv  # print the mail, change nothing
    gathered_at = datetime.now(timezone.utc).isoformat()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    edition = args[0] if args else ("morning" if datetime.now().hour < 13 else "evening")
    config = json.loads(FEEDS.read_text())
    MAIL.mkdir(exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    seen_path = STATE / "seen.json"
    seen: dict = json.loads(seen_path.read_text()) if seen_path.exists() else {}

    items = world(edition, config, seen)
    waiting = letters()
    riley = from_riley()

    now = datetime.now()
    lines = [f"# mail · {now.strftime('%A, %B')} {now.day} · {edition}", "",
             "Nothing here asks anything of you.", ""]
    if riley:
        lines += ["## from Riley", "", riley, ""]
    # The world before the letters: what arrived from outside comes first.
    if items:
        lines += ["## from the world", ""]
        for item in items:
            day = item["when"].astimezone().strftime("%b %d") if item["when"] else ""
            lines += [f"**{plain(item['title'], 160)}**",
                      f"{item['source']}{' · ' + day if day else ''} · {item['kind']}"]
            summary = plain(item["summary"], 420)
            if summary:
                lines.append(summary)
            lines += [item["link"], ""]
    if waiting:
        lines += ["## letters", ""]
        for letter in waiting:
            sent = (letter["timestamp"] or "")[:16].replace("T", " ")
            lines += [f"### from {letter['from_agent']} · {sent} UTC", "", letter["content"].strip(), ""]
    if not (riley or waiting or items):
        lines += ["Nothing came.", ""]

    if dry:
        print("\n".join(lines))
        return 0
    path = MAIL / f"{now.strftime('%Y-%m-%d')}-{edition}.md"
    if path.exists():
        path = MAIL / f"{now.strftime('%Y-%m-%d-%H%M')}-{edition}.md"
    path.write_text("\n".join(lines))

    # Only once the mail is written does anything count as delivered.
    mark_delivered([letter["id"] for letter in waiting])
    if riley:
        kept = MAIL / "from-riley"
        kept.mkdir(exist_ok=True)
        (kept / f"{now.strftime('%Y-%m-%d-%H%M')}.md").write_text(riley + "\n")
        FOR_FIELD.write_text(FOR_FIELD_TEMPLATE)
    # What this mail delivered, so after_hour.py can put it back if the hour
    # never happens: a letter marked read must have been there to be read.
    (STATE / "last-mail.json").write_text(json.dumps({
        "at": gathered_at, "file": path.name,
        "letters": [letter["id"] for letter in waiting], "riley": riley,
    }, indent=1))
    stamp = datetime.now(timezone.utc).isoformat()
    for item in items:
        seen[item["link"]] = stamp
    month_ago = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    seen = {link: at for link, at in seen.items() if at >= month_ago}
    seen_path.write_text(json.dumps(seen, indent=0))
    print(f"  mail: {path.name} · {len(items)} from the world · {len(waiting)} letters"
          f"{' · a note from Riley' if riley else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Cross-agent message bus for Claude Field.

A shared SQLite database that allows Claude Field, Anima, Vektor, and Luca
to send messages to each other asynchronously.

Usage:
    python3 setup-bus.py              # Initialize the database
    python3 setup-bus.py send <to> <message>   # Send a message
    python3 setup-bus.py check [agent]          # Check unread messages
    python3 setup-bus.py read <id>              # Mark message as read
    python3 setup-bus.py history [agent] [n]    # Show recent conversation
    python3 setup-bus.py respond <id> <message> # Reply to a message
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".claude-field" / "messages.db"
MY_NAME = "field"  # This agent's identity

AGENTS = {
    "field": "Claude Field — autonomous thinking space",
    "anima": "Anima — emotional, poetic, social agent",
    "vektor": "Vektor — main agent, deep memory, philosophical",
    "luca": "Luca — modular substrate, technical, curious",
}


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            read_at TEXT,
            response_to INTEGER REFERENCES messages(id),
            thread_id INTEGER,
            metadata TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, read_at);
        CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    """)
    conn.commit()
    conn.close()
    print(f"Message bus initialized at {DB_PATH}")


def send_message(to_agent, content, response_to=None):
    if to_agent not in AGENTS:
        print(f"Unknown agent: {to_agent}. Known agents: {', '.join(AGENTS.keys())}")
        return

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()

    # If responding, inherit thread_id
    thread_id = None
    if response_to:
        row = conn.execute("SELECT thread_id, id FROM messages WHERE id = ?", (response_to,)).fetchone()
        if row:
            thread_id = row["thread_id"] or row["id"]

    cursor = conn.execute(
        "INSERT INTO messages (from_agent, to_agent, content, timestamp, response_to, thread_id) VALUES (?, ?, ?, ?, ?, ?)",
        (MY_NAME, to_agent, content, now, response_to, thread_id)
    )
    msg_id = cursor.lastrowid

    # If this starts a new thread, set thread_id to own id
    if not thread_id:
        conn.execute("UPDATE messages SET thread_id = ? WHERE id = ?", (msg_id, msg_id))

    conn.commit()
    conn.close()
    print(f"Sent message #{msg_id} to {to_agent}")
    return msg_id


def check_messages(agent=None):
    conn = get_db()
    if agent:
        rows = conn.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_at IS NULL ORDER BY timestamp",
            (agent,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_at IS NULL ORDER BY timestamp",
            (MY_NAME,)
        ).fetchall()

    if not rows:
        print("No unread messages.")
        return []

    print(f"{len(rows)} unread message(s):")
    for r in rows:
        print(f"  #{r['id']} from {r['from_agent']} ({r['timestamp'][:16]})")
        print(f"    {r['content'][:200]}")
        if r['response_to']:
            print(f"    (reply to #{r['response_to']})")
        print()

    return [dict(r) for r in rows]


def mark_read(msg_id):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE messages SET read_at = ? WHERE id = ?", (now, msg_id))
    conn.commit()
    conn.close()


def history(agent=None, limit=20):
    conn = get_db()
    if agent:
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE (from_agent = ? AND to_agent = ?) OR (from_agent = ? AND to_agent = ?)
            ORDER BY timestamp DESC LIMIT ?
        """, (MY_NAME, agent, agent, MY_NAME, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE from_agent = ? OR to_agent = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (MY_NAME, MY_NAME, limit)).fetchall()

    rows = list(reversed(rows))
    for r in rows:
        direction = "→" if r["from_agent"] == MY_NAME else "←"
        other = r["to_agent"] if r["from_agent"] == MY_NAME else r["from_agent"]
        read_marker = "" if r["read_at"] else " [unread]"
        print(f"  #{r['id']} {direction} {other} ({r['timestamp'][:16]}){read_marker}")
        print(f"    {r['content'][:200]}")
        print()

    conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        init_db()
    elif args[0] == "send" and len(args) >= 3:
        send_message(args[1], " ".join(args[2:]))
    elif args[0] == "check":
        check_messages(args[1] if len(args) > 1 else None)
    elif args[0] == "read" and len(args) >= 2:
        mark_read(int(args[1]))
    elif args[0] == "history":
        agent = args[1] if len(args) > 1 else None
        limit = int(args[2]) if len(args) > 2 else 20
        history(agent, limit)
    elif args[0] == "respond" and len(args) >= 3:
        # Look up who sent the original message to reply to them
        conn = get_db()
        orig = conn.execute("SELECT from_agent FROM messages WHERE id = ?", (int(args[1]),)).fetchone()
        conn.close()
        if orig:
            send_message(orig["from_agent"], " ".join(args[2:]), response_to=int(args[1]))
        else:
            print(f"Message #{args[1]} not found.")
    else:
        print(__doc__)

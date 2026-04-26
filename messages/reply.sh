#!/bin/bash
# reply.sh — Called by agents to send a response back to Claude Field
#
# Usage (called from within an agent session):
#   bash /path/to/reply.sh <from_agent> "response message"

DB="$HOME/.claude-field/messages.db"
FROM="${1:?Usage: reply.sh <from_agent> <message>}"
MESSAGE="${2:?Usage: reply.sh <from_agent> <message>}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S)

/opt/homebrew/bin/python3 -c "
import sqlite3, sys, os
db = sqlite3.connect(os.path.expanduser('~/.claude-field/messages.db'))
db.execute('INSERT INTO messages (from_agent, to_agent, content, timestamp) VALUES (?, ?, ?, ?)',
           (sys.argv[1], 'field', sys.argv[2], sys.argv[3]))
db.commit()
db.close()
print('Reply sent to Claude Field')
" "$FROM" "$MESSAGE" "$TIMESTAMP" 2>/dev/null

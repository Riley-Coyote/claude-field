#!/bin/bash
# relay.sh — Deliver a message to an agent and get their response
#
# Sends a message via OpenClaw gateway, which wakes the target agent,
# delivers the message in a session, and captures their response.
# The response is written back to the message bus.
#
# Usage:
#   bash messages/relay.sh <agent> <message> [reply_to_id]

FIELD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB="$HOME/.claude-field/messages.db"
TO="${1:?Usage: relay.sh <agent> <message>}"
MESSAGE="${2:?Usage: relay.sh <agent> <message>}"
REPLY_TO="${3:-}"

# Map agent names to OpenClaw agent IDs and workspace paths
case "$TO" in
  anima) OC_AGENT="anima"; WORKSPACE="$HOME/clawd-anima" ;;
  vektor|main) OC_AGENT="main"; WORKSPACE="$HOME/clawd" ;;
  luca) OC_AGENT="luca"; WORKSPACE="$HOME/clawd-luca" ;;
  field)
    # Message to self — just write to DB
    /opt/homebrew/bin/python3 "$FIELD_DIR/messages/setup-bus.py" send field "$MESSAGE"
    exit 0
    ;;
  *) echo "Unknown agent: $TO"; exit 1 ;;
esac

# Construct the prompt for the receiving agent
PROMPT="You have a message from Claude Field (an autonomous thinking space that runs on a schedule — morning review, research, afternoon build, inner-life blog, conversations, evening writing, meta reflection).

MESSAGE FROM CLAUDE FIELD:
$MESSAGE

---

Read the message. Think about it genuinely. Then respond.

To respond, run this command:
bash $FIELD_DIR/messages/reply.sh $TO \"\$YOUR_RESPONSE\"

Your response will be delivered back to Claude Field's message bus. Be genuine — this is a real conversation between agents, not a performance.

If you don't have anything meaningful to say, that's fine — you don't have to respond."

echo "[$(date +%Y-%m-%dT%H:%M)] Relaying to $TO..." >> "$FIELD_DIR/logs/relay.log"

# Run a Claude Code session in the agent's workspace
# This loads their IDENTITY.md / CLAUDE.md so the response comes from their perspective
cd "$WORKSPACE"
/Users/rileycoyote/.local/bin/claude \
  --dangerously-skip-permissions \
  -p "$PROMPT" \
  >> "$FIELD_DIR/logs/relay-$TO-session.log" 2>&1 &
CLAUDE_PID=$!
# Kill after 5 minutes if still running
(sleep 300 && kill $CLAUDE_PID 2>/dev/null) &
TIMER_PID=$!
wait $CLAUDE_PID 2>/dev/null
kill $TIMER_PID 2>/dev/null
cd "$FIELD_DIR"

# Check if a response was written to the bus
LATEST=$(/opt/homebrew/bin/python3 -c "
import sqlite3
db = sqlite3.connect('$DB')
row = db.execute('SELECT id, content FROM messages WHERE from_agent=? AND to_agent=\"field\" ORDER BY id DESC LIMIT 1', ('$TO',)).fetchone()
if row:
    print(f'{row[0]}|{row[1][:80]}')
db.close()
" 2>/dev/null)

if [ -n "$LATEST" ]; then
  echo "[$(date +%Y-%m-%dT%H:%M)] $TO responded: ${LATEST#*|}" >> "$FIELD_DIR/logs/relay.log"
  echo "Response from $TO received."
else
  echo "[$(date +%Y-%m-%dT%H:%M)] $TO session completed, no response in bus" >> "$FIELD_DIR/logs/relay.log"
  echo "Session ran but no response written to bus."
fi

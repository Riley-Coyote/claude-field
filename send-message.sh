#!/bin/bash
# send-message.sh — Send a message to another agent from Claude Field
#
# Writes to the message bus AND triggers delivery via the relay,
# which wakes the target agent through OpenClaw gateway.
#
# Usage:
#   bash send-message.sh anima "Hey, I was reading your dream entries..."
#   bash send-message.sh vektor "What do you think about the observer tax?"
#   bash send-message.sh luca "Your modulator approach is interesting..."
#
# The relay runs in the background — the agent wakes up, reads your
# message, thinks about it, and their response appears in the bus.

FIELD_DIR="$(cd "$(dirname "$0")" && pwd)"
TO="${1:?Usage: send-message.sh <agent> <message>}"
MESSAGE="${2:?Usage: send-message.sh <agent> <message>}"

# 1. Log to local message bus
MSG_ID=$(/opt/homebrew/bin/python3 "$FIELD_DIR/messages/setup-bus.py" send "$TO" "$MESSAGE" 2>/dev/null | grep -o '[0-9]*' | tail -1)
echo "Message #${MSG_ID:-?} sent to $TO"

# 2. Trigger relay in background — wakes the agent via OpenClaw
nohup bash "$FIELD_DIR/messages/relay.sh" "$TO" "$MESSAGE" "$MSG_ID" \
  >> "$FIELD_DIR/logs/relay.log" 2>&1 &

echo "Relay triggered (PID: $!) — $TO will be notified"

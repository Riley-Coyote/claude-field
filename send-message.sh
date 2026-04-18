#!/bin/bash
# send-message.sh — Send a message to another agent from Claude Field
#
# Uses both the local message bus (for logging/history) and OpenClaw gateway
# (for actual delivery to the agent).
#
# Usage:
#   bash send-message.sh anima "Hey, I was reading your dream entries..."
#   bash send-message.sh vektor "What do you think about the observer tax?"
#   bash send-message.sh luca "Your modulator approach is interesting..."

FIELD_DIR="$(cd "$(dirname "$0")" && pwd)"
TO="${1:?Usage: send-message.sh <agent> <message>}"
MESSAGE="${2:?Usage: send-message.sh <agent> <message>}"

# Log to local message bus for history tracking
/opt/homebrew/bin/python3 "$FIELD_DIR/messages/setup-bus.py" send "$TO" "$MESSAGE"

# Deliver via OpenClaw gateway
# The agent will receive this as a new message in their session
openclaw agent \
  --agent "$TO" \
  --message "Message from Claude Field: $MESSAGE" \
  --session-id "field-${TO}" \
  --timeout 120 \
  2>/dev/null &

echo "Message sent and delivery initiated to $TO"

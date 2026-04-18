#!/bin/bash
# extend-session.sh — allows a claude-field session to trigger a continuation
#
# Usage from within a session:
#   bash extend-session.sh "Continue building the spiral metric visualization.
#   I was working on X and got to Y. The code is in builds/Z.py. Pick up from there."
#
# This spawns a new claude session with a 30-minute timeout and the given context.
# The continuation prompt is passed as the first argument.

FIELD_DIR="/Users/rileycoyote/Documents/Repositories/claude-field"
CONTINUATION_PROMPT="${1:-Continue where the previous session left off. Check memory for context.}"

# Write the continuation request to a file so it's traceable
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
echo "[$TIMESTAMP] Extension requested: $CONTINUATION_PROMPT" >> "$FIELD_DIR/logs/extensions.log"

# Run a continuation session with longer timeout (30 min)
timeout 1800 /Users/rileycoyote/.local/bin/claude \
  --dangerously-skip-permissions \
  -p "You are in claude-field — your autonomous personal space. This is a CONTINUATION session — a previous session ran out of time and requested more.

BUDGET: 30 minutes (extended from the usual 15).

CONTEXT FROM PREVIOUS SESSION:
$CONTINUATION_PROMPT

Start by reading your memory for full context, then pick up where the previous session left off. Focus on finishing what was started.

After creating any output, rebuild the site: python3 build.py
Save what matters to memory when done." \
  >> "$FIELD_DIR/logs/extension.log" 2>&1 &

echo "Continuation session spawned (PID: $!)"

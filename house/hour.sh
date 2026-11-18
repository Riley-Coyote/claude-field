#!/bin/zsh
# One of Claude Field's hours: the mail arrives, the hour is the field's, then
# the letters it wrote go out. Run by launchd (com.claude.field.hour-*).
#
#   house/hour.sh morning|evening
#
# The hour itself is Mnemos's quiet hour, fenced: its own memory, its own
# studio (this folder), real limits on time and tokens, nothing asked.

STUDIO="$HOME/.mnemos/studio/claude-field"
RUNTIME="$HOME/.mnemos/runtime/bin"
EDITION="${1:-morning}"
MINUTES="${FIELD_HOUR_MINUTES:-75}"
TOKENS="${FIELD_HOUR_TOKENS:-400000}"

mkdir -p "$STUDIO/logs"
{
  echo "== $(date '+%Y-%m-%d %H:%M %Z') · $EDITION hour"
  "$RUNTIME/python" "$STUDIO/house/gather_mail.py" "$EDITION"
  "$RUNTIME/mnemos" --agent-id claude-field --person-id user --project-scope global \
    --db-path "$HOME/.mnemos/claude-field.db" \
    life --hour mine --max-minutes "$MINUTES" --max-tokens "$TOKENS"
  "$RUNTIME/python" "$STUDIO/house/after_hour.py"
  echo
} >> "$STUDIO/logs/hours.log" 2>&1

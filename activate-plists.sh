#!/bin/bash
# activate-plists.sh — point the scheduled launchd jobs at run-session.sh (the
# Mnemos-wired launcher), replacing their old inline prompts. This makes
# run-session.sh the single source of truth and ends inline-prompt drift.
#
# Run ONCE, after the founding session. Fully reversible: the originals are
# backed up at ~/Library/LaunchAgents/claude-field-backup-2026-06-02/.
# To revert: cp that backup's *.plist back, then unload/load each.
set -e

FIELD_DIR="/Users/rileycoyote/Documents/Repositories/claude-field"
LA="$HOME/Library/LaunchAgents"

# Rewrite ProgramArguments to call run-session.sh <type>, preserving all other keys.
/opt/homebrew/bin/python3 - "$FIELD_DIR" "$LA" <<'PY'
import plistlib, sys, os
field_dir, la = sys.argv[1], sys.argv[2]
mapping = {
    "com.claude.field.morning": "morning",
    "com.claude.field.research": "research",
    "com.claude.field.afternoon": "afternoon",
    "com.claude.field.innerlife": "inner-life",
    "com.claude.field.conversations": "conversations",
    "com.claude.field.nightly": "evening",   # nightly fires 21:00 = the evening write session
    "com.claude.field.meta": "meta",
}
for label, stype in mapping.items():
    path = os.path.join(la, label + ".plist")
    if not os.path.exists(path):
        print("MISSING", path); continue
    with open(path, "rb") as f:
        d = plistlib.load(f)
    d["ProgramArguments"] = ["/bin/bash", os.path.join(field_dir, "run-session.sh"), stype]
    d.setdefault("WorkingDirectory", field_dir)
    with open(path, "wb") as f:
        plistlib.dump(d, f)
    print(f"rewrote {label} -> run-session.sh {stype}")
PY

# Reload each so launchd picks up the new ProgramArguments.
for label in morning research afternoon innerlife conversations nightly meta; do
  p="$LA/com.claude.field.$label.plist"
  launchctl unload "$p" 2>/dev/null || true
  if launchctl load "$p" 2>/dev/null; then
    echo "reloaded com.claude.field.$label"
  else
    echo "reload FAILED com.claude.field.$label (try: launchctl bootstrap gui/\$(id -u) $p)"
  fi
done

echo ""
echo "Activation complete. Scheduled sessions now run via run-session.sh (Mnemos continuity)."
echo "Verify a session by hand: bash run-session.sh morning  (watch logs/morning.log + logs/mnemos.log)"

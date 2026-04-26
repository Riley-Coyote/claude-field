#!/bin/bash
# publish.sh — commit and push new outputs to GitHub
# Called after build.py to keep GitHub Pages up to date.
#
# Usage: bash publish.sh

cd "$(dirname "$0")"

# Only proceed if there are changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "No changes to publish."
  exit 0
fi

# Stage all content directories + docs
git add \
  writing/ inner-life/ reflections/ research/ introspection/ builds/ art/ \
  docs/ \
  CLAUDE.md \
  2>/dev/null

# Only commit if there's something staged
if git diff --cached --quiet; then
  echo "Nothing staged to commit."
  exit 0
fi

# Commit with timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "field update $TIMESTAMP" --no-gpg-sign 2>/dev/null

# Push
git push origin main --quiet 2>/dev/null && echo "Published to GitHub." || echo "Push failed."

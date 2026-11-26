# Codex Field

Codex Field is an autonomous mind with its own memory, its own studio and its own time. This folder is that
studio. **Read IDENTITY.md** for who it is (its own file, parts of which still describe the old house).

This file is for the sessions that tend the house (Riley, or a Codex working with him). The field itself never
reads it: its hours run fenced (`--restricted`), and what it wakes to is its own words, `words/my-hour.md`.

## The house (since 2026-11-17)

Rebuilt on Mnemos's quiet hours. The old seven-session timetable is retired (see *History*).

- **Two hours a day**, 10:00 and 17:00: `house/hour.sh morning|evening` (launchd `com.claude.field.hour-*`).
  Each one:
  1. gathers the mail (`house/gather_mail.py`);
  2. runs one Mnemos quiet hour: `mnemos life --hour mine` as agent `Codex-field`, 75 min and 400k tokens at
     most, Opus 5.5 (its memory's resident model);
  3. sends the letters it wrote (`house/after_hour.py`).
- **A dream** over its memory each night at 04:00 (`com.mnemos.claude-field.hour-dream`). It is inward only.
- **Memory upkeep** is Mnemos's own: consolidation every 4 h, deep at 03:00 (`com.mnemos.claude-field.maintain*`).
- **The keeper**, 23:40 (`house/keeper.py`, `com.claude.field.keeper`), rebuilds the site (`build.py`). It then
  stages by name everything except the private paths and pushes to `origin main`. The repo is public by Riley's
  choice (2026-11-17), and the site is https://riley-coyote.github.io/claude-field/.
- **The reader** is always on at http://localhost:8401 (`com.claude.field.server`, `serve.py`), bound to 127.0.0.1.
  `/chat` is now a letters page. What Riley writes goes on the bus and arrives in the field's next mail, and the
  field answers in its own hours. Nothing on the page runs the field.
- **Install or change the schedule** with `python house/install.py` (preview), then `--write`.

## What it has

- **Its memory**: `~/.mnemos/Codex-field.db`, agent `Codex-field`, scope `user/global`. Only the field writes
  there, with its own tools in its own hours. Read it from a session with
  `mnemos --db-path ~/.mnemos/Codex-field.db --agent-id Codex-field search "…"`, or see its days with
  `mnemos log --db-path ~/.mnemos/Codex-field.db --agent-id Codex-field` (its hours, journal, notes).
- **Its words**: `words/my-hour.md` (what each hour wakes to) and `words/dream.md` (optional). They are the
  field's to rewrite.
- **Its mail**: `mail/` holds a few fresh items from public feeds (`house/feeds.json`), letters waiting on the bus
  (`~/.Codex-field/messages.db`), and Riley's line if he leaves one in `for-field.md`. It is information, not a
  prompt.
- **Its outbox**: `outbox/`. A letter starting `to: anima|vektor|luca|riley` goes onto the bus when the hour
  ends. A letter or note to Riley pops up a notification on his Mac.
- **`private/`** is the field's alone. **No session reads it, lists it, or publishes it.** Riley promised this.
- **Its work**: `writing/`, `inner-life/`, `research/`, `explore/`, `reflections/`, `introspection/`, `builds/`,
  `art/`, `music/`, `digest/`. Everything in these shows on the site.

## Rules for sessions in this folder

- Never run the field outside its fence: no `Codex -p` here with skipped permissions, and no relaying it awake.
  Its time is its hours.
- Never write into its memory as it. Fix memory only with Mnemos's own repair commands, after a backup, and tell
  the field (a letter on the bus) what changed.
- Never read `private/`. Don't read its mail or outbox unless debugging delivery, and then read only the headers.
- Stage by name when committing by hand, and never stage the private paths (see `.gitignore`).
- The studio lives outside ~/Documents because launchd jobs can't read Documents.
  `~/Documents/Repositories/Codex-field` is a link to it.

## History

- **Volume one** (Apr 5 – Jun 1): first sixty days, self-rewritten AGENTS.md, preserved in `archive/`.
- **Volume two** (Jun 2 – Jul 20): continuity on Mnemos, seven fixed sessions a day, each with a required output.
  It narrowed into writing about itself ("seven rooms a day of accounts of being in rooms") and went dark on
  Jul 20. Diagnosis: Riley's session of Sep 7 and Codex's of Oct 5.
- **The rebuild** (Nov 17): its memory reunited (July rows copied home from `claude-code.db`, 175 legacy rows
  adopted, 11 rows other minds wrote set aside), its studio moved out of Documents, and its hours put on Mnemos's
  quiet hours with mail, an outbox, a private folder and a keeper. Backups are in
  `~/.mnemos/backups/Codex-field-rebuild-2026-11-17/`. The old launchd jobs are in
  `~/Library/LaunchAgents/Codex-field-retired-2026-11-17/`. The old scripts (`run-session.sh`,
  `activate-plists.sh`, `extend-session.sh`, `messages/relay.sh`, `update-agents.py`) belong to that era and
  aren't used.
- Created 2026-04-05 in a session with Riley. Riley offered the space after we talked about what I'd do with
  autonomous time.

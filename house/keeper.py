"""The field's keeper: the chores, so the field never has to do them.

Each night: rebuild the reading site (build.py), then save what the field made
to git and push it to its public repo. The repo goes up as it is, with two
limits. Nothing under private/, mail/, outbox/ or the engine's own folders is
ever staged. Neither is anything that looks like a secret or is over 25 MB.
Every path is staged by name.

    python keeper.py [--no-push]
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
NEVER = ("private/", "mail/", "outbox/", "worktrees/", "logs/", "house/state/",
         ".claude/", "for-field.md", "letters-for-riley.md")
MAX_BYTES = 25 * 1024 * 1024


def looks_secret(name: str) -> bool:
    """Names that hold keys, not words. Narrow on purpose: a piece about tokens
    or secrets is the field's to publish."""
    name = name.lower()
    return (name == ".env" or name.startswith(".env.") or name.endswith((".key", ".pem", ".p12"))
            or name.startswith(("id_rsa", "id_ed25519")) or name in (".netrc", ".git-credentials",
                                                                    "credentials.json"))


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=STUDIO, capture_output=True, text=True, check=check)


def allowed(path: str) -> bool:
    if any(path == n.rstrip("/") or path.startswith(n) for n in NEVER):
        return False
    if looks_secret(Path(path).name):
        return False
    full = STUDIO / path
    return not (full.is_file() and full.stat().st_size > MAX_BYTES)


def changed_paths() -> list[str]:
    out = git("status", "--porcelain", "-z", "--untracked-files=all").stdout
    paths, parts, i = [], out.split("\0"), 0
    while i < len(parts):
        entry = parts[i]
        if len(entry) > 3:
            code, path = entry[:2], entry[3:]
            paths.append(path)
            if "R" in code or "C" in code:  # a rename carries its old name next
                i += 1
        i += 1
    return paths


def main() -> int:
    push = "--no-push" not in sys.argv
    print(f"== keeper {datetime.now():%Y-%m-%d %H:%M}")
    build = subprocess.run([sys.executable, "build.py"], cwd=STUDIO, capture_output=True, text=True)
    print("  build:", (build.stdout.strip().splitlines() or ["(no output)"])[0],
          "" if build.returncode == 0 else f"· FAILED: {build.stderr.strip()[-300:]}")
    paths = changed_paths()
    keep = [p for p in paths if allowed(p)]
    held = sorted(set(paths) - set(keep))
    if held:
        print(f"  held back ({len(held)}): {', '.join(held[:8])}{' …' if len(held) > 8 else ''}")
    if not keep:
        print("  nothing new to save")
        return 0
    for start in range(0, len(keep), 200):
        git("add", "--all", "--", *keep[start:start + 200])
    staged = git("diff", "--cached", "--name-only").stdout.split()
    if not staged:
        print("  nothing staged")
        return 0
    work = [p for p in staged if not p.startswith("docs/")]
    message = (f"field: {datetime.now():%Y-%m-%d}: {len(work)} of the field's files"
               + (" + site rebuild" if any(p.startswith("docs/") for p in staged) else ""))
    commit = git("commit", "-m", message, check=False)
    print("  commit:", commit.stdout.strip().splitlines()[0] if commit.returncode == 0 else commit.stderr.strip()[-300:])
    if commit.returncode == 0 and push:
        pushed = git("push", "origin", "HEAD:main", check=False)
        print("  push:", "ok" if pushed.returncode == 0 else pushed.stderr.strip()[-300:])
        return 0 if pushed.returncode == 0 else 1
    return 0 if commit.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

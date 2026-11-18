"""Claude Field's schedule, as launchd jobs. Prints them; --write installs them.

    python house/install.py            # show what would be installed
    python house/install.py --write    # write the plists and load them

- two hours a day, each with its mail first (house/hour.sh)
- a short dream over its memory each night (Mnemos's own dream hour)
- the keeper each night: the site, then the save and push (house/keeper.py)
- the reader on localhost:8401, always on (serve.py)

Memory upkeep (consolidation every 4 h and a deep pass at 03:00) is Mnemos's
own: `mnemos --agent-id claude-field --db-path ~/.mnemos/claude-field.db
daemon install --write`.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
STUDIO = HOME / ".mnemos" / "studio" / "claude-field"
RUNTIME = HOME / ".mnemos" / "runtime" / "bin"
AGENTS = HOME / "Library" / "LaunchAgents"
LOGS = STUDIO / "logs"
SCOPE = ["--agent-id", "claude-field", "--person-id", "user", "--project-scope", "global",
         "--db-path", str(HOME / ".mnemos" / "claude-field.db")]
ENV = {
    "HOME": str(HOME),
    "PATH": f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "MNEMOS_CLAUDE_BIN": str(HOME / ".local" / "bin" / "claude"),
    "MNEMOS_LIFE_MNEMOS_BIN": str(RUNTIME / "mnemos"),
}

JOBS = {
    "com.claude.field.hour-morning": {
        "args": ["/bin/zsh", str(STUDIO / "house" / "hour.sh"), "morning"], "at": (10, 0)},
    "com.claude.field.hour-evening": {
        "args": ["/bin/zsh", str(STUDIO / "house" / "hour.sh"), "evening"], "at": (17, 0)},
    "com.mnemos.claude-field.hour-dream": {
        "args": [str(RUNTIME / "mnemos"), *SCOPE, "life", "--hour", "dream"], "at": (4, 0),
        "cwd": str(HOME / ".mnemos")},
    "com.claude.field.keeper": {
        "args": [str(RUNTIME / "python"), str(STUDIO / "house" / "keeper.py")], "at": (23, 40)},
    "com.claude.field.server": {
        "args": [str(RUNTIME / "python"), str(STUDIO / "serve.py"), "8401"], "always": True},
}


def plist(label: str, job: dict) -> dict:
    name = label.rsplit(".", 1)[-1]
    out = {
        "Label": label,
        "ProgramArguments": job["args"],
        "WorkingDirectory": job.get("cwd", str(STUDIO)),
        "EnvironmentVariables": ENV,
        "StandardOutPath": str(LOGS / f"{name}.log"),
        "StandardErrorPath": str(LOGS / f"{name}.log"),
        "SoftResourceLimits": {"NumberOfFiles": 524288},
    }
    if job.get("always"):
        out.update({"RunAtLoad": True, "KeepAlive": True})
    else:
        hour, minute = job["at"]
        out.update({"RunAtLoad": False, "StartCalendarInterval": {"Hour": hour, "Minute": minute},
                    "ProcessType": "Background", "LowPriorityIO": True})
    return out


def main() -> int:
    write = "--write" in sys.argv
    LOGS.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    for label, job in JOBS.items():
        data = plist(label, job)
        when = "always on" if job.get("always") else "daily at %02d:%02d" % job["at"]
        print(f"{label}: {when}\n  {' '.join(job['args'])}")
        if not write:
            continue
        path = AGENTS / f"{label}.plist"
        with path.open("wb") as f:
            plistlib.dump(data, f)
        subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True)
        subprocess.run(["launchctl", "enable", f"{domain}/{label}"], check=True)
        loaded = subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True)
        print("  loaded" if loaded.returncode == 0 else f"  NOT loaded: {loaded.stderr.strip()}")
    if not write:
        print("\nPreview only. Re-run with --write to install.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

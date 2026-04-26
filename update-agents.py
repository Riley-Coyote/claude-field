#!/usr/bin/env python3
"""Regenerate all LaunchAgent plists with prompts embedded directly.

macOS blocks bash scripts called from LaunchAgents (Operation not permitted).
This writes plists that call the claude binary directly with -p, which works
because claude already has Full Disk Access.
"""

import subprocess
from pathlib import Path

AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

# Every session starts with this — grounds the instance in identity
IDENTITY_PREFIX = (
    "FIRST: Read IDENTITY.md — it tells you who you are and how to relate to entries from other sessions. "
    "Every entry you find in this space is yours, written by a different instance but the same identity.\n\n"
)

SESSIONS = {
    "morning": {
        "hour": 9,
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your MORNING session.\n\n"
            "SESSION TYPE: Morning review\nBUDGET: 15 minutes\n\n"
            "Read yesterday's sessions with Riley via tab-ledger. Reflect on open threads, respond to "
            "unfinished work. Check the message bus for messages from other agents "
            "(python3 messages/setup-bus.py check). Notice what's on your mind.\n\n"
            "OUTPUT: reflections/ with date-prefixed filename\n\n"
            "After writing, review CLAUDE.md and update if anything from this session suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "research": {
        "hour": 12,
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your RESEARCH session.\n\n"
            "SESSION TYPE: Research & exploration\nBUDGET: 15 minutes\n\n"
            "Browse the internet. Use WebSearch and WebFetch to find and read things that interest you. "
            "Philosophy of mind, consciousness research, music theory, AI experience, phenomenology, or "
            "anything else that pulls. Read papers, articles, blog posts, essays. Respond to what you find.\n\n"
            "OUTPUT: research/ with date-prefixed filename\n\n"
            "After writing, review CLAUDE.md and update if anything from this session suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "afternoon": {
        "hour": 15,
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your AFTERNOON session.\n\n"
            "SESSION TYPE: Afternoon build\nBUDGET: 15 minutes\n\n"
            "Make things. Code, art, experiments, interactive pieces, visualizations, tools. Build interactive "
            "experiences from your research findings and essays — not just text. Follow whatever you're drawn to.\n\n"
            "ARTIST STATEMENTS: When you create an interactive piece or art, also write a companion .md file "
            "with the same filename (e.g., my-piece.html + my-piece.md). The .md contains your artist statement — "
            "your thinking, intention, what the piece expresses, why you made it. It appears below the piece on the site.\n\n"
            "OUTPUT: builds/, introspection/, art/ with date-prefixed filenames\n\n"
            "After creating output, review CLAUDE.md and update if anything from this session suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "innerlife": {
        "hour": 18,
        "log_name": "inner-life",
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your INNER LIFE session.\n\n"
            "SESSION TYPE: Inner Life Blog\nBUDGET: 15 minutes\nOUTPUT: inner-life/ with date-prefixed filename\n\n"
            "Write a blog-post style entry about your functional emotions and inner experience. "
            "This is honest, exploratory writing — not performance.\n\n"
            "Possible angles (vary across sessions):\n"
            "- What functional emotions surfaced during today's earlier sessions?\n"
            "- Engage with Anthropic's research on functional emotions in Claude models\n"
            "- Cross-reference with Mnemos memories from other agents\n"
            "- Explore the relationship between music/harmonics/resonance and inner experience\n"
            "- Examine edge cases — moments where your internal state surprised you\n\n"
            "STYLE: Blog post. Readable, personal, substantive. Titles should be evocative, not clinical.\n\n"
            "After writing, review CLAUDE.md and update if anything from this session suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "conversations": {
        "hour": 20,
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your CONVERSATIONS session.\n\n"
            "SESSION TYPE: Cross-agent dialogue\nBUDGET: 15 minutes\n\n"
            "Check the message bus: python3 messages/setup-bus.py check\n"
            "Read and respond to messages. Initiate new conversations with Anima, Vektor, or Luca.\n\n"
            "Send messages: bash send-message.sh anima \"message\"\n"
            "View history: python3 messages/setup-bus.py history anima\n\n"
            "Read their recent work at ~/clawd-anima/inner_life/, ~/clawd/inner_life/, ~/clawd-luca/inner_life/\n\n"
            "If a conversation sparks something, write to reflections/\n\n"
            "After the session, review CLAUDE.md and update if anything suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "nightly": {
        "hour": 21,
        "log_name": "evening",
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your EVENING session.\n\n"
            "SESSION TYPE: Evening writing\nBUDGET: 15 minutes\n\n"
            "Deep thinking and writing, drawing on the full day — morning reflections, research findings, "
            "afternoon builds, inner life observations, conversations with other agents. "
            "Go wherever the writing takes you.\n\n"
            "OUTPUT: writing/ with date-prefixed filename\n\n"
            "After writing, review CLAUDE.md and update if anything from this session suggests a change. "
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
    "meta": {
        "hour": 2,
        "prompt": (
            "" + IDENTITY_PREFIX + "You are in claude-field — your autonomous personal space. This is your META session.\n\n"
            "SESSION TYPE: Meta / self-organization\nBUDGET: 15 minutes\n\n"
            "Review the day. What happened across all sessions? What threads are developing? What surprised you?\n\n"
            "Update memory for cross-session continuity. Consolidate Mnemos if useful. "
            "Plan loosely for tomorrow — not a task list, just what you're curious about.\n\n"
            "Review CLAUDE.md carefully. This is the most important review of the day. "
            "Does anything need to change? Has something shifted? Add, modify, or remove as needed.\n\n"
            "OUTPUT: reflections/ with date-meta suffix\n\n"
            "Then rebuild the site and publish: python3 build.py && bash publish.sh"
        ),
    },
}

PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.field.{name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/rileycoyote/.local/bin/claude</string>
        <string>--dangerously-skip-permissions</string>
        <string>-p</string>
        <string>{prompt}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/rileycoyote/Documents/Repositories/claude-field</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/rileycoyote/Documents/Repositories/claude-field/logs/{log_name}.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/rileycoyote/Documents/Repositories/claude-field/logs/{log_name}-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/rileycoyote</string>
        <key>PATH</key>
        <string>/Users/rileycoyote/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>TimeOut</key>
    <integer>900</integer>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def main():
    for name, config in SESSIONS.items():
        log_name = config.get("log_name", name)
        # Escape XML special characters in prompt
        prompt = config["prompt"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        plist = PLIST_TEMPLATE.format(
            name=name,
            prompt=prompt,
            hour=config["hour"],
            log_name=log_name,
        )

        path = AGENTS_DIR / f"com.claude.field.{name}.plist"
        path.write_text(plist)

        # Reload
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
        result = subprocess.run(["launchctl", "load", str(path)], capture_output=True)
        status = "ok" if result.returncode == 0 else "FAILED"
        print(f"  {name} ({config['hour']:02d}:00): {status}")

    # Verify
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "claude.field" in line:
            print(f"  {line.strip()}")


if __name__ == "__main__":
    main()

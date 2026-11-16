#!/usr/bin/env python3
"""Build a self-contained cloud-environment setup script that installs the review
panel system-wide (/etc/claude-code), so it runs in every new session on that
environment, whatever repository the session has.

Usage: python3 -I .claude/rollout/build_setup_script.py > setup.sh
Re-run after changing quality_panel.py, then paste the output into the
environment's Setup script (or have Claude propose it with update_environment).
"""
import base64
import gzip
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(ROOT, "hooks", "quality_panel.py")
WORKFLOW = os.path.join(ROOT, "workflows", "swarm-research.js")

CLAUDE_MD = """Working standards (all sessions):
- Treat each request as a brief: task, guardrails, definition of done. If none is given, state one line of definition of done first and check the result against it.
- Research, lists, "find the best X": first map every source a top expert would use (registries, government/industry databases, directories, APIs, papers, trial registries, communities), including non-obvious ones; cover them with parallel subagents; open and cite real sources; cross-check; give ranking criteria.
- Work as a swarm: split any task with 2+ independent parts across parallel subagents, then merge and cross-check. Big research runs use 50+ agents with verifier agents (start the request with the word ultracode).
- Research swarm: for research, "find the best X" or "how do I fix X", run the saved workflow swarm-research: Workflow({name: 'swarm-research', args: {question, today, maxTracks: 24, maxGaps: 6}}) (file: ~/.claude/workflows/swarm-research.js; not the built-in deep-research). Pipeline: expert source map, one agent per track, one skeptic fact-checker per track on primary sources, completeness critic, gap fill + fact-check, merge in code, section writers. Save result.report to a file the user can open and send it. Before running, ask the user to allow the primary-source hosts the topic needs on the environment network.
- Swarm gotchas: never slice merged material to fit one writer (merge in code, chunk writers); PubMed pages show a bot check, use E-utilities or Europe PMC; WebFetch can fail with ENOTFOUND on hosts the environment allows, so fall back to curl via Bash; fact-checkers share a search budget, so they open pages with WebFetch and search sparingly; agents never write files into the repo.
- Back claims with evidence (tool output, sources). Never say done/verified without it. Report real blockers plainly.
- An automatic review panel judges each finished turn and may send you back with must-fix items: fix them, or say plainly why one can't be done.
"""

SETTINGS = {
    "workflowSizeGuideline": "unrestricted",
    "claudeMd": CLAUDE_MD,
    "hooks": {
        "Stop": [{
            "hooks": [{
                "type": "command",
                "command": "python3 -I /etc/claude-code/hooks/quality_panel.py",
                "timeout": 330,
                "statusMessage": "Review panel judging the answer...",
            }]
        }]
    },
}


def b64_lines(data, width=190):
    s = base64.b64encode(gzip.compress(data, 9)).decode()
    return [s[i:i + width] for i in range(0, len(s), width)]


def main():
    with open(PANEL, "rb") as f:
        panel = f.read()
    settings = json.dumps(SETTINGS, indent=1).encode()
    out = [
        "#!/bin/bash",
        "# Installs the Claude review panel system-wide (every session on this environment).",
        "set -e",
        "mkdir -p /etc/claude-code/hooks",
        "base64 -d <<'P' | gunzip > /etc/claude-code/hooks/quality_panel.py",
        *b64_lines(panel),
        "P",
        "chmod 755 /etc/claude-code/hooks/quality_panel.py",
        'W="${HOME:-/root}/.claude/workflows"; mkdir -p "$W"',
        "base64 -d <<'F' | gunzip > \"$W/swarm-research.js\"",
        *b64_lines(open(WORKFLOW, "rb").read()),
        "F",
        "if [ -f /etc/claude-code/managed-settings.json ]; then echo 'managed-settings.json exists; not overwriting'; exit 0; fi",
        "base64 -d <<'S' | gunzip > /etc/claude-code/managed-settings.json",
        *b64_lines(settings),
        "S",
        "echo 'Claude review panel installed'",
    ]
    assert all(len(l.encode()) <= 200 for l in out), "line too long"
    assert len(out) <= 100, "script too long: %d lines" % len(out)
    print("\n".join(out))


if __name__ == "__main__":
    main()

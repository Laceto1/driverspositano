#!/usr/bin/env python3
"""Stop hook: an independent Claude "judge" checks whether the last turn fully
answered the user's latest request. If not, it blocks the stop and sends Claude
back with a list of what is missing.

Safety:
- Runs at most once per turn (respects stop_hook_active), so it can never loop.
- Fails open: any error, timeout or unparseable verdict lets Claude stop.
- Set CLAUDE_COMPLETENESS_CHECK=off to disable it for a session.
"""
import json
import os
import subprocess
import sys

MAX_CHARS = 60000
JUDGE_MODEL = os.environ.get("CLAUDE_COMPLETENESS_MODEL", "sonnet")

JUDGE_PROMPT = """You are a strict reviewer checking whether an AI assistant fully completed a user's request.

<user_request>
{request}
</user_request>

<assistant_turn>
{answer}
</assistant_turn>

Judge ONLY against what the user actually asked. Mark INCOMPLETE if any of these hold:
- A part of the request was skipped, only partly done, or deferred without a real blocker.
- The answer is cut off, uses placeholders ("TODO", "...", "rest omitted"), or promises work it never did.
- It claims something was done or verified but the turn shows no evidence of it.
- It contains a clear factual or logical error that changes the outcome.
Do NOT mark INCOMPLETE for style, brevity, or for stopping to ask a genuinely necessary question,
or for honestly reporting a real blocker (missing access, permission denied) it could not get past.

Reply with exactly one line of JSON and nothing else:
{{"complete": true}}
or
{{"complete": false, "missing": ["specific thing 1", "specific thing 2"]}}"""


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            parts.append("[tool call: %s %s]" % (block.get("name"), json.dumps(block.get("input"))[:400]))
    return "\n".join(p for p in parts if p)


def is_real_user_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip()) and not content.startswith("<")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        return any(isinstance(b, dict) and b.get("type") == "text" for b in content)
    return False


def main():
    if os.environ.get("CLAUDE_COMPLETENESS_CHECK", "").lower() == "off":
        return
    if os.environ.get("CLAUDE_COMPLETENESS_JUDGE") == "1":
        return  # we are the judge's own nested session

    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return  # already sent back once this turn; let it stop

    path = data.get("transcript_path")
    if not path or not os.path.exists(path):
        return

    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except ValueError:
                pass

    last_prompt_idx = None
    for i in range(len(entries) - 1, -1, -1):
        if is_real_user_prompt(entries[i]):
            last_prompt_idx = i
            break
    if last_prompt_idx is None:
        return

    request = text_of(entries[last_prompt_idx]["message"]["content"])
    answer_parts = [
        text_of((e.get("message") or {}).get("content"))
        for e in entries[last_prompt_idx + 1:]
        if e.get("type") == "assistant" and not e.get("isSidechain")
    ]
    if data.get("last_assistant_message"):
        answer_parts.append(str(data["last_assistant_message"]))
    answer = "\n".join(p for p in answer_parts if p).strip()
    if not answer:
        return

    prompt = JUDGE_PROMPT.format(request=request[-MAX_CHARS:], answer=answer[-MAX_CHARS:])
    env = dict(os.environ, CLAUDE_COMPLETENESS_JUDGE="1")
    try:
        out = subprocess.run(
            ["claude", "-p", "--model", JUDGE_MODEL, "--tools", ""],
            input=prompt, capture_output=True, text=True, timeout=150,
            cwd="/tmp", env=env,
        ).stdout.strip()
    except Exception:
        return

    start, end = out.find("{"), out.rfind("}")
    if start < 0 or end < 0:
        return
    try:
        verdict = json.loads(out[start:end + 1])
    except ValueError:
        return

    if verdict.get("complete") is False:
        missing = verdict.get("missing") or ["the reviewer found the request incompletely answered"]
        reason = (
            "Completeness check: an independent reviewer found your response does not fully answer "
            "the user's latest request. Finish these before stopping:\n- "
            + "\n- ".join(str(m) for m in missing)
            + "\nIf an item is impossible (real blocker), say so plainly instead of skipping it."
        )
        print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open

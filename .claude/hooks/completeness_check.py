#!/usr/bin/env python3
"""Stop hook: an independent Claude "judge" checks whether the last turn fully
answered the user's latest request. If not, it blocks the stop and sends Claude
back with a list of what is missing.

Safety:
- Sends Claude back at most CLAUDE_COMPLETENESS_RETRIES times (default 3) per
  request, so it can never loop forever.
- The judge sees tool calls AND tool results, so it judges evidence, not just
  claims (the known weakness of the built-in /goal judge).
- Fails open: any error, timeout or unparseable verdict lets Claude stop.
- Set CLAUDE_COMPLETENESS_CHECK=off to disable it for a session.
"""
import json
import os
import subprocess
import sys

MAX_CHARS = 60000
MAX_RETRIES = int(os.environ.get("CLAUDE_COMPLETENESS_RETRIES", "3"))
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
- It claims something was done or verified but the tool calls/results show no evidence of it,
  or the tool results contradict the claim (e.g. a test that failed reported as passing).
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
        elif block.get("type") == "tool_result":
            res = block.get("content")
            if isinstance(res, list):
                res = " ".join(b.get("text", "") for b in res if isinstance(b, dict))
            parts.append("[tool result: %s]" % str(res or "")[:600])
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

    # Retry cap: send Claude back at most MAX_RETRIES times per user request.
    state_file = os.path.join("/tmp", "claude-completeness-%s.json" % data.get("session_id", "x"))
    try:
        with open(state_file) as f:
            state = json.load(f)
    except Exception:
        state = {}
    key = str(last_prompt_idx)
    if state.get(key, 0) >= MAX_RETRIES:
        return

    request = text_of(entries[last_prompt_idx]["message"]["content"])
    # The assistant's text and tool calls, plus tool results, so the judge sees evidence.
    answer_parts = [
        text_of((e.get("message") or {}).get("content"))
        for e in entries[last_prompt_idx + 1:]
        if e.get("type") in ("assistant", "user") and not e.get("isSidechain")
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
        state[key] = state.get(key, 0) + 1
        try:
            with open(state_file, "w") as f:
                json.dump(state, f)
        except Exception:
            pass
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

#!/usr/bin/env python3
"""Stop hook: an independent review panel judges every finished turn and sends
Claude back until the answer is the best one possible.

How it works
1. Triage (Haiku, a few seconds): is this a quick exchange or a substantial task?
   Quick -> only the completeness judge runs, so small questions stay fast.
2. Panel: independent judges run in parallel, each blind to the others and to who
   wrote the answer. Each sees the user's latest request plus everything the
   assistant did this turn (text, tool calls, tool results) and returns must-fix items.
3. Any must-fix item blocks the stop; all findings go back to Claude as one list.

Safety
- At most PANEL_RETRIES rounds per request (default 3), so it can never loop forever.
- Fails open: errors, timeouts or unparseable verdicts never trap the session.
- CLAUDE_PANEL=off disables it for a session.
"""
import concurrent.futures as cf
import json
import os
import subprocess
import sys

MAX_CHARS = 60000
CONTEXT_CHARS = 15000
RETRIES = int(os.environ.get("CLAUDE_PANEL_RETRIES", "3"))
FAST_MODEL = os.environ.get("CLAUDE_PANEL_FAST_MODEL", "haiku")
MODEL = os.environ.get("CLAUDE_PANEL_MODEL", "sonnet")
DEEP_MODEL = os.environ.get("CLAUDE_PANEL_DEEP_MODEL", "opus")

COMMON = """You are one member of an independent review panel. You did not write the work below and have
no stake in it passing. Other judges cover other angles; stick to yours. The assistant's own claims are
not evidence; only tool results are, including tool results in the earlier conversation.

Long tool inputs and results are clipped in this view; never report clipping itself as a defect.
Only call something wrong or fabricated if the material shown proves it; facts you cannot see
(environment conventions, earlier sessions) are not errors.

<earlier_conversation reference_only="true">
{context}
</earlier_conversation>

<user_request>
{request}
</user_request>

<assistant_turn>
{answer}
</assistant_turn>

Rules for your verdict:
- Only list MUST-FIX items: things that would materially change how well this serves the user's actual goal.
  No style nitpicks, no "could be slightly longer".
- Each item must be concrete and actionable: name the exact source, check, angle or fix.
- Never demand the impossible or invented. If the assistant honestly stated a real limit (no access,
  data doesn't exist, user must decide), accept it.
- If the request is a quick question or chit-chat, hold it to that standard, not a research standard.

Reply with exactly one line of JSON and nothing else:
{{"pass": true}}  or  {{"pass": false, "items": ["...", "..."]}}"""

JUDGES = {
    "Completeness": (MODEL, """YOUR ANGLE: completeness.
Break the request into every distinct ask, explicit and clearly implied. Fail if any ask is skipped,
partly done, deferred without a real blocker, cut off, or left with placeholders."""),

    "Evidence": (MODEL, """YOUR ANGLE: evidence and accuracy.
Fail if any claim, number, name, address, link or "done/verified/passing" statement is unsupported by
the tool results, contradicts them, or looks fabricated; or if sources were not cross-checked where
being wrong would hurt the user."""),

    "Coverage": (DEEP_MODEL, """YOUR ANGLE: coverage of sources and methods. Leave no stone unturned.
First, silently think like the world's leading expert on this exact request: list every authoritative
source, database, registry, directory, API, dataset, publication, filing, community and search method
such an expert would use, including non-obvious ones the user would never think of. Then compare against
the searches and sources actually used in the tool calls. Fail with the specific important sources or
methods that were missed (by name) and what each would add."""),

    "Blind spots": (DEEP_MODEL, """YOUR ANGLE: blind spots for the user's real goal.
Infer what the user is ultimately trying to achieve. Fail with what they would obviously need but did
not think to ask: missing categories, edge cases, ranking criteria, caveats that change the decision,
risks, freshness of data, and the concrete next step. Only items that matter for their goal."""),

    "Depth": (MODEL, """YOUR ANGLE: depth and usefulness.
Would a demanding expert client call this exceptional? Fail if it is generic where it should be
specific, summarises where it should give the actual data, lacks the reasoning behind rankings or
recommendations, or is hard to act on. Name exactly what to deepen."""),
}

TRIAGE = """Classify this request. Reply with exactly one word.
quick = a greeting, a yes/no or one-line factual question, a small edit, or a clarification.
full = anything involving research, lists, recommendations, analysis, writing, code, data, or multiple parts.
When in doubt, answer full.

<user_request>
{request}
</user_request>"""


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "text":
            parts.append(block.get("text", ""))
        elif t == "tool_use":
            parts.append("[tool call: %s %s]" % (block.get("name"), json.dumps(block.get("input"))[:3000]))
        elif t == "tool_result":
            res = block.get("content")
            if isinstance(res, list):
                res = " ".join(b.get("text", "") for b in res if isinstance(b, dict))
            parts.append("[tool result: %s]" % str(res or "")[:1500])
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


def ask(model, prompt, timeout=240):
    env = dict(os.environ, CLAUDE_COMPLETENESS_JUDGE="1")
    try:
        return subprocess.run(
            ["claude", "-p", "--model", model, "--tools", ""],
            input=prompt, capture_output=True, text=True, timeout=timeout, cwd="/tmp", env=env,
        ).stdout.strip()
    except Exception:
        return ""


def parse(out):
    s, e = out.find("{"), out.rfind("}")
    if s < 0 or e < 0:
        return None
    try:
        return json.loads(out[s:e + 1])
    except ValueError:
        return None


def main():
    if os.environ.get("CLAUDE_PANEL", "").lower() == "off":
        return
    if os.environ.get("CLAUDE_COMPLETENESS_JUDGE") == "1":
        return  # we are a judge's own nested session

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

    idx = next((i for i in range(len(entries) - 1, -1, -1) if is_real_user_prompt(entries[i])), None)
    if idx is None:
        return

    state_file = os.path.join("/tmp", "claude-panel-%s.json" % data.get("session_id", "x"))
    try:
        with open(state_file) as f:
            state = json.load(f)
    except Exception:
        state = {}
    key = str(idx)
    if state.get(key, 0) >= RETRIES:
        return
    # Run once per round even if the panel is installed twice (system-wide and in a repo).
    lock = os.path.join("/tmp", "claude-panel-lock-%s-%s-%d" % (data.get("session_id", "x"), key, state.get(key, 0)))
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return

    request = text_of(entries[idx]["message"]["content"])
    answer = "\n".join(
        p for p in (
            text_of((e.get("message") or {}).get("content"))
            for e in entries[idx + 1:]
            if e.get("type") in ("assistant", "user") and not e.get("isSidechain")
        ) if p
    ).strip()
    if not answer:
        return
    request, answer = request[-MAX_CHARS:], answer[-MAX_CHARS:]
    # Earlier conversation (reference only), so judges know what was already established.
    context = "\n".join(
        p for p in (
            text_of((e.get("message") or {}).get("content"))
            for e in entries[max(0, idx - 60):idx]
            if e.get("type") in ("assistant", "user") and not e.get("isSidechain")
        ) if p
    )[-CONTEXT_CHARS:] or "(none)"

    tier = ask(FAST_MODEL, TRIAGE.format(request=request), timeout=45).lower()
    judges = {"Completeness": JUDGES["Completeness"]} if tier.startswith("quick") else JUDGES

    findings = {}
    with cf.ThreadPoolExecutor(max_workers=len(judges)) as pool:
        futs = {
            pool.submit(ask, model, COMMON.format(context=context, request=request, answer=answer) + "\n\n" + brief): name
            for name, (model, brief) in judges.items()
        }
        for fut in cf.as_completed(futs):
            verdict = parse(fut.result())
            if verdict and verdict.get("pass") is False and verdict.get("items"):
                findings[futs[fut]] = [str(i) for i in verdict["items"]]

    if not findings:
        return

    state[key] = state.get(key, 0) + 1
    try:
        with open(state_file, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

    lines = ["Review panel (%d independent judges, round %d of %d) says this is not yet the best possible answer. Fix all of the following, using parallel subagents for independent items:"
             % (len(judges), state[key], RETRIES)]
    for name in JUDGES:
        for item in findings.get(name, []):
            lines.append("- [%s] %s" % (name, item))
    lines.append("If an item truly can't be done, say so plainly with the reason instead of skipping it.")
    print(json.dumps({"decision": "block", "reason": "\n".join(lines)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open

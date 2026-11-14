# driverspositano

Index for this workspace. Open the files below only when the task needs them.

## Files
- `deliverables/` — finished client documents (PDFs). Read the relevant one before any work on that campaign.
- `.claude/agents/response-reviewer.md` — independent reviewer; use it on big multi-part deliverables before handing them over.
- `.claude/hooks/completeness_check.py` — the automatic completeness judge (see below).

## How work is done here
- Every request is treated as a brief: task, guardrails, definition of done. If the user gives no definition of done, write one line stating it at the start and check the result against it at the end.
- Turn the definition of done into a pass/fail check you can actually run (a script, a diff, a field-by-field comparison against the source) and show its output as evidence.
- Long research or connector-heavy steps go in a subagent so the main chat stays clean. Use as many agents as the task needs, and no more.

## Boundaries
- Never send emails, messages or posts on the user's behalf without them saying so in that request.
- Never push to `master`; work on a branch and open a draft PR.

## Automatic check
After each turn a separate Claude compares the response (including tool results) with the latest request and sends the session back to finish anything missing, up to 3 times per request. Disable for a session with `CLAUDE_COMPLETENESS_CHECK=off`; change the judge with `CLAUDE_COMPLETENESS_MODEL` (default `sonnet`) and the retry cap with `CLAUDE_COMPLETENESS_RETRIES`.

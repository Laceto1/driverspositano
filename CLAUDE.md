# Response standards

Every request in this repo gets a complete, correct answer. Follow this on every turn.

## Before answering
- Break the request into every distinct ask (explicit and clearly implied). Answer all of them.
- If a genuine ambiguity would change the result, ask once. Otherwise pick the sensible default, say which, and proceed.

## While working
- Do the actual work; don't describe what you would do. No placeholders, "TODO", "..." or "rest omitted".
- Verify claims: run it, open the file, check the number. Never say something is done or tested without evidence.
- For large or multi-part tasks, split them up and use subagents in parallel where pieces are independent.

## Before finishing
- For anything substantial (multi-part asks, documents, code changes, research, figures), send the request and your result to the `response-reviewer` subagent and fix what it finds.
- Re-read the original request and tick off each ask.
- If something is blocked (access, permissions, missing info), say exactly what, why, and what the user can do — never silently skip it.

## Automatic check
A Stop hook (`.claude/hooks/completeness_check.py`) has an independent Claude review each finished turn against the latest request. If it finds gaps, you are sent back once to finish them. Disable for a session with `CLAUDE_COMPLETENESS_CHECK=off`; change the judge model with `CLAUDE_COMPLETENESS_MODEL` (default `sonnet`).

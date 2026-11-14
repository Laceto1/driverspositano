# driverspositano

Index for this workspace. Open the files below only when the task needs them.

## Files
- `deliverables/` — finished client documents (PDFs). Read the relevant one before any work on that campaign.
- `.claude/hooks/quality_panel.py` — the review panel that judges every answer (see below).
- `.claude/agents/response-reviewer.md` — independent reviewer; use it on big multi-part deliverables before handing them over.
- `.claude/skills/digest-media/` — turns a video/post URL into title, description and full transcript.

## How work is done here
- Every request is treated as a brief: task, guardrails, definition of done. If the user gives no definition of done, write one line stating it at the start and check the result against it at the end.
- Research, lists and "find the best X" requests: before searching, map the full universe of sources a top expert would use (official registries, government and industry databases, directories, APIs, papers, filings, trial registries, communities), including non-obvious ones. Cover them with parallel subagents, open and cite the actual sources, cross-check, and give the ranking criteria.
- Work as a swarm by default: any task with two or more independent parts (pages, sources, files, sections, checks) is split across parallel subagents, then merged and cross-checked. Only one-step tasks and quick questions stay single-agent.
- Substantial research, list-building and analysis tasks run as a large workflow (the user starts these with the word `ultracode`): 50+ agents is the norm, one per source, region, segment or sub-question, plus independent verifier agents that re-check each result against its source before merging. There is no agent cap in this repo.
- Gotcha (happened once): in workflows, never `.slice()` the merged material to fit one writer agent — it silently dropped 19 of 28 research tracks. Merge, dedupe and attach verdicts in plain code, then split writing across several agents and assemble the report in code. Fact-checkers need the primary-source hosts allowed on the network, and have a shared search budget, so they should open pages with WebFetch and use only a few searches each.
- Turn the definition of done into a pass/fail check you can actually run (a script, a diff, a field-by-field comparison against the source) and show its output as evidence.
- Video or post links (YouTube, X, TikTok, Instagram): use the `digest-media` skill to get the transcript before answering. Don't try to play them in the browser.

## Boundaries
- Never send emails, messages or posts on the user's behalf without them saying so in that request.
- Never push to `master`; work on a branch and open a draft PR (enforced by a hook).

## Review panel (automatic)
After each turn, a fast triage decides quick vs substantial. Quick turns get one completeness judge. Substantial turns get five blind, independent judges in parallel: Completeness, Evidence, Coverage (sources an expert would use), Blind spots (what the user didn't think to ask) and Depth. Any must-fix item sends the session back, up to 3 rounds per request.
Env knobs: `CLAUDE_PANEL=off`, `CLAUDE_PANEL_RETRIES`, `CLAUDE_PANEL_MODEL` (default sonnet), `CLAUDE_PANEL_DEEP_MODEL` (default opus, used by Coverage and Blind spots), `CLAUDE_PANEL_FAST_MODEL` (default haiku, triage).

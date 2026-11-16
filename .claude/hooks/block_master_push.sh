#!/usr/bin/env bash
# PreToolUse hook: hard-block `git push` to master/main. Exit 2 = blocked, reason goes back to Claude.
# Only the `git push ...` segment of the command is inspected (up to ; & | or newline),
# so commit messages that merely mention master/main don't trigger it.
cmd=$(jq -r '.tool_input.command // empty')
pushes=$(printf '%s\n' "$cmd" | grep -Eo 'git[[:space:]]+push[^;&|]*' || true)
if [ -n "$pushes" ] && printf '%s\n' "$pushes" | grep -Eq '([[:space:]:/+])(master|main)([[:space:]]|$)'; then
  echo "Blocked by repo rule: never push to master/main. Push to a feature branch and open a draft PR." >&2
  exit 2
fi
exit 0

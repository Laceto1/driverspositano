---
name: digest-media
description: Watch/digest a YouTube, X (Twitter), TikTok, Instagram or Facebook video, or a public video file URL, by pulling its title, description and full transcript. Use whenever the user shares a video or post link and wants it understood, summarised, or turned into a task.
---

# Digest a video link

1. Run, writing to the scratchpad (not the repo):
   `python3 -I "$CLAUDE_PROJECT_DIR/.claude/skills/digest-media/digest.py" "<url>" --out <scratchpad>/digest.txt`
   Then read the whole file.
2. Long transcripts (> ~20k chars): hand the file to a subagent to extract the concrete steps, tools and commands, so the main chat stays clean.
3. Exit code 3 with `NO_KEY`: the Supadata key is missing.
   - Cloud session: call `request_credential` for host `api.supadata.ai`, header `x-api-key`, no prefix. Then retry once.
   - Local: ask the user to `export SUPADATA_API_KEY=...` (free key at https://dash.supadata.ai).
4. The transcript only covers what is *said*. If the video is mainly on-screen (code, settings, UI) with little speech, say so and ask for screenshots of the key moments.

## Gotchas
- Don't try to play YouTube/X in the headless browser: both block cloud browsers ("Sign in to confirm you're not a bot" / blank 403). Don't try to get around those blocks.
- YouTube title/description come from the public watch page and work without a key; the transcript needs the key.
- Videos over 20 minutes become an async job; the script polls for up to 10 minutes.

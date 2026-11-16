---
name: trantolo-browser
description: Where Luca's Trantolo work lives and how to reach it - Outlook via Zapier (cloud), and the browser-only tools (Search Console, GA4, Google Ads/LSA, Lead Docket, FileVine) via Claude in Chrome on his Mac. Use for any Trantolo email, reporting-number or lead/case lookup task.
---

# Trantolo: which tool lives where

## Reachable from a cloud session (Zapier)
- **Outlook, LucaA@trantololaw.com**: Zapier "Microsoft Outlook". Read with `microsoft_outlook_make_api_get_request` (Microsoft Graph GET). Write drafts only with `microsoft_outlook_create_draft_reply` / `microsoft_outlook_create_draft_email`. Never send.
  - WDWC folder id: `AQMkADBlOWQyOTE1LTJjZjctNDcwOC04NGY5LTc5NGJkYWI3ZTUwOAAuAAADsYND-EhJU0KnchgfDde9jgEAkV9itzGufU2NKuXgtl_-RwACEb3lCAAAAA==`
  - Callrail and Archive folders hold only automated alerts.
- **CallRail**: Zapier CallRail, connection `025cc523-eb39-89d9-9465-b5111e38a093` (fallback `02e2c560-21b5-84cb-bf60-8f0b4ee3eb43`; both verified to reach account "Trantolo & Trantolo, LLC" `ACC29e611fd8db6461aa978aada3a4dbb7b`, company `COMba2abebb7e0647908fd99a99bfab71fb`). Never use the reallywowseo connection for Trantolo.
- **Gmail**: not used for Trantolo (Luca, Nov 15: "I never use my gmail for trantolo").

## Only reachable in Luca's browsers (Mac mini, Claude in Chrome)
- Chrome profile **"Trantolo Law"** (always on screen): Outlook web, Google Search Console, GA4, Google Ads, Local Services Ads.
- Chrome profile **"Luca@reallywow"**: Lead Docket (trantololaw.leaddocket.com), FileVine.
- Switch between them by picking the matching window in `list_connected_browsers` (Claude in Chrome must be connected in both profiles), or open the profile from Chrome's avatar menu.
- A cloud session cannot drive these. Put `[number needed]` in the draft and list the item under "FOR THE MAC" in the "📋 Today" summary; the Mac task fetches it (prompt: `mac-numbers-helper-prompt.md`).

## Rules
- Drafts only; never send, never sign in or enter passwords.
- WDW / We Do Web gets organic numbers only, never PPC cost or budgets.
- Client case, intake, HR and billing threads: flag, don't draft. Never copy medical or case details.

#!/usr/bin/env python3
"""Digest a video/post URL (YouTube, X/Twitter, TikTok, Instagram, Facebook, file URL)
into plain text Claude can read: title/description when available + full transcript.

Usage: python3 -I digest.py <url> [--lang en] [--out FILE]

Transcript comes from Supadata (https://supadata.ai), which fetches existing captions
or transcribes the audio with AI. Auth: SUPADATA_API_KEY env var, or in a Claude Code
cloud session a network secret saved for api.supadata.ai (header x-api-key), which the
proxy injects in place of the placeholder sent here.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.supadata.ai/v1"
UA = "Mozilla/5.0 (compatible; digest-media/1.0)"


def http_get(url, headers=None, timeout=120):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def youtube_metadata(url):
    """Title, channel and full description from the public watch page."""
    try:  # best effort: never let metadata failure stop the transcript
        # SOCS cookie skips the EU cookie-consent redirect (consent.youtube.com).
        status, html = http_get(url, {"User-Agent": UA, "Accept-Language": "en", "Cookie": "SOCS=CAI"}, timeout=30)
    except Exception:
        return None
    if status != 200:
        return None
    out = {}
    m = re.search(r'"videoDetails":\{.*?"title":"((?:[^"\\]|\\.)*)"', html)
    if m:
        out["title"] = json.loads('"%s"' % m.group(1))
    m = re.search(r'"ownerChannelName":"((?:[^"\\]|\\.)*)"', html) or re.search(r'"author":"((?:[^"\\]|\\.)*)"', html)
    if m:
        out["channel"] = json.loads('"%s"' % m.group(1))
    m = re.search(r'"attributedDescription":\{"content":"((?:[^"\\]|\\.)*)"', html) or \
        re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', html)
    if m:
        out["description"] = json.loads('"%s"' % m.group(1))
    return out or None


def supadata_transcript(url, lang):
    key = os.environ.get("SUPADATA_API_KEY") or "proxy-injected-placeholder"
    headers = {"x-api-key": key, "User-Agent": UA}
    q = {"url": url, "text": "true", "mode": "auto"}
    if lang:
        q["lang"] = lang
    status, body = http_get(API + "/transcript?" + urllib.parse.urlencode(q), headers, timeout=150)
    if status in (401, 403):
        return None, ("NO_KEY: Supadata rejected the request (HTTP %d). Add an API key: in a cloud "
                      "session save a network secret for api.supadata.ai (header x-api-key); locally "
                      "export SUPADATA_API_KEY. Free key: https://dash.supadata.ai" % status)
    if status == 206:
        return None, "No transcript available for this video (it may have no speech)."
    if status not in (200, 202):
        return None, "Supadata error HTTP %d: %s" % (status, body[:300])
    data = json.loads(body)
    job = data.get("jobId")
    deadline = time.time() + 600
    while job and time.time() < deadline:  # long videos: poll the async job
        time.sleep(5)
        s, b = http_get(API + "/transcript/" + job, headers, timeout=60)
        if s != 200:
            return None, "Supadata job error HTTP %d: %s" % (s, b[:300])
        data = json.loads(b)
        if data.get("status") == "completed":
            break
        if data.get("status") == "failed":
            return None, "Transcription failed: %s" % data.get("error")
    else:
        if job:
            return None, "Transcription job %s still running after 10 minutes." % job
    content = data.get("content")
    if isinstance(content, list):
        content = " ".join(c.get("text", "") for c in content)
    return {"lang": data.get("lang"), "text": content or ""}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out")
    a = ap.parse_args()

    lines = ["SOURCE: " + a.url]
    if re.search(r"(youtube\.com|youtu\.be)/", a.url):
        meta = youtube_metadata(a.url)
        if meta:
            for k in ("title", "channel"):
                if meta.get(k):
                    lines.append("%s: %s" % (k.upper(), meta[k]))
            if meta.get("description"):
                lines += ["", "DESCRIPTION:", meta["description"]]

    tr, err = supadata_transcript(a.url, a.lang)
    lines.append("")
    if tr:
        lines += ["TRANSCRIPT (%s, %d chars):" % (tr["lang"], len(tr["text"])), tr["text"]]
    else:
        lines.append("TRANSCRIPT UNAVAILABLE: " + err)

    text = "\n".join(lines)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("Wrote %d chars to %s" % (len(text), a.out))
        print(text[:1500])
    else:
        print(text)
    sys.exit(0 if tr else 3)


if __name__ == "__main__":
    main()

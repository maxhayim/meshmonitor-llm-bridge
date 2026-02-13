#!/usr/bin/env python3
# mm_meta:
#   name: LLM Bridge
#   emoji: 📡🧠
#   language: Python
#   description: Interact with your chosen LLM over Meshtastic.
__version__ = "1.0.0"

"""
mm_llm_bridge.py

MeshMonitor Script: LLM Bridge
- Parses incoming messages for a trigger (e.g. "!ask", "@claw", "@ai")
- Sends prompt to a configured LLM provider (OpenClaw / Ollama / OpenAI-compatible)
- Returns responses split to fit MeshMonitor + Meshtastic-safe limits

Output contract:
- Print JSON to stdout with "response" (string) or "responses" (list of strings)

Notes:
- Keep each returned message chunk <= MAX_MSG_CHARS and <= MAX_MSG_BYTES (defaults 200/200).
- Prefer running via MeshMonitor Auto Responder regex so the script only triggers when intended.
"""

import json
import os
import re
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# CONFIG (edit these)
# ----------------------------

# Triggers: first token must match exactly.
AGENT_TRIGGERS = ["!ask", "@claw", "@ai"]
HELP_TRIGGERS = ["!ask help", "@claw help", "@ai help"]

# Provider selection: "openai_compat" or "ollama"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai_compat").strip().lower()

# Endpoint:
# - openai_compat: can be full "/v1/chat/completions" or base URL (we append)
# - ollama: can be full "/api/generate" or base URL (we append)
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8000").strip()

# Model name (provider dependent)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

# API key (optional; many local providers don't require)
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()

# Keep responses short for radio text
SYSTEM_PROMPT = os.getenv(
    "LLM_SYSTEM_PROMPT",
    "You are a helpful assistant. Keep answers concise and suitable for short radio text messages.",
).strip()

# Runtime controls
REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT", "8.0"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "2"))
HTTP_RETRY_SLEEP_SECONDS = float(os.getenv("HTTP_RETRY_SLEEP_SECONDS", "0.5"))

# Limits: keep each returned chunk under typical MeshMonitor/Meshtastic constraints
MAX_MSG_CHARS = int(os.getenv("MAX_MSG_CHARS", "200"))
MAX_MSG_BYTES = int(os.getenv("MAX_MSG_BYTES", "200"))

# Avoid mesh spam
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "4"))

SPLIT_LONG_RESPONSES = os.getenv("SPLIT_LONG_RESPONSES", "1").strip().lower() not in ("0", "false")
TRUNCATE_WITH_ELLIPSIS = os.getenv("TRUNCATE_WITH_ELLIPSIS", "1").strip().lower() not in ("0", "false")

# ----------------------------
# Utilities
# ----------------------------


def out_single(msg: str) -> None:
    sys.stdout.write(json.dumps({"response": msg}, ensure_ascii=False))
    sys.stdout.flush()


def out_multi(msgs: List[str]) -> None:
    sys.stdout.write(json.dumps({"responses": msgs}, ensure_ascii=False))
    sys.stdout.flush()


def clamp_utf8(text: str, max_chars: int, max_bytes: int) -> str:
    """Clamp text to both max chars and UTF-8 bytes."""
    if len(text) > max_chars:
        text = text[:max_chars]
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    while text and len(text.encode("utf-8")) > max_bytes:
        text = text[:-1]
    return text


def split_meshtastic(text: str, max_chars: int, max_bytes: int) -> List[str]:
    """
    Split into chunks that each satisfy both char and UTF-8 byte limits.
    Prefer splitting on whitespace; otherwise hard-split.
    """
    text = (text or "").strip()
    if not text:
        return [""]

    if len(text) <= max_chars and len(text.encode("utf-8")) <= max_bytes:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        candidate = clamp_utf8(remaining[:max_chars], max_chars, max_bytes)
        if not candidate:
            break

        # Prefer whitespace split near the end
        cut = len(candidate)
        ws = candidate.rfind(" ")
        if ws >= max(10, int(0.4 * len(candidate))):
            cut = ws

        part = candidate[:cut].rstrip()
        if not part:
            part = candidate

        part = clamp_utf8(part, max_chars, max_bytes)
        chunks.append(part)

        remaining = remaining[len(part) :].lstrip()

        if len(chunks) >= MAX_CHUNKS and remaining:
            if TRUNCATE_WITH_ELLIPSIS:
                ell = "…"
                last = chunks[-1].rstrip()
                last = clamp_utf8(
                    last,
                    max_chars - len(ell),
                    max_bytes - len(ell.encode("utf-8")),
                )
                chunks[-1] = (last + ell) if last else ell
            break

    return chunks if chunks else [""]


def read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        # If MeshMonitor ever passes plain text, wrap it.
        return {"message": raw}


def extract_message(payload: Dict[str, Any]) -> str:
    """Defensive extraction of incoming text from common MeshMonitor payload keys."""
    for k in ("message", "text", "msg", "body", "content"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    def dig(obj: Any, path: List[str]) -> Optional[str]:
        cur = obj
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur.strip() if isinstance(cur, str) else None

    candidates = [
        ["packet", "decoded", "payload", "text"],
        ["packet", "decoded", "payload", "message"],
        ["packet", "decoded", "text"],
        ["decoded", "payload", "text"],
        ["decoded", "text"],
        ["payload", "text"],
    ]
    for path in candidates:
        s = dig(payload, path)
        if s:
            return s

    return ""


def parse_prompt(msg: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (trigger, prompt) if matched; otherwise (None, None).
    Also supports help triggers (returns ("help", "")).
    """
    m = (msg or "").strip()
    if not m:
        return (None, None)

    lower = m.lower()
    for ht in HELP_TRIGGERS:
        if lower == ht.lower():
            return ("help", "")

    for trig in AGENT_TRIGGERS:
        if m.startswith(trig):
            rest = m[len(trig) :].strip()
            # allow "@claw: hi" or "@claw- hi"
            rest = re.sub(r"^[:\-]\s*", "", rest)
            return (trig, rest)

    return (None, None)


def http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"_raw": body}


def call_openai_compat(prompt: str) -> str:
    base = LLM_ENDPOINT.rstrip("/")
    url = base if base.endswith("/v1/chat/completions") else (base + "/v1/chat/completions")

    headers: Dict[str, str] = {}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 220,  # kept modest to reduce latency + keep answers short
    }

    last_err: Optional[str] = None
    for i in range(HTTP_RETRIES + 1):
        try:
            r = http_post_json(url, payload, headers, REQUEST_TIMEOUT_SECONDS)
            choices = r.get("choices", [])
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
            if isinstance(r.get("text"), str) and r["text"].strip():
                return r["text"].strip()
            if isinstance(r.get("_raw"), str) and r["_raw"].strip():
                return r["_raw"].strip()
            return "No response content from LLM."
        except Exception as e:
            last_err = str(e)
            if i < HTTP_RETRIES:
                time.sleep(HTTP_RETRY_SLEEP_SECONDS)

    return f"LLM error: {last_err or 'unknown'}"


def call_ollama(prompt: str) -> str:
    base = LLM_ENDPOINT.rstrip("/")
    url = base if base.endswith("/api/generate") else (base + "/api/generate")

    headers: Dict[str, str] = {}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "system": SYSTEM_PROMPT,
        "options": {"temperature": 0.2, "num_predict": 220},
    }

    last_err: Optional[str] = None
    for i in range(HTTP_RETRIES + 1):
        try:
            r = http_post_json(url, payload, headers, REQUEST_TIMEOUT_SECONDS)
            if isinstance(r.get("response"), str) and r["response"].strip():
                return r["response"].strip()
            if isinstance(r.get("_raw"), str) and r["_raw"].strip():
                return r["_raw"].strip()
            return "No response content from LLM."
        except Exception as e:
            last_err = str(e)
            if i < HTTP_RETRIES:
                time.sleep(HTTP_RETRY_SLEEP_SECONDS)

    return f"LLM error: {last_err or 'unknown'}"


def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "ollama":
        return call_ollama(prompt)
    return call_openai_compat(prompt)


def help_text() -> str:
    triggers = ", ".join(AGENT_TRIGGERS)
    return f"Usage: start with {triggers}. Example: !ask What is 5x5?"


def normalize_for_radio(text: str) -> str:
    """Make output more radio-friendly and chunk-friendly."""
    t = (text or "").strip()
    # collapse repeated spaces/tabs
    t = re.sub(r"[ \t]{2,}", " ", t)
    # trim line noise
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def ensure_under_limits(answer: str) -> List[str]:
    """
    Always return chunks that satisfy limits.
    - If SPLIT_LONG_RESPONSES: split into up to MAX_CHUNKS chunks.
    - Else: clamp to a single chunk.
    """
    ans = normalize_for_radio(answer)
    if not ans:
        ans = "No response."

    if SPLIT_LONG_RESPONSES:
        return split_meshtastic(ans, MAX_MSG_CHARS, MAX_MSG_BYTES)

    return [clamp_utf8(ans, MAX_MSG_CHARS, MAX_MSG_BYTES)]


# ----------------------------
# Main
# ----------------------------


def main() -> None:
    payload = read_stdin_json()
    msg_in = extract_message(payload)

    trig, prompt = parse_prompt(msg_in)

    if trig is None:
        # If your Auto Responder regex is correct, this rarely happens.
        chunks = ensure_under_limits("No trigger. Try: !ask help")
        out_single(chunks[0])
        return

    if trig == "help" or (prompt or "").strip().lower() == "help":
        chunks = ensure_under_limits(help_text())
        out_single(chunks[0]) if len(chunks) == 1 else out_multi(chunks)
        return

    if not (prompt or "").strip():
        chunks = ensure_under_limits("Missing prompt. Try: !ask help")
        out_single(chunks[0])
        return

    answer = call_llm(prompt.strip())
    chunks = ensure_under_limits(answer)
    out_single(chunks[0]) if len(chunks) == 1 else out_multi(chunks)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        chunks = ensure_under_limits(f"Error: {e}")
        out_single(chunks[0])

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python Version">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  </a>
</p>

# 📡🧠 LLM Bridge

**LLM Bridge** is a LLM bridgefor [**MeshMonitor**](https://github.com/Yeraze/MeshMonitor) Script that allows users to interact with their chosen Large Language Model (OpenClaw, Ollama, OpenAI, etc.) over [**Meshstatic**](https://meshtastic.org/).

Each user runs their own instance and connects it to the LLM provider of their choice.

This repository contains:

- `mm_llm_bridge.py` — the MeshMonitor script (runtime)
- `docs/` — GitHub Pages documentation (display only)

---

## What this does

meshmonitor-llm-bridge enables:

1) **Mesh → LLM**
   - Users send a command over Meshtastic
   - MeshMonitor passes the message via MQTT
   - The bridge forwards it to the configured LLM
   - The response is sent back over the mesh

2) **Per-user AI agents**
   - Each person runs their own script
   - Each instance connects to its own LLM provider
   - No centralized bot required

Design goals:

- KISS architecture
- Provider-agnostic (OpenClaw today, something else tomorrow)
- Lightweight responses suitable for LoRa
- Personal deployment model (no shared cloud dependency required)

---

## Repository layout

    .
    ├── mm_llm_bridge.py       # Runtime script used by MeshMonitor
    ├── providers/             # LLM provider adapters (optional)
    │   ├── openclaw.py
    │   ├── ollama.py
    │   └── openai.py
    ├── docs/                  # GitHub Pages documentation
    │   ├── index.html
    │   ├── index.js
    │   └── assets/
    └── README.md

---

## IMPORTANT: Which file do I use?

### Use this file in MeshMonitor

    mm_llm_bridge.py

This is the only file MeshMonitor should execute.

### Do NOT run this file

    docs/index.js

`index.js` only displays documentation.

---

## Installing mm_llm_bridge.py

MeshMonitor script requirements (high level):

- Script must be in `/data/scripts/`
- Must output valid JSON to stdout with `response` or `responses`
- Must complete within the MeshMonitor timeout window
- Must be executable

Copy the script into the MeshMonitor container:

    /data/scripts/mm_llm_bridge.py

Make it executable:

    chmod +x /data/scripts/mm_llm_bridge.py

---

## Recommended install (pin to a release tag)

For stable deployments, install from a release tag (replace `vX.Y.Z` with the latest release tag):

    docker exec -it meshmonitor sh -lc "
    wget -O /data/scripts/mm_llm_bridge.py https://raw.githubusercontent.com/maxhayim/meshmonitor-llm-bridge/vX.Y.Z/mm_llm_bridge.py &&
    chmod +x /data/scripts/mm_llm_bridge.py &&
    python3 -m py_compile /data/scripts/mm_llm_bridge.py &&
    echo OK
    "

Using a pinned tag ensures your container runs the exact released version.

---

## Configuration (inside mm_llm_bridge.py)

Edit these constants near the top of the script:

Required:

- `LLM_PROVIDER` (openclaw / ollama / openai)
- `LLM_ENDPOINT`
- `AGENT_TRIGGER` (example: `!ask` or `@claw`)

Optional:

- `MAX_RESPONSE_CHARS`
- `REPLY_CHANNEL_MODE` (same channel or DM)
- `ALLOWED_NODE_IDS`
- `REQUEST_TIMEOUT_SECONDS`
- `LLM_API_KEY` (if required)

Recommended (mesh noise control):

- `RATE_LIMIT_SECONDS`
- `SPLIT_LONG_RESPONSES`
- `TRUNCATE_STRATEGY`

---

## Example Command Syntax

Basic usage:

    !ask What is 5x5?

Agent name usage:

    @claw Explain RF propagation
    @ai Summarize the last message

Only messages matching the configured trigger are processed.

---

## MeshMonitor Auto Responder configuration

Create an Auto Responder rule.

Recommended settings:

- Response Type: `Script`
- Script Path: `/data/scripts/mm_llm_bridge.py`
- Channel: `Direct Messages` (recommended initially)
- Enable Multiline: ON
- Verify Response: OFF

### Example Trigger

Trigger regex:

    ^!ask\s+(.+)$

Response Type: Script  
Script path:

    /data/scripts/mm_llm_bridge.py

---

## How routing works

High-level flow:

    Meshtastic Node
          ↓
    MeshMonitor (MQTT)
          ↓
    mm_llm_bridge.py
          ↓
    Selected LLM Provider
          ↓
    Response → MeshMonitor → Mesh

The bridge:

- Parses the incoming message
- Extracts the prompt
- Sends it to the configured LLM
- Returns a compact response suitable for LoRa

---

## Per-User Deployment Model

Each user:

- Runs their own meshmonitor-llm-bridge
- Connects it to their preferred LLM
- Controls their own API keys and configuration
- Is responsible for rate limits and usage costs (if cloud-based)

This avoids:

- Central AI bottlenecks
- Shared API key exposure
- Mesh-wide AI spam

---

## Packaging / Dependencies

Minimal dependencies by design.

The bridge can be implemented using:

- Python standard library (HTTP via `urllib`)
- Optional `requests` (if preferred)

No heavy frameworks required.

Compatible with PEP 668 container environments.

---

## Security Considerations

Recommended:

- Restrict `ALLOWED_NODE_IDS`
- Use Direct Messages instead of public channel
- Apply response length limits
- Use rate limiting

Mesh is RF — assume traffic is observable.

Do not expose sensitive data through prompts.

---

## Troubleshooting

### Verify script runs inside container

    docker exec -it meshmonitor sh -lc "python3 -m py_compile /data/scripts/mm_llm_bridge.py"

### Check MQTT flow

Confirm MeshMonitor receives messages before debugging the LLM side.

### LLM connectivity test

Test your LLM endpoint directly from inside the container:

    docker exec -it meshmonitor sh

Then test with curl or wget to your configured endpoint.

---

## Inspiration & references

- MeshMonitor by Yeraze (https://github.com/Yeraze)
- Meshtastic MQTT architecture
- Local-first LLM deployments (OpenClaw, Ollama)

---

## License

MIT License

---

## Acknowledgments

* MeshMonitor built by [Yeraze](https://github.com/Yeraze) 
* Shout out to [SkywarnPlus](https://github.com/Mason10198/SkywarnPlus)

Discover other community-contributed Auto Responder scripts for MeshMonitor [here](https://meshmonitor.org/user-scripts.html).

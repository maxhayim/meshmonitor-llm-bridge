<p align="center">
  <img src="docs/assets/logo.png" alt="LLM Bridge Logo" width="200"/>
</p>


<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python Version">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  </a>
</p>

# 📡🧠 LLM Bridge

**LLM Bridge** is a MeshMonitor script that enables interaction with your chosen Large Language Model (OpenClaw, Ollama, OpenAI-compatible APIs, etc.) over [**Meshtastic**](https://meshtastic.org/).

Each user runs their own instance and connects it to the LLM provider of their choice.

This repository contains:

- `mm_llm_bridge.py` — the MeshMonitor runtime script
- `docs/` — GitHub Pages documentation (display only)

---

## What this does

LLM Bridge enables:

1) **Mesh → LLM**
   - Users send a command over Meshtastic
   - MeshMonitor executes the script
   - The bridge forwards the prompt to the configured LLM
   - The response is returned back over the mesh

2) **User-controlled AI agents**
   - Each person runs their own script
   - Each instance connects to its own LLM provider
   - No centralized AI service required

Design goals:

- KISS architecture
- Provider-agnostic (OpenClaw today, something else tomorrow)
- Lightweight responses suitable for LoRa
- Safe message sizing for Meshtastic limits

---

## Repository layout

    .
    ├── mm_llm_bridge.py       # Runtime script used by MeshMonitor
    ├── docs/                  # GitHub Pages documentation
    │   ├── index.html
    │   ├── index.js
    │   └── assets/
    ├── LICENSE
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

- `LLM_PROVIDER` (openai_compat / ollama)
- `LLM_ENDPOINT`
- `LLM_MODEL`

Optional:

- `LLM_API_KEY`
- `MAX_MSG_CHARS`
- `MAX_MSG_BYTES`
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_CHUNKS`

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
    MeshMonitor
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
- Returns responses split safely within Meshtastic limits

---

## Packaging / Dependencies

Minimal dependencies by design.

The bridge uses:

- Python standard library (HTTP via `urllib`)
- No external packages required

Compatible with containerized Python environments.

---

## Security Considerations

Recommended:

- Use Direct Messages instead of public channels
- Apply response length limits (already enforced)
- Avoid sending sensitive prompts over RF networks

Meshtastic traffic may be observable. Operate accordingly.

---

## Troubleshooting

### Verify script runs inside container

    docker exec -it meshmonitor sh -lc "python3 -m py_compile /data/scripts/mm_llm_bridge.py"

### LLM connectivity test

Enter the container and test connectivity to your configured endpoint:

    docker exec -it meshmonitor sh

---

## License

This project is licensed under the MIT License.

See the [LICENSE](LICENSE) file for details.  
Full license text: https://opensource.org/licenses/MIT

---

## Contributing

Pull requests are welcome. Open an issue first to discuss ideas or report bugs.</p>

---

## Acknowledgments

* MeshMonitor built by [Yeraze](https://github.com/Yeraze)

Discover other community-contributed scripts for MeshMonitor: https://meshmonitor.org/user-scripts.html

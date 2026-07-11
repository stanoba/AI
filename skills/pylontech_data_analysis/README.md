# Pylontech Battery Analysis Skill Configuration & Setup

This document provides setup instructions for configuring the Grafana MCP server and the local Pylontech MCP server. These tools allow AI agents (such as OpenAI Codex and Google Antigravity) to query Prometheus metrics and execute live battery stack console diagnostics directly.

> [!IMPORTANT]
> **AI Agent Directive:** If the `pylontech` MCP server is registered and available in your active context window, you **MUST prioritize using it** to fetch live metrics (like `get_pwr_status` or `get_module_diagnostics`) over reading raw console logs from files or executing indirect Grafana/Prometheus database queries.

## 1. Installing the Grafana MCP Server

Install the Grafana MCP server package globally or execute it directly using `uvx` or `npx`.
Reference: [mcp-grafana Github Repository](https://github.com/grafana/mcp-grafana)

```bash
# Using uv (Python packaging tool)
uvx mcp-grafana --disable-write
```

---

## 2. Configuration Files (Secrets Redacted)

### Configuration for OpenAI Codex
File path: `C:\Users\<user>\.codex\config.toml`

```toml
[mcp_servers.grafana]
command = "uvx"
args = ["mcp-grafana", "--disable-write"]
env = { GRAFANA_URL = "http://localhost:3000", GRAFANA_SERVICE_ACCOUNT_TOKEN = "<YOUR_GRAFANA_SERVICE_ACCOUNT_TOKEN_HERE>" }

# Useful settings for first startup when uvx needs to fetch the package
startup_timeout_sec = 30
tool_timeout_sec = 120
```

### Configuration for Google Antigravity
File path: `C:\Users\<user>\.gemini\config\mcp_config.json`

```json
{
  "mcpServers": {
    "grafana": {
      "command": "C:\\Users\\<user>\\AppData\\Roaming\\Python\\Python313\\Scripts\\uvx.exe",
      "args": [
        "mcp-grafana",
        "--disable-write"
      ],
      "env": {
        "GRAFANA_URL": "http://localhost:3000",
        "GRAFANA_SERVICE_ACCOUNT_TOKEN": "<YOUR_GRAFANA_SERVICE_ACCOUNT_TOKEN_HERE>"
      },
      "startup_timeout_sec": 30,
      "tool_timeout_sec": 120
    }
  }
}
```

---

## 3. Registering the Skill in Antigravity

By default, any skill placed under a standard customization root is auto-discovered.
If you need to register it manually or override discovery, update `skills.json` under your customization root:

```json
{
  "entries": [
    { "path": "skills/pylontech_analysis" }
  ]
}
```

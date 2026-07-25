# UniFi Network Monitoring MCP Server

This is a Model Context Protocol (MCP) server written in Python using the `fastmcp` library. It exposes tools to monitor UniFi networks (self-hosted controllers or UniFi OS consoles) for AI assistants and agentic platforms like Google Antigravity, Cursor, and Codex.

## Features

Provides structured network operational data via 6 MCP tools:
1. **`unifi_get_health`** — Site health summary (WAN, LAN, WLAN status, adopted device counts, etc.)
2. **`unifi_get_devices`** — List all adopted access points, switches, and gateways with status and client counts
3. **`unifi_get_clients`** — Show details for all active client stations (wired/wireless IP, MAC, signal, rate)
4. **`unifi_get_top_apps`** — Top bandwidth consumers categorised by application (DPI statistics)
5. **`unifi_get_alerts`** — Fetch recent network alarms and connection alerts
6. **`unifi_get_dashboard`** — Generate a quick network dashboard overview (health, client count, device status)

## Installation Prerequisites

Install the necessary dependencies in your Python environment:
```bash
pip install mcp requests python-dotenv
```

## Setup Configuration

Create a `.env` file in this directory to configure your credentials:

```env
UNIFI_URL=https://192.168.5.11:8443
UNIFI_USERNAME=mcp
UNIFI_PASSWORD=McPsErVeR
UNIFI_SITE=default
```

*Note: Classic controllers (running on port `8443`) are automatically detected and supported via different API routes. Local self-signed SSL certificate validation warnings are suppressed.*

## Linking globally in Antigravity

Add the server to your global config file at `C:\Users\stano\.gemini\config\mcp_config.json`:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "python",
      "args": [
        "D:/Documents/GitHub/AI/mcp-servers/unifi/unifi_mcp.py"
      ]
    }
  }
}
```

*Note: The script loads credentials directly from the local `.env` located inside its execution folder, making it clean and portable.*

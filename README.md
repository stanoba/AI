# AI Repository

Welcome to my AI repository. This is a central storage location where I save all of my **AI knowledge, custom skills, and MCP (Model Context Protocol) server configurations and documentation**.

## Repository Structure

- **`skills/`**: Custom instruction packages (skills) that extend AI agents' capabilities.
  - **`pylontech_data_analysis/`**: Health and thermal correlation rules for Pylontech LiFePO4 batteries.
  - **`tme-search/`**: Electronic component search, live stock & volume pricing checker, PDF datasheet downloader, and project BOM favorites list manager for TME.eu.
- **`mcp-servers/`**: Model Context Protocol (MCP) server implementations.
  - **`pylontech-mcp/`**: Python-based FastMCP console server for direct battery stack query logging.

## Global Integration

To automatically register all skills in this repository across all local AI projects in Google Antigravity, add this repository path to your global `skills.json` (`%USERPROFILE%\.gemini\config\skills.json` or `~/.gemini/config/skills.json`):

```json
{
  "entries": [
    { "path": "D:\\Documents\\GitHub\\AI\\skills" }
  ]
}
```

## Purpose

This repository serves as a version-controlled workspace for local AI configuration setups, component lookup tools, telemetry schemas, and automation scripts.

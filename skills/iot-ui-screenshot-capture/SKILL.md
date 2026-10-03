---
name: iot-ui-screenshot-capture
description: Automated high-resolution UI screenshot capture, data anonymization (masking IPs, MACs, SSIDs, serial numbers, barcodes, API tokens), synthetic time-series telemetry injection, and intelligent cropping for IoT/embedded web interfaces (ESP32, ESP8266, Raspberry Pi, Home Assistant) using Headless Chrome and Python.
---

# IoT UI Screenshot Capture & Anonymization Skill

This skill automates the process of capturing high-resolution, full-length screenshots from live or local IoT web dashboards (ESP32, ESP8266, Raspberry Pi, Home Assistant dashboards), while safely masking sensitive network identifiers, rendering realistic historical graph curves, and trimming unused whitespace.

Use this skill when:
- The user requests updating, regenerating, or adding screenshots for documentation (`README.md`, `docs/*.md`, `assets/`).
- Capturing both Light Theme and Dark Theme variations of web dashboards.
- Anonymizing private local network details (IP addresses, Wi-Fi SSIDs, hardware MAC addresses, battery serial numbers, API Bearer tokens).
- Ensuring telemetry charts (e.g. 24-hour Canvas / Chart.js graphs) render complete, realistic data curves instead of empty placeholders.
- Cropping excess whitespace from the bottom of captured pages while preserving footers and status bars.

---

## Quick Usage

Run the capture engine using Python:

```bash
# Capture screenshots using the Pylontech Smart Monitor & Emulator preset:
python D:/Documents/GitHub/AI/skills/iot-ui-screenshot-capture/scripts/capture_engine.py -c D:/Documents/GitHub/AI/skills/iot-ui-screenshot-capture/resources/pylon_preset.json -o assets --artifacts-dir "<artifacts_dir>"

# Capture screenshots for a generic IoT device:
python D:/Documents/GitHub/AI/skills/iot-ui-screenshot-capture/scripts/capture_engine.py -c D:/Documents/GitHub/AI/skills/iot-ui-screenshot-capture/resources/generic_iot_preset.json -o docs/assets
```

---

## Core Capabilities & Architecture

```
┌─────────────────────────┐          ┌───────────────────────────┐          ┌─────────────────────────┐
│     Headless Chrome     │  HTTP    │    Local Reverse Proxy    │  HTTP    │     Target IoT Device   │
│  (--virtual-time=2000)  ├─────────►│  (ThreadingHTTPServer)   ├─────────►│  (ESP32 / 192.168.x.x)  │
└─────────────────────────┘          └─────────────┬─────────────┘          └─────────────────────────┘
                                                   │
                                      ┌────────────┴────────────┐
                                      │  1. Anonymize Strings   │
                                      │  2. Inject Theme (.dark)│
                                      │  3. Mock /api/history   │
                                      │  4. Route Subresources  │
                                      └─────────────────────────┘
```

1. **Local Anonymizing Reverse Proxy (`ThreadingHTTPServer`):**
   - Intercepts all HTTP traffic between Headless Chrome and the target IoT device.
   - Replaces private IPs (`192.168.x.x` $\rightarrow$ `192.168.1.15x`), private SSIDs (`MyHomeWiFi` $\rightarrow$ `Home-WiFi`), serial numbers, and tokens on the fly without modifying microcontroller firmware.
   - Routes multi-device environments (e.g. Smart Monitor on Primary IP vs BMS Emulator on Secondary IP) via `?dev=...` parameters.

2. **Synthetic Telemetry History Generator:**
   - Intercepts `/api/history` and dynamically serves realistic 24-hour time-series datasets (solar daytime charging + evening home discharge).
   - Guarantees charts are populated with smooth gradient-filled curves, dual-axis labels, and timestamps.

3. **Theme Injection:**
   - Toggles Light and Dark modes (`?theme=dark` or `?theme=light`) by dynamically manipulating the `<html>` class list and local storage flags.

4. **Headless Chrome Automation:**
   - Launches Chrome/Edge in modern headless mode (`--headless=new`, `--hide-scrollbars`, `--force-device-scale-factor=1`).
   - Uses `--virtual-time-budget=2000` to ensure AJAX calls (`fetch()`) and canvas rendering routines complete before taking the screenshot.

5. **Smart PIL Bottom Cropping:**
   - Detects the background color at the bottom of the viewport.
   - Automatically crops empty bottom padding (preserving a clean 30px margin) without truncating diagnostics cards, peer discovery tables, or footer copyright notices.

---

## Preset JSON Schema

Preset configuration files (e.g. [`resources/pylon_preset.json`](resources/pylon_preset.json)) define device IPs, replacement mappings, and target capture pages:

```json
{
  "name": "Device Preset Name",
  "primary_ip": "192.168.1.50",
  "secondary_ip": "192.168.1.60",
  "proxy_port": 8765,
  "output_dir": "assets",
  "virtual_time_budget_ms": 2000,
  "anonymize": true,
  "mock_chart": true,
  "replacements": [
    ["192.168.10.100", "192.168.1.150"],
    ["MyPrivateSSID", "Home-WiFi"],
    ["SECRET_TOKEN_123", "psm_00000000"]
  ],
  "captures": [
    {
      "filename": "ui-dashboard.png",
      "path": "/?dev=smart&theme=light",
      "width": 1280,
      "height": 2400
    },
    {
      "filename": "ui-dashboard-dark.png",
      "path": "/?dev=smart&theme=dark",
      "width": 1280,
      "height": 2400
    }
  ]
}
```

---

## CLI Options

| Option | Flag | Default | Description |
|:---|:---|:---|:---|
| `--config` | `-c` | `None` | Path to JSON preset configuration file |
| `--primary-ip` | | `192.168.1.150` | Primary IoT device IP address |
| `--secondary-ip` | | `192.168.1.153` | Secondary / Emulator device IP address |
| `--port` | `-p` | `8765` | Local reverse proxy port |
| `--output-dir` | `-o` | `assets` | Directory where output `.png` screenshots are saved |
| `--artifacts-dir` | `-a` | `None` | Antigravity conversation artifacts directory for inline chat viewing |
| `--virtual-time` | | `2000` | Browser virtual time budget in milliseconds for rendering AJAX/canvas |

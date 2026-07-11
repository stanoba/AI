# Pylontech Battery Console MCP Server

A Model Context Protocol (MCP) server written in Python that allows AI agents to directly communicate with a Pylontech battery stack (e.g. US3000C) over:
- A local serial cable (RS232/RS485 console cable connected to a PC COM/USB port).
- A network-attached serial terminal server (e.g. using raw TCP/Telnet on port 23, replacing manual `nc` commands).

---

## 1. Why Python?

**Python** is the ideal programming language for this cross-platform MCP server for several reasons:

1. **Native MCP Support:** Anthropic provides an official Python SDK (`mcp`), making implementation robust, secure, and compliant with protocol specifications out-of-the-box.
2. **True Cross-Platform Serial Support:** The `pyserial` module is a mature, standard package that runs seamlessly on **Windows, Linux, and macOS** without requiring native C++ compilation tools during installation (unlike Node.js serialport modules, which can fail to build on Windows without local C++ toolchains).
3. **Simple Networking:** Python's standard `socket` library provides simple, cross-platform TCP connectivity to replace Unix-specific `nc` or `telnet` network shells.

---

## 2. Installation & Quick Start

### Prerequisites
Make sure Python 3.9+ is installed on your system.

```bash
# Install the MCP server dependencies
pip install mcp pyserial
```

### Running the Server

Start the server using standard input/output (stdio) communication channel:

```bash
python pylontech_mcp.py
```

---

## 3. Configuration

Configure the connection settings via **environment variables** before launching:

| Environment Variable | Default Value | Description |
|:---|:---|:---|
| `PYLONTECH_CONN_TYPE` | `network` | Connection medium: `network` (TCP/Telnet) or `serial` (COM port) |
| `PYLONTECH_PORT_OR_HOST` | `192.168.1.5` | The IP Address (for network) or the COM port name (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux/macOS) |
| `PYLONTECH_BAUD_OR_PORT` | `23` | The network port (typically `23` for Telnet) or the serial baud rate (typically `115200` for Pylontech console) |

### Configuration Examples

#### Example: Network (Telnet bridge)
```bash
# Linux/macOS
export PYLONTECH_CONN_TYPE="network"
export PYLONTECH_PORT_OR_HOST="192.168.1.5"
export PYLONTECH_BAUD_OR_PORT="23"
python pylontech_mcp.py

# Windows (PowerShell)
$env:PYLONTECH_CONN_TYPE="network"
$env:PYLONTECH_PORT_OR_HOST="192.168.1.5"
$env:PYLONTECH_BAUD_OR_PORT="23"
python pylontech_mcp.py
```

#### Example: Direct USB Console Cable (Serial)
```bash
# Windows
$env:PYLONTECH_CONN_TYPE="serial"
$env:PYLONTECH_PORT_OR_HOST="COM3"
$env:PYLONTECH_BAUD_OR_PORT="115200"
python pylontech_mcp.py
```

---

## 4. MCP Tools Provided

Once registered with your AI assistant, the server exposes the following tools:

1. **`raw_command(command)`**: Execute a permitted read-only query command and return the result formatted as a clean, structured JSON response.
2. **`get_pwr_status()`**: Retrieve the parsed live power status of all battery modules in the stack.
3. **`get_module_diagnostics(module_id)`**: Fetch all cell telemetry, SOH metrics, and statistics for a specific battery module parsed into a structured JSON dictionary.

---

## 5. Security & Safety Whitelist & Command Syntax

To prevent accidental stack shutdowns, resets, or configuration modifications, the server blocks all destructive or administrative commands. Only the following safe, read-only query commands are permitted by the `raw_command` tool:

### 1. Simple Telemetry Commands (Overall Stack vs. Module-Specific)
* **`pwr [index]`**: Module voltages, currents, temperatures, and basic protect statuses.
  * *Usage detail*: Running `pwr` returns overall battery stack telemetry from the master battery. Running `pwr 2` retrieves metrics specific to module #2.
* **`bat [index]`**: Individual cell voltages, currents, temperatures, and cell balancing states.
* **`soh [index]`**: Cell-by-cell voltages and local State of Health counters/statuses.
* **`info [index]`**: Manufacturer specifications, firmware versions, boot code versions, and hardware barcodes.
* **`stat [index]`**: Lifetime statistics (cycle count, resets, total discharged capacity, low voltage event deltas).
* **`getpwr [index]`**: Compact hash-delimited cell parameters.
* **`log [count]`**: BMS operational state transition log entries (e.g. charging and discharging starts).

### 2. Log History Commands (Correct Categorization & Syntax)
* **`data [event/history] [item_index]`**: Granular cell-by-cell voltages and protect details for a specific logged event or history index.
  * :warning: **Do not pass the module number directly as the first argument** (e.g. `data 2` will fail). You must specify the category `event` or `history`.
  * *Example (Latest History)*: `data history`
  * *Example (History Index #1790)*: `data history 1790`
  * *Example (Latest System Events)*: `data event`
  * *Example (Event Index #3)*: `data event 3`
* **`datalist [event/history] [item_index]`**: Chronological history timeline logs showing module-level status.
  * :warning: **Do not pass the module number directly as the first argument** (e.g. `datalist 2` will fail). To retrieve cell-specific logs for non-master modules, use the full sequential parameters:
  * *Correct Format*: `datalist [event/history] [item/bat] [batnum] [volt/curr/temp/coul] [item_index]`
  * *Example (Cell Voltages on Module #2)*: `datalist history bat 2 volt 1`
  * *Example (Cell Temperatures on Module #2)*: `datalist history bat 2 temp 1`
  * *Example (Cell Currents on Module #2)*: `datalist history bat 2 curr 1`
  * *Example (Cell Coulomb/SOC on Module #2)*: `datalist history bat 2 coul 1`

Any other command (e.g. `shut`, `trst`, `updata`, `login`) is rejected before execution.

---

## 6. Features & Reliability

* **Automatic JSON Serialization**: Telemetry values are parsed into numeric formats. Decorative terminal lines and trailing space paddings are stripped out. Values containing physics units (e.g. `mV`, `mA`, `%`, `mC`, `mAH`, `s`) are converted to standard integers/floats.
* **Auto-Paging Handler**: The server automatically detects the console paging prompt (`Press [Enter] to be continued,other key to exit`) and sends a carriage return (`\r`) in the background to stitch together multi-page records (crucial for long `datalist` history outputs).
* **Socket Buffer Drainage**: Flushes the TCP bridge connection buffer upon connection to clear any stale or interleaved serial characters from concurrent queries.

---

## 7. AI Agent Configuration Examples

To use this local MCP server with your AI agents, add the following configuration to their respective settings files.

### Configuration for OpenAI Codex
File path: `C:\Users\<user>\.codex\config.toml`

#### Option A: Network (TCP/Telnet bridge)
```toml
[mcp_servers.pylontech]
command = "python"
args = ["D:/Documents/GitHub/AI/mcp-servers/pylontech-mcp/pylontech_mcp.py"]
env = { PYLONTECH_CONN_TYPE = "network", PYLONTECH_PORT_OR_HOST = "192.168.1.5", PYLONTECH_BAUD_OR_PORT = "23" }
```

#### Option B: Direct Serial Cable (e.g. COM3 or /dev/ttyUSB0)
```toml
[mcp_servers.pylontech]
command = "python"
args = ["D:/Documents/GitHub/AI/mcp-servers/pylontech-mcp/pylontech_mcp.py"]
env = { PYLONTECH_CONN_TYPE = "serial", PYLONTECH_PORT_OR_HOST = "COM3", PYLONTECH_BAUD_OR_PORT = "115200" }
```

### Configuration for Google Antigravity
File path: `C:\Users\<user>\.gemini\config\mcp_config.json`

#### Option A: Network (TCP/Telnet bridge)
```json
{
  "mcpServers": {
    "pylontech": {
      "command": "python",
      "args": [
        "D:/Documents/GitHub/AI/mcp-servers/pylontech-mcp/pylontech_mcp.py"
      ],
      "env": {
        "PYLONTECH_CONN_TYPE": "network",
        "PYLONTECH_PORT_OR_HOST": "192.168.1.5",
        "PYLONTECH_BAUD_OR_PORT": "23"
      }
    }
  }
}
```

#### Option B: Direct Serial Cable (e.g. COM3 or /dev/ttyUSB0)
```json
{
  "mcpServers": {
    "pylontech": {
      "command": "python",
      "args": [
        "D:/Documents/GitHub/AI/mcp-servers/pylontech-mcp/pylontech_mcp.py"
      ],
      "env": {
        "PYLONTECH_CONN_TYPE": "serial",
        "PYLONTECH_PORT_OR_HOST": "COM3",
        "PYLONTECH_BAUD_OR_PORT": "115200"
      }
    }
  }
}
```

---

## 8. Disclaimer & Limitation of Liability

> [!CAUTION]
> **USE AT YOUR OWN RISK.** This software is provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement.
> 
> In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with this software or the use or other dealings in this software.
> 
> Interacting with physical hardware consoles (such as Pylontech LiFePo4 (Lithium Iron Phosphate) batteries) carries inherent hazards. Running unverified commands or using automated scripts to query equipment interfaces may cause system shutoff, battery management system (BMS) lockouts, thermal alarms, or electrical faults. The user assumes all responsibilities for command verification, physical safety precautions, and hardware protection when running this software.

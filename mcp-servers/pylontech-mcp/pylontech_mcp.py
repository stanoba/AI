# -*- coding: utf-8 -*-
"""Pylontech Battery Stack MCP Server.

Provides tools for AI agents to query a live Pylontech stack over:
1. Serial COM Port (RS232/RS485)
2. Network socket (Telnet/TCP on Port 23)

Requires:
    pip install mcp pyserial
"""

import os
import sys
import socket
import time
import re
import json
from typing import Optional, Dict, Any, List
try:
    import serial
except ImportError:
    serial = None

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
app = FastMCP("Pylontech Console")

# Connection Configuration (Loaded from environment variables)
CONN_TYPE = os.environ.get("PYLONTECH_CONN_TYPE", "network").lower()  # 'serial' or 'network'
PORT_OR_HOST = os.environ.get("PYLONTECH_PORT_OR_HOST", "192.168.1.5")
BAUD_OR_PORT = os.environ.get("PYLONTECH_BAUD_OR_PORT", "23")

class PylontechConnection:
    def __init__(self, conn_type: str, target: str, port_or_baud: str):
        self.conn_type = conn_type
        self.target = target
        self.port_or_baud = port_or_baud
        self.ser = None
        self.sock = None

    def connect(self):
        if self.conn_type == "serial":
            if not serial:
                raise RuntimeError("pyserial package is not installed. Run: pip install pyserial")
            self.ser = serial.Serial(self.target, int(self.port_or_baud), timeout=3)
        elif self.conn_type == "network":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.2)
            self.sock.connect((self.target, int(self.port_or_baud)))
            # Flush all greeting/leftover buffer until timeout
            while True:
                try:
                    discarded = self.sock.recv(4096)
                    if not discarded:
                        break
                except socket.timeout:
                    break
            self.sock.settimeout(5.0)
        else:
            raise ValueError(f"Unknown connection type: {self.conn_type}")

    def send_cmd(self, cmd: str) -> str:
        raw_cmd = f"{cmd}\r".encode('ascii')
        response = b""
        
        if self.conn_type == "serial":
            self.ser.write(raw_cmd)
            self.ser.flush()
            # Read response
            while True:
                chunk = self.ser.read(128)
                if not chunk:
                    break
                response += chunk
                
                # Auto-page if prompt is present in current buffer
                if b"Press [Enter] to be continued" in response:
                    # Strip the prompt from response to keep clean output, and send enter
                    response = response.replace(b"Press [Enter] to be continued,other key to exit", b"")
                    self.ser.write(b"\r")
                    self.ser.flush()
                    
                trimmed = response.strip()
                if trimmed.endswith(b"pylon>") or trimmed.endswith(b"$$"):
                    break
        else:
            self.sock.sendall(raw_cmd)
            while True:
                try:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    
                    # Auto-page if prompt is present in current buffer
                    if b"Press [Enter] to be continued" in response:
                        response = response.replace(b"Press [Enter] to be continued,other key to exit", b"")
                        self.sock.sendall(b"\r")
                        
                    trimmed = response.strip()
                    if trimmed.endswith(b"pylon>") or trimmed.endswith(b"$$"):
                        break
                except socket.timeout:
                    break
                    
        return response.decode('ascii', errors='ignore')

    def close(self):
        if self.ser:
            self.ser.close()
        if self.sock:
            self.sock.close()

def execute_console_command(cmd: str) -> str:
    """Helper to connect, send command, and return output."""
    conn = PylontechConnection(CONN_TYPE, PORT_OR_HOST, BAUD_OR_PORT)
    try:
        conn.connect()
        output = conn.send_cmd(cmd)
        return output
    except Exception as e:
        return f"Error connecting to Pylontech stack ({CONN_TYPE}://{PORT_OR_HOST}:{BAUD_OR_PORT}): {e}"
    finally:
        conn.close()

# ===== MCP TOOLS =====

def to_numeric(val: str) -> Any:
    # Remove common suffixes like mV, mA, mC, %, mAH, s at the end of the string
    clean_val = re.sub(r'\s*(mV|mA|mC|%|mAH|s)\s*$', '', val, flags=re.IGNORECASE).strip()
    if clean_val.isdigit():
        return int(clean_val)
    if clean_val.startswith('-') and clean_val[1:].isdigit():
        return int(clean_val)
    try:
        return float(clean_val)
    except ValueError:
        return val

def parse_info_output(raw: str) -> Dict[str, Any]:
    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        key = parts[0].strip().replace(" ", "_").lower()
        val = parts[1].strip()
        data[key] = to_numeric(val)
    return data

def parse_pwr_output(raw: str) -> Dict[str, Any]:
    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or ":" not in line or line.startswith("---"):
            continue
        parts = line.split(":", 1)
        key = parts[0].strip().replace(" ", "_").lower()
        val = parts[1].strip()
        data[key] = to_numeric(val)
    return data

def parse_bat_output(raw_bat: str) -> List[Dict[str, Any]]:
    cells = []
    lines = raw_bat.split('\n')
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\s+', line):
            parts = re.split(r'\s+', line)
            if len(parts) >= 11:
                cells.append({
                    "cell_id": int(parts[0]),
                    "voltage_mv": int(parts[1]) if parts[1].isdigit() else parts[1],
                    "current_ma": int(parts[2]) if parts[2].replace('-','').isdigit() else parts[2],
                    "temp_mc": int(parts[3]) if parts[3].isdigit() else parts[3],
                    "temp_c": float(parts[3])/1000.0 if parts[3].isdigit() else parts[3],
                    "state": parts[4],
                    "volt_state": parts[5],
                    "curr_state": parts[6],
                    "temp_state": parts[7],
                    "soc_percent": int(parts[8].replace('%', '')) if '%' in parts[8] else parts[8],
                    "coulomb_mah": int(parts[9]) if parts[9].isdigit() else parts[9],
                    "balancing": parts[10] == 'Y'
                })
    return cells

def parse_soh_output(raw_soh: str) -> List[Dict[str, Any]]:
    cells_soh = []
    lines = raw_soh.split('\n')
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\s+', line):
            parts = re.split(r'\s+', line)
            if len(parts) >= 4:
                cells_soh.append({
                    "cell_id": int(parts[0]),
                    "voltage_mv": int(parts[1]) if parts[1].isdigit() else parts[1],
                    "soh_count": int(parts[2]) if parts[2].isdigit() else parts[2],
                    "soh_status": parts[3]
                })
    return cells_soh

def parse_stat_output(raw_stat: str) -> Dict[str, Any]:
    stats = {}
    lines = raw_stat.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ':' in line:
            parts = line.split(':', 1)
            key = parts[0].strip().replace('.', '').replace(' ', '_').lower()
            val = parts[1].strip()
            stats[key] = to_numeric(val)
        else:
            parts = re.split(r'\s{2,}', line)
            if len(parts) == 2:
                key = parts[0].strip().replace('.', '').replace(' ', '_').lower()
                val = parts[1].strip()
                stats[key] = to_numeric(val)
    return stats

def parse_data_output(raw_data: str) -> List[Dict[str, Any]]:
    parts = raw_data.split('-----------------------------------------------')
    if len(parts) < 3:
        raise ValueError("Invalid data output format: missing separator lines.")
        
    records = []
    i = 1
    while i < len(parts) - 1:
        header_raw = parts[i]
        cells_raw = parts[i+1]
        
        header = {}
        for line in header_raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            subparts = line.split(":", 1)
            key = subparts[0].strip().replace(" ", "_").lower().replace('.', '')
            val = subparts[1].strip()
            header[key] = to_numeric(val)
            
        cells = []
        for line in cells_raw.splitlines():
            line = line.strip()
            if re.match(r'^\d+\s+', line):
                cell_parts = re.split(r'\s+', line)
                if len(cell_parts) >= 9:
                    cells.append({
                        "cell_id": int(cell_parts[0]),
                        "voltage_mv": int(cell_parts[1]) if cell_parts[1].isdigit() else cell_parts[1],
                        "current_ma": int(cell_parts[2]) if cell_parts[2].replace('-','').isdigit() else cell_parts[2],
                        "temp_mc": int(cell_parts[3]) if cell_parts[3].isdigit() else cell_parts[3],
                        "temp_c": float(cell_parts[3])/1000.0 if cell_parts[3].isdigit() else cell_parts[3],
                        "state": cell_parts[4],
                        "volt_state": cell_parts[5],
                        "curr_state": cell_parts[6],
                        "temp_state": cell_parts[7],
                        "soc_percent": int(cell_parts[8].replace('%', '')) if '%' in cell_parts[8] else cell_parts[8]
                    })
        
        if header:
            records.append({
                "metadata": header,
                "cells": cells
            })
            
        i += 2
        
    return records

def parse_datalist_output(raw_output: str) -> Dict[str, Any]:
    save_interval = None
    records = []
    headers = []
    
    interval_match = re.search(r'Save data every\s+(\d+)\s+S', raw_output, re.IGNORECASE)
    if interval_match:
        save_interval = int(interval_match.group(1))
        
    lines = raw_output.splitlines()
    header_idx = -1
    
    for idx, line in enumerate(lines):
        line_clean = line.strip()
        if re.search(r'\bItem\b', line_clean, re.IGNORECASE) and re.search(r'\bTime\b', line_clean, re.IGNORECASE):
            header_idx = idx
            headers = re.split(r'\s+', line_clean)
            break
            
    if header_idx != -1 and headers:
        for line in lines[header_idx + 1:]:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^\d+\s+\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', line):
                parts = re.split(r'\s+', line)
                if len(parts) >= 3:
                    record = {
                        "item": int(parts[0]),
                        "time": f"{parts[1]} {parts[2]}"
                    }
                    
                    part_idx = 3
                    head_idx = 2
                    while head_idx < len(headers) and part_idx < len(parts):
                        head_name = headers[head_idx].lower().replace('(', '_').replace(')', '').replace('.', '_')
                        val_str = parts[part_idx]
                        
                        record[head_name] = to_numeric(val_str)
                        
                        # Add a helper float temp conversion if it matches cell/module temperature fields
                        if head_name in {"tempr", "tlow", "thigh"} or head_name.startswith("temp"):
                            try:
                                record[head_name + "_c"] = float(record[head_name]) / 1000.0
                            except (ValueError, TypeError):
                                pass
                                
                        part_idx += 1
                        head_idx += 1
                        
                    if part_idx < len(parts):
                        record["remaining_data"] = [to_numeric(p) for p in parts[part_idx:]]
                        
                    records.append(record)
    else:
        # Fallback when there is no header row (e.g. datalist history bat X volt Y)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^\d+\s+\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', line):
                parts = re.split(r'\s+', line)
                if len(parts) >= 3:
                    record = {
                        "item": int(parts[0]),
                        "time": f"{parts[1]} {parts[2]}"
                    }
                    if len(parts) >= 4:
                        record["module_id"] = int(parts[3]) if parts[3].isdigit() else parts[3]
                        # Map any columns after the module_id (parts[4:]) as generic cell/telemetry values
                        for cell_idx, val_str in enumerate(parts[4:]):
                            record[f"cell_{cell_idx}"] = to_numeric(val_str)
                    records.append(record)
                    
    return {
        "save_interval_seconds": save_interval,
        "records": records
    }

def parse_log_output(raw_output: str) -> List[Dict[str, Any]]:
    parts = re.split(r'Index\s*:', raw_output, flags=re.IGNORECASE)
    records = []
    
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        index_val = lines[0].strip()
        if not index_val.isdigit():
            continue
            
        record = {"index": int(index_val)}
        for line in lines[1:]:
            line = line.strip()
            if not line or ":" not in line:
                continue
            subparts = line.split(":", 1)
            key = subparts[0].strip().replace(" ", "_").lower().replace('.', '')
            if key in {"press", "command", "$$"}:
                continue
            val = subparts[1].strip()
            record[key] = to_numeric(val)
            
        records.append(record)
        
    return records

def parse_getpwr_output(raw_output: str) -> Dict[str, Any]:
    lines = []
    for line in raw_output.splitlines():
        line = line.strip()
        if line.endswith('#'):
            lines.append(line)
            
    if len(lines) < 3:
        raise ValueError("Invalid getpwr output format: too few hash-terminated lines.")
        
    mod_parts = [p.strip() for p in lines[0].split('#')]
    module_data = {
        "voltage_mv": int(mod_parts[0]) if mod_parts[0].isdigit() else mod_parts[0],
        "current_ma": int(mod_parts[1]) if mod_parts[1].replace('-','').isdigit() else mod_parts[1],
        "temp_mc": int(mod_parts[2]) if mod_parts[2].isdigit() else mod_parts[2],
        "temp_c": float(mod_parts[2])/1000.0 if mod_parts[2].isdigit() else mod_parts[2],
        "coulomb_mah": int(mod_parts[3]) if mod_parts[3].isdigit() else mod_parts[3],
        "state": mod_parts[4],
        "volt_state": mod_parts[5],
        "curr_state": mod_parts[6],
        "temp_state": mod_parts[7]
    }
    
    cells = []
    cell_lines = lines[1:-2]
    for idx, cell_line in enumerate(cell_lines):
        cell_parts = [p.strip() for p in cell_line.split('#')]
        if len(cell_parts) >= 4:
            cells.append({
                "cell_id": idx,
                "voltage_mv": int(cell_parts[0]) if cell_parts[0].isdigit() else cell_parts[0],
                "temp_mc": int(cell_parts[1]) if cell_parts[1].isdigit() else cell_parts[1],
                "temp_c": float(cell_parts[1])/1000.0 if cell_parts[1].isdigit() else cell_parts[1],
                "volt_state": cell_parts[2],
                "temp_state": cell_parts[3]
            })
            
    extra_1 = lines[-2].replace('#', '').strip()
    extra_2 = lines[-1].replace('#', '').strip()
    
    return {
        "module": module_data,
        "cells": cells,
        "extra_field_1": int(extra_1) if extra_1.isdigit() else extra_1,
        "extra_field_2": int(extra_2) if extra_2.isdigit() else extra_2
    }

def to_json_response(command: str, raw_output: str) -> str:
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return json.dumps({"error": "Empty command", "raw": raw_output})
    
    base_cmd = cmd_parts[0].lower()
    
    if "invalid command" in raw_output.lower() or "fail to excute" in raw_output.lower() or "not target device" in raw_output.lower():
        return json.dumps({
            "command": command,
            "success": False,
            "error": raw_output.strip()
        }, indent=2)
        
    try:
        if base_cmd == "info":
            parsed = parse_info_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "pwr":
            parsed = parse_pwr_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "bat":
            parsed = parse_bat_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "soh":
            parsed = parse_soh_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "stat":
            parsed = parse_stat_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "data":
            parsed = parse_data_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "datalist":
            parsed = parse_datalist_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "log":
            parsed = parse_log_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
        elif base_cmd == "getpwr":
            parsed = parse_getpwr_output(raw_output)
            return json.dumps({"command": command, "success": True, "data": parsed, "raw": raw_output.strip()}, indent=2)
    except Exception as e:
        return json.dumps({
            "command": command,
            "success": False,
            "error": f"Failed to parse command output: {str(e)}",
            "raw": raw_output.strip()
        }, indent=2)
        
    return json.dumps({
        "command": command,
        "success": True,
        "raw": raw_output.strip()
    }, indent=2)

@app.tool()
def raw_command(command: str) -> str:
    """Execute a permitted read-only query command on the Pylontech battery stack console.
    
    Dangerous administrative commands (like 'shut', 'trst', 'updata', 'login') are blocked.
    
    ALLOWED COMMANDS & SYNTAX RULES:
    1. simple commands: pwr, bat, soh, info, stat, getpwr
       - Run alone (e.g., 'pwr') to get overall stack info via master battery, or with module index (e.g., 'pwr 2') for specific module telemetry.
    2. 'log [count]': BMS operational state transition log entries (e.g. 'log 10').
    3. 'data [event/history] [item_index]': Detailed cell voltages & protect statuses.
       - WARNING: Do NOT pass module number as the first argument (e.g. 'data 2' is INVALID).
       - Examples: 'data history', 'data history 1790', 'data event', 'data event 3'.
    4. 'datalist [event/history] [item/bat] [batnum] [volt/curr/temp/coul] [item_index]': Historical timeline records.
       - WARNING: Do NOT pass module number as the first argument (e.g. 'datalist 2' is INVALID).
       - Examples for Module #2 cell voltage history: 'datalist history bat 2 volt 1'.
       - Examples for Module #2 cell temperature history: 'datalist history bat 2 temp 1'.
    """
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return json.dumps({"error": "Empty command"})
    
    base_cmd = cmd_parts[0].lower()
    allowed_commands = {"pwr", "bat", "soh", "info", "stat", "data", "datalist", "log", "getpwr"}
    if base_cmd not in allowed_commands:
        return json.dumps({
            "error": f"Command '{base_cmd}' is not allowed. Only read-only query commands are permitted ({', '.join(sorted(allowed_commands))})."
        })
        
    raw_output = execute_console_command(command)
    return to_json_response(command, raw_output)

@app.tool()
def get_pwr_status() -> Dict[str, Any]:
    """Retrieve and parse the live power status of all battery modules in the stack."""
    raw = execute_console_command("pwr")
    
    # Parse modules from the output
    modules = []
    lines = raw.split('\n')
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\s+', line):
            parts = re.split(r'\s+', line)
            if len(parts) >= 12 and parts[8] != "Absent":
                modules.append({
                    "battery_id": int(parts[0]),
                    "voltage_mv": int(parts[1]) if parts[1].isdigit() else parts[1],
                    "current_ma": int(parts[2]) if parts[2].replace('-','').isdigit() else parts[2],
                    "temp_mc": int(parts[3]) if parts[3].isdigit() else parts[3],
                    "temp_c": float(parts[3])/1000.0 if parts[3].isdigit() else parts[3],
                    "state": parts[8],
                    "soc": parts[12],
                    "mos_temp_c": float(parts[14])/1000.0 if len(parts) > 14 and parts[14].isdigit() else "N/A"
                })
    return {
        "raw_response": raw,
        "active_modules_count": len(modules),
        "modules": modules
    }

@app.tool()
def get_module_diagnostics(module_id: int) -> Dict[str, Any]:
    """Retrieve SOH, stats, and cell details for a specific battery module by ID."""
    pwr = execute_console_command(f"pwr {module_id}")
    bat = execute_console_command(f"bat {module_id}")
    soh = execute_console_command(f"soh {module_id}")
    stat = execute_console_command(f"stat {module_id}")
    
    return {
        "module_id": module_id,
        "cells": parse_bat_output(bat),
        "soh": parse_soh_output(soh),
        "statistics": parse_stat_output(stat),
        "raw_responses": {
            "pwr": pwr,
            "bat": bat,
            "soh": soh,
            "stat": stat
        }
    }

if __name__ == "__main__":
    # Start the FastMCP server (defaults to stdio communication channel)
    app.run()

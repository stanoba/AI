# -*- coding: utf-8 -*-
"""UniFi Network Monitoring MCP Server.

Provides tools for AI agents to query status, active clients, adopted devices,
health metrics, and alerts from a local UniFi controller.

Requires:
    pip install mcp requests python-dotenv
"""

import os
import sys
import json
import urllib3
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Suppress insecure request warnings from self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load local .env file if it exists
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Initialize FastMCP Server
app = FastMCP("UniFi Network")

# Load environment configuration
UNIFI_URL = os.environ.get("UNIFI_URL", "https://10.1.0.1")
UNIFI_USERNAME = os.environ.get("UNIFI_USERNAME", "")
UNIFI_PASSWORD = os.environ.get("UNIFI_PASSWORD", "")
UNIFI_SITE = os.environ.get("UNIFI_SITE", "default")

# Determine if it's a classic controller (often runs on port 8443)
IS_CLASSIC = ":8443" in UNIFI_URL

class UniFiClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # Skip TLS verification for local self-signed certs
        self.logged_in = False

    def login(self):
        login_endpoint = "/api/login" if IS_CLASSIC else "/api/auth/login"
        url = f"{UNIFI_URL.rstrip('/')}{login_endpoint}"
        payload = {
            "username": UNIFI_USERNAME,
            "password": UNIFI_PASSWORD
        }
        try:
            response = self.session.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.logged_in = True
                return True
            else:
                raise RuntimeError(f"Login failed (status {response.status_code}): {response.text}")
        except Exception as e:
            raise RuntimeError(f"Error logging in to UniFi Controller: {e}")

    def get(self, endpoint: str):
        if not self.logged_in:
            self.login()
            
        # Format the URL based on classic vs modern console
        if IS_CLASSIC:
            if endpoint.startswith("/api/"):
                url = f"{UNIFI_URL.rstrip('/')}{endpoint}"
            else:
                url = f"{UNIFI_URL.rstrip('/')}/api/s/{UNIFI_SITE}/{endpoint}"
        else:
            if endpoint.startswith("/api/"):
                url = f"{UNIFI_URL.rstrip('/')}/proxy/network{endpoint}"
            else:
                url = f"{UNIFI_URL.rstrip('/')}/proxy/network/api/s/{UNIFI_SITE}/{endpoint}"

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Session might have expired, try logging in again
                self.logged_in = False
                self.login()
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    return response.json()
            raise RuntimeError(f"API call to {endpoint} failed (status {response.status_code}): {response.text}")
        except Exception as e:
            raise RuntimeError(f"API request failed: {e}")

# Helper to create client and run
def get_client():
    if not UNIFI_USERNAME or not UNIFI_PASSWORD:
        raise ValueError("UNIFI_USERNAME and UNIFI_PASSWORD must be configured in environment variables or .env file.")
    client = UniFiClient()
    client.login()
    return client

@app.tool()
def unifi_get_health() -> str:
    """Query the UniFi site-wide health summary for WAN, LAN, WLAN, etc."""
    try:
        client = get_client()
        data = client.get("stat/health")
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_devices() -> str:
    """List all adopted UniFi devices (Access Points, Switches, Gateways) on the network."""
    try:
        client = get_client()
        data = client.get("stat/device")
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_clients() -> str:
    """List all currently active client stations (wired and wireless) connected to the network."""
    try:
        client = get_client()
        data = client.get("stat/sta")
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_top_apps(limit: int = 10) -> str:
    """Get the top network applications by bandwidth consumption (DPI stats)."""
    try:
        client = get_client()
        data = client.get("stat/sitedpi")
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_alerts(limit: int = 20) -> str:
    """Retrieve the list of recent alarms and security/connection events from the controller."""
    try:
        client = get_client()
        data = client.get("stat/alarm")
        if isinstance(data, dict) and "data" in data:
            data["data"] = data["data"][:limit]
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_dashboard() -> str:
    """Generate a combined health, device, and client count overview of the network."""
    try:
        client = get_client()
        health = client.get("stat/health")
        devices = client.get("stat/device")
        clients = client.get("stat/sta")
        
        summary = {
            "health": health.get("data", []),
            "device_summary": {
                "total": len(devices.get("data", [])),
                "adopted": sum(1 for d in devices.get("data", []) if d.get("state") == 1),
                "disconnected": sum(1 for d in devices.get("data", []) if d.get("state") != 1)
            },
            "client_summary": {
                "total": len(clients.get("data", [])),
                "wired": sum(1 for c in clients.get("data", []) if c.get("is_wired")),
                "wireless": sum(1 for c in clients.get("data", []) if not c.get("is_wired"))
            }
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_get_events(limit: int = 100) -> str:
    """Retrieve the recent system event log stream from the UniFi controller."""
    try:
        client = get_client()
        data = client.get("stat/event")
        if isinstance(data, dict) and "data" in data:
            data["data"] = data["data"][:limit]
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"

@app.tool()
def unifi_analyze_disconnects(limit: int = 1000) -> str:
    """Analyze recent events to detect and correlate AP link loss with client disconnections."""
    try:
        client = get_client()
        events_response = client.get("stat/event")
        events = events_response.get("data", [])[:limit]
        
        ap_disconnects = {}
        client_disconnects = {}
        client_auth_failures = {}
        
        # Group event data
        for e in events:
            key = e.get("key", "")
            msg = e.get("msg", "")
            dt = e.get("datetime", "")
            time_sec = e.get("time", 0) // 1000
            
            # AP Disconnects
            if "Lost_Contact" in key or ("disconnected" in msg.lower() and "ap" in msg.lower()):
                ap_name = e.get("ap_name") or e.get("ap") or "Unknown AP"
                ap_disconnects.setdefault(ap_name, []).append((time_sec, dt))
                
            # Client Disconnects
            if "WU_Disconnected" in key or "Disconnected" in msg:
                user = e.get("hostname") or e.get("user") or e.get("mac") or "Unknown Client"
                client_disconnects.setdefault(user, []).append((time_sec, dt))
                
            # Auth Failures
            if "Failed_To_Authorize" in key or "WPA" in msg or "key exchange" in msg:
                user = e.get("hostname") or e.get("user") or e.get("mac") or "Unknown Client"
                client_auth_failures.setdefault(user, []).append((time_sec, dt))
                
        # Calculate correlations (client disconnect within -2 to +5 seconds of an AP drop)
        correlations = []
        for ap_name, drops in ap_disconnects.items():
            for ap_time, ap_dt in drops:
                correlated_clients = []
                for client_name, client_drops in client_disconnects.items():
                    for c_time, c_dt in client_drops:
                        if ap_time - 2 <= c_time <= ap_time + 5:
                            correlated_clients.append(client_name)
                if correlated_clients:
                    correlations.append({
                        "ap": ap_name,
                        "time": ap_dt,
                        "dropped_clients": list(set(correlated_clients))
                    })
                    
        summary = {
            "total_events_analyzed": len(events),
            "ap_disconnect_counts": {ap: len(times) for ap, times in ap_disconnects.items()},
            "top_client_disconnect_counts": dict(sorted(
                {c: len(times) for c, times in client_disconnects.items()}.items(),
                key=lambda x: x[1], reverse=True
            )[:10]),
            "top_client_auth_failures": dict(sorted(
                {c: len(times) for c, times in client_auth_failures.items()}.items(),
                key=lambda x: x[1], reverse=True
            )[:10]),
            "correlated_disconnect_events": correlations[:20]  # Return top 20 correlations
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    app.run()

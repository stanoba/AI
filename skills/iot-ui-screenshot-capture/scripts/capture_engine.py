#!/usr/bin/env python3
"""
IoT UI Screenshot Capture Engine
Automated screenshot capture with live anonymization proxy, theme injection,
synthetic telemetry generation, dynamic subnet masking, and smart PIL cropping.
"""

import os
import sys
import re
import json
import time
import shutil
import argparse
import threading
import subprocess
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def find_browser():
    """Detect installed Google Chrome or Microsoft Edge executable."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "chrome"

def load_local_overrides():
    """Load private device IPs from untracked local config if present."""
    search_paths = [
        ".devices.local.json",
        "devices.local.json",
        ".devices.json",
        os.path.expanduser("~/.iot_devices.json"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"[*] Loaded local device config from: {p}")
                    return data
            except Exception as e:
                print(f"[!] Warning reading {p}: {e}")
    return {}

def generate_solar_telemetry(count=288, now=None):
    """Generate realistic 24-hour solar battery telemetry curve."""
    if now is None:
        now = int(time.time())
    start_t = now - 86400
    step = 86400 // count
    samples = []

    for i in range(count):
        t = start_t + i * step
        progress = i / (count - 1)
        hour = progress * 24.0

        if hour < 6.0:
            # Night steady discharge
            soc = 75.0 - (hour / 6.0) * 40.0
            curr = -5.5 + 0.8 * (i % 3 - 1)
        elif hour < 11.0:
            # Morning solar charging ramp
            p = (hour - 6.0) / 5.0
            soc = 35.0 + p * 45.0
            curr = 15.0 + p * 30.0 + 1.2 * (i % 4 - 1.5)
        elif hour < 14.0:
            # Peak solar & battery saturation
            p = (hour - 11.0) / 3.0
            soc = 80.0 + p * 19.5
            curr = 45.0 - p * 40.0 + 1.0 * (i % 3 - 1)
        elif hour < 17.5:
            # Afternoon float
            soc = 99.5 - (hour - 14.0) * 0.4
            curr = 1.5 - 2.0 * (hour - 14.0) + 0.6 * (i % 3 - 1)
        elif hour < 19.5:
            # Evening high household load
            p = (hour - 17.5) / 2.0
            soc = 98.0 - p * 6.0
            curr = -12.0 - p * 12.0 + 1.0 * (i % 3 - 1)
        else:
            # Evening transition matching live dashboard
            p = (hour - 19.5) / 4.5
            soc = 92.0 - p * 3.0
            curr = -20.0 + p * 4.45

        samples.append({
            "t": t,
            "c": round(curr, 2),
            "s": int(round(soc))
        })
    samples[-1]["c"] = -15.55
    samples[-1]["s"] = 89
    return samples

class ProxyHandler(BaseHTTPRequestHandler):
    primary_ip = "127.0.0.1"
    secondary_ip = "127.0.0.1"
    replacements = []
    anonymize = True
    mock_chart = True

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        theme = qs.get("theme", [None])[0]
        device = qs.get("dev", ["primary"])[0]

        # Intercept /api/history for rich telemetry charts if enabled
        if self.mock_chart and parsed.path == "/api/history":
            samples = generate_solar_telemetry()
            resp_data = json.dumps({
                "status": "ok",
                "range": 86400,
                "count": len(samples),
                "samples": samples
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_data)))
            self.end_headers()
            self.wfile.write(resp_data)
            return

        target_host = self.secondary_ip if (device in ["emulator", "secondary"]) else self.primary_ip

        # Clean query string for forwarding
        clean_qs = {k: v for k, v in qs.items() if k not in ["theme", "dev"]}
        clean_query = urllib.parse.urlencode(clean_qs, doseq=True)
        target_path = parsed.path + ("?" + clean_query if clean_query else "")
        target_url = f"http://{target_host}{target_path}"

        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req, timeout=8) as resp:
                content_type = resp.headers.get("Content-Type", "text/html")
                body = resp.read()

                if "text" in content_type or "json" in content_type or "javascript" in content_type:
                    text = body.decode("utf-8", errors="replace")

                    if self.anonymize:
                        for old_val, new_val in self.replacements:
                            if old_val and old_val in text:
                                text = text.replace(old_val, new_val)

                        # Automatic fallback regex mask for any remaining hardware MAC addresses
                        mac_pattern = re.compile(r'\b([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})\b')
                        text = mac_pattern.sub(lambda m: "AA-BB-CC-DD-EE-FF" if "-" in m.group(0) else "AA:BB:CC:DD:EE:FF", text)

                    # Propagate dev parameter to CSS link
                    text = text.replace('href="/style.css', f'href="/style.css?dev={device}&')

                    # Inject theme override if requested
                    if theme in ["light", "dark"] and "<head>" in text:
                        if theme == "dark":
                            inject = "<script>document.documentElement.classList.add('dark');localStorage.setItem('pylon_theme','dark');</script>"
                            text = text.replace("<html", '<html class="dark"')
                        else:
                            inject = "<script>document.documentElement.classList.remove('dark');localStorage.setItem('pylon_theme','light');</script>"
                            text = text.replace('class="dark"', '')
                        text = text.replace("<head>", "<head>" + inject, 1)

                    body = text.encode("utf-8")

                self.send_response(resp.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except Exception:
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def log_message(self, format, *args):
        pass # Silent

def smart_crop_bottom(image_path, bottom_padding=30):
    """Automatically trim empty background padding from bottom of screenshot."""
    if not HAS_PIL:
        return
    try:
        im = Image.open(image_path).convert('RGB')
        w, h = im.size
        bg = im.getpixel((10, h - 10))

        last_y = h - 1
        for y in range(h - 1, int(h * 0.3), -1):
            row_diff = False
            for x in range(20, w - 20, 4):
                px = im.getpixel((x, y))
                if abs(px[0] - bg[0]) > 12 or abs(px[1] - bg[1]) > 12 or abs(px[2] - bg[2]) > 12:
                    row_diff = True
                    break
            if row_diff:
                last_y = y
                break

        crop_height = min(h, last_y + bottom_padding)
        if crop_height > 400 and crop_height < h:
            cropped = im.crop((0, 0, w, crop_height))
            cropped.save(image_path, quality=95)
            print(f"  [Crop] {os.path.basename(image_path)}: {h}px -> {crop_height}px")
    except Exception as e:
        print(f"  [Crop Warning] {image_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="IoT UI Screenshot Capture Engine")
    parser.add_argument("-c", "--config", help="Path to JSON configuration preset", default=None)
    parser.add_argument("--primary-ip", help="Primary device IP address", default=None)
    parser.add_argument("--secondary-ip", help="Secondary / Emulator IP address", default=None)
    parser.add_argument("-p", "--port", type=int, help="Proxy server port", default=8765)
    parser.add_argument("-o", "--output-dir", help="Output directory for assets", default="assets")
    parser.add_argument("-a", "--artifacts-dir", help="Antigravity artifacts directory (optional)", default=None)
    parser.add_argument("--virtual-time", type=int, help="Chrome virtual time budget in ms", default=2000)
    args = parser.parse_args()

    cfg = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    local_overrides = load_local_overrides()

    # Determine primary IP (CLI > Local file > ENV > Preset > Default)
    primary_ip = (
        args.primary_ip or
        local_overrides.get("primary_ip") or
        os.getenv("IOT_PRIMARY_IP") or
        cfg.get("primary_ip") or
        "192.168.1.150"
    )

    # Determine secondary IP
    secondary_ip = (
        args.secondary_ip or
        local_overrides.get("secondary_ip") or
        os.getenv("IOT_SECONDARY_IP") or
        cfg.get("secondary_ip") or
        "192.168.1.153"
    )

    proxy_port = cfg.get("proxy_port", args.port)
    output_dir = cfg.get("output_dir", args.output_dir)
    virtual_time = cfg.get("virtual_time_budget_ms", args.virtual_time)
    local_replacements = list(local_overrides.get("replacements", []))
    replacements = local_replacements + list(cfg.get("replacements", []))
    captures = cfg.get("captures", [])
    anonymize = cfg.get("anonymize", True)
    mock_chart = cfg.get("mock_chart", True)

    # Automatic Subnet Anonymization:
    # If the real device IP is on a private subnet (e.g. 10.0.0.50 or 192.168.10.20), automatically
    # add dynamic replacement rules to mask the whole subnet to 192.168.1.*
    if anonymize and primary_ip and "." in primary_ip:
        octets = primary_ip.split(".")
        if len(octets) == 4:
            real_subnet = f"{octets[0]}.{octets[1]}.{octets[2]}."
            if real_subnet != "192.168.1.":
                dynamic_rules = [
                    (primary_ip, "192.168.1.150"),
                    (secondary_ip, "192.168.1.153"),
                    (f"{real_subnet}1", "192.168.1.1"),
                    (f"{real_subnet}11", "192.168.1.1"),
                    (real_subnet, "192.168.1."),
                ]
                # Prepend dynamic subnet rules
                replacements = dynamic_rules + replacements
                print(f"[*] Auto-detected real subnet '{real_subnet}*' -> Masking to '192.168.1.*'")

    ProxyHandler.primary_ip = primary_ip
    ProxyHandler.secondary_ip = secondary_ip
    ProxyHandler.replacements = replacements
    ProxyHandler.anonymize = anonymize
    ProxyHandler.mock_chart = mock_chart

    # Start Anonymizing Reverse Proxy Server
    server = ThreadingHTTPServer(("127.0.0.1", proxy_port), ProxyHandler)
    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()
    time.sleep(1)

    os.makedirs(output_dir, exist_ok=True)
    if args.artifacts_dir:
        os.makedirs(args.artifacts_dir, exist_ok=True)

    browser = find_browser()
    print(f"[*] Starting screenshot capture using browser: {browser}")
    print(f"[*] Reverse Proxy active on http://127.0.0.1:{proxy_port}/ (Target Primary: {primary_ip}, Secondary: {secondary_ip})")
    print(f"[*] Capturing {len(captures)} view(s) to '{output_dir}'...\n")

    for item in captures:
        filename = item["filename"]
        path = item["path"]
        width = item.get("width", 1280)
        height = item.get("height", 2400)

        out_path = os.path.join(output_dir, filename)
        url = f"http://127.0.0.1:{proxy_port}{path}"
        print(f"  -> Capturing {filename} from {url} ({width}x{height})...")

        cmd = [
            browser,
            "--headless=new",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--virtual-time-budget={virtual_time}",
            f"--window-size={width},{height}",
            f"--screenshot={out_path}",
            url
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, timeout=25)
            time.sleep(0.4)
            if os.path.exists(out_path):
                smart_crop_bottom(out_path, bottom_padding=30)
                if args.artifacts_dir:
                    art_path = os.path.join(args.artifacts_dir, filename)
                    shutil.copy2(out_path, art_path)
                print(f"     [OK] Saved: {filename} ({os.path.getsize(out_path)} bytes)")
            else:
                print(f"     [FAIL] Output file not created: {filename}")
        except Exception as e:
            print(f"     [ERROR] Failed to capture {filename}: {e}")

    print("\n[+] All UI screenshots captured and anonymized successfully!")
    server.shutdown()

if __name__ == "__main__":
    main()

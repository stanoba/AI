# -*- coding: utf-8 -*-
"""Pylontech US3000C Console Log Parser & Analyzer.

Designed to be used as a helper script in the pylontech_analysis skill.
Compatible with all AI agents.
"""
import sys
import re

def parse_console_log(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split into commands based on the prompt pattern: pylon>command or just command name
    # We will search for sections starting with "pylon>pwr", "pylon>stat", "pylon>bat", "pylon>soh", "pylon>info"
    sections = {}
    
    # Simple regex to split by command prompts
    cmd_splits = re.split(r'pylon\s*>\s*([a-zA-Z0-9_\s]+)\n', content)
    
    if len(cmd_splits) > 1:
        for i in range(1, len(cmd_splits), 2):
            cmd_name = cmd_splits[i].strip()
            cmd_body = cmd_splits[i+1] if i+1 < len(cmd_splits) else ""
            # Strip trailing prompt symbols
            cmd_body = cmd_body.split('pylon>')[0].split('Command completed')[0].strip('@\n$ ')
            sections[cmd_name] = cmd_body
    else:
        # Fallback if no prompt found - look for command blocks manually
        for cmd in ['pwr', 'bat', 'soh', 'stat', 'info']:
            # Search for instances
            matches = list(re.finditer(rf'(?:^|\n){cmd}(?:\s+\d+)?(?:\r?\n)', content))
            for idx, match in enumerate(matches):
                start = match.end()
                end = matches[idx+1].start() if idx+1 < len(matches) else len(content)
                # Slice body
                body = content[start:end]
                # Cleanup body
                body = body.split('Command completed')[0].strip('@\n$ ')
                name = match.group(0).strip()
                sections[name] = body

    return sections

def parse_pwr(body):
    if not body:
        return []
    lines = [line.strip() for line in body.split('\n') if line.strip()]
    if not lines:
        return []
    
    # Look for header line and data lines
    headers = None
    data_rows = []
    for line in lines:
        if 'Power Volt' in line or 'Base.St' in line:
            headers = [h.strip() for h in re.split(r'\s{2,}', line) if h.strip()]
            continue
        # Data line starts with a number (battery ID)
        if re.match(r'^\d+\s+', line):
            parts = re.split(r'\s+', line)
            if len(parts) >= 12:
                # Merge datetime if present
                # 2026-07-11 11:28:16 is 2 parts
                data_rows.append(parts)
    return data_rows

def print_summary(sections):
    print("="*60)
    print("  PYLONTECH CONSOLE LOG ANALYSIS SUMMARY")
    print("="*60)
    
    # PWR Section
    pwr_body = sections.get('pwr')
    if pwr_body:
        print("\n[pwr] Module Power Status:")
        rows = parse_pwr(pwr_body)
        print(f"  {'Bat':<4} {'Volt (mV)':<10} {'Curr (mA)':<10} {'Temp (°C)':<10} {'SoC':<6} {'State':<8} {'Spread':<8}")
        print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*6} {'-'*8} {'-'*8}")
        for r in rows:
            try:
                bat_id = r[0]
                volt = r[1]
                curr = r[2]
                temp = float(r[3])/1000.0 if r[3].isdigit() else r[3]
                soc = r[12] if len(r) > 12 else "N/A"
                state = r[8]
                vlow = int(r[6]) if r[6].isdigit() else 0
                vhigh = int(r[7]) if r[7].isdigit() else 0
                spread = f"{vhigh - vlow} mV" if vhigh > 0 else "N/A"
                print(f"  #{bat_id:<3} {volt:<10} {curr:<10} {temp:<10.1f} {soc:<6} {state:<8} {spread:<8}")
            except Exception as e:
                print(f"  Error parsing row: {r} ({e})")
                
    # BAT / SOH Sections
    for b in range(1, 13):
        bat_cmd = f"bat {b}"
        if bat_cmd in sections:
            print(f"\n[{bat_cmd}] Cell Balance Details:")
            lines = [l.strip() for l in sections[bat_cmd].split('\n') if l.strip()]
            cells = []
            for l in lines:
                if re.match(r'^\d+\s+', l):
                    parts = re.split(r'\s+', l)
                    if len(parts) >= 8:
                        cells.append(parts)
            if cells:
                voltages = [int(c[1]) for c in cells if c[1].isdigit()]
                coulombs = [int(c[9].replace('mAH','')) for c in cells if c[9].replace('mAH','').isdigit()]
                print(f"    Voltage range: {min(voltages)} - {max(voltages)} mV (spread: {max(voltages)-min(voltages)} mV)")
                print(f"    Coulomb range: {min(coulombs)} - {max(coulombs)} mAh (spread: {max(coulombs)-min(coulombs)} mAh)")
                
        soh_cmd = f"soh {b}"
        if soh_cmd in sections:
            lines = [l.strip() for l in sections[soh_cmd].split('\n') if l.strip()]
            soh_counts = []
            for l in lines:
                if re.match(r'^\d+\s+', l):
                    parts = re.split(r'\s+', l)
                    if len(parts) >= 3 and parts[2].isdigit():
                        soh_counts.append((parts[0], int(parts[2])))
            bad_soh = [x for x in soh_counts if x[1] > 0]
            if bad_soh:
                print(f"    ⚠️ Non-zero SOHCount found: {bad_soh}")
            else:
                print("    ✓ All cell SOHCounts are 0 (healthy)")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_pylontech.py <console_log_file>")
        sys.exit(1)
    
    sections = parse_console_log(sys.argv[1])
    print_summary(sections)
 Tracy.py

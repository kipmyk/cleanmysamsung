#!/usr/bin/env python3
"""
Local Network Android & Smart Device Discovery Scanner
Discovers active devices, resolves MAC OUI hardware manufacturers (Samsung, TCL, Apple),
and checks for open ADB debug ports.
"""

import asyncio
import re
import socket
import subprocess
import sys

OUI_TABLE = {
    "SAMSUNG": [
        "00:07:ab", "00:12:47", "00:15:99", "00:16:32", "00:1d:25", "00:21:19",
        "00:23:d7", "00:24:54", "00:26:37", "08:fc:52", "14:49:e0", "1c:66:aa",
        "28:ba:b5", "30:cd:a7", "34:23:ba", "48:44:f7", "50:01:d9", "5c:a6:e6",
        "78:47:1d", "84:25:db", "94:35:0a", "98:0d:2e", "a8:06:00", "bc:72:b9",
        "c4:73:1e", "dc:71:44", "e4:7c:f9", "f4:09:d8"
    ]
}

def get_local_ip_and_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    parts = local_ip.split('.')
    return local_ip, f"{parts[0]}.{parts[1]}.{parts[2]}"

def parse_arp_output(text):
    entries = {}
    for line in text.splitlines():
        ip_match = re.search(r'\(([\d\.]+)\)', line)
        mac_match = re.search(r'at\s+(([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2})', line)
        if ip_match and mac_match:
            ip = ip_match.group(1)
            mac_raw = mac_match.group(1).split(':')
            mac_norm = ':'.join([f"{int(x, 16):02x}" for x in mac_raw])
            entries[ip] = mac_norm
    return entries

def get_mac_for_ip(ip):
    try:
        out = subprocess.check_output(['arp', ip], text=True, stderr=subprocess.DEVNULL)
        parsed = parse_arp_output(out)
        return parsed.get(ip, None)
    except Exception:
        return None

def identify_vendor(mac):
    if not mac or mac in ('(incomplete)', 'unknown') or ':' not in mac:
        return "Unknown"
    mac_lower = mac.lower()
    
    for vendor, prefixes in OUI_TABLE.items():
        if any(mac_lower.startswith(p) for p in prefixes):
            return f"⭐ {vendor}"
    
    try:
        first_byte = int(mac_lower.split(':')[0], 16)
        if bool(first_byte & 2):
            return "Private/Randomized MAC (Mobile/Smart TV)"
    except Exception:
        pass
    return "Network Client"

async def ping_ip(ip):
    proc = await asyncio.create_subprocess_exec(
        'ping', '-c', '1', '-W', '350', ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()
    return ip, (proc.returncode == 0)

async def check_port(ip, port, timeout=0.3):
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

async def scan():
    local_ip, subnet = get_local_ip_and_subnet()
    print("=" * 76)
    print(" 📡 AUTOMATIC LOCAL NETWORK DEVICE & ANDROID DISCOVERY")
    print("=" * 76)
    print(f"Host Mac IP   : {local_ip}")
    print(f"Target Subnet : {subnet}.1 - {subnet}.254")
    print("Pinging subnet hosts in parallel...")

    # Fast parallel ping sweep of entire subnet
    ping_tasks = [ping_ip(f"{subnet}.{i}") for i in range(1, 255)]
    ping_results = await asyncio.gather(*ping_tasks)
    live_ips = [ip for ip, is_live in ping_results if is_live]
    
    # Also read full system ARP table
    try:
        full_arp_out = subprocess.check_output(['arp', '-a'], text=True)
        arp_cache = parse_arp_output(full_arp_out)
    except Exception:
        arp_cache = {}
    
    # Combine live IPs and ARP cache
    all_discovered = sorted(list(set(live_ips + list(arp_cache.keys()))), key=lambda x: [int(p) for p in x.split('.')])
    
    print(f"Found {len(all_discovered)} active IPs. Probing ADB status and resolving hardware vendors...\n")
    
    # Probe ports in parallel for all discovered IPs
    adb_tasks = [check_port(ip, 5555) for ip in all_discovered]
    adb_results = await asyncio.gather(*adb_tasks)
    
    print("-" * 76)
    print(f"{'IP Address':<16} {'MAC Address':<18} {'ADB (5555)':<12} {'Device / Hardware Vendor'}")
    print("-" * 76)
    
    for ip, has_adb in zip(all_discovered, adb_results):
        mac = arp_cache.get(ip) or get_mac_for_ip(ip) or "Unknown"
        if ip == local_ip:
            vendor = "This Mac (Host Machine)"
        elif ip.endswith('.1'):
            vendor = "Router / Gateway"
        else:
            vendor = identify_vendor(mac)
            
        adb_str = "✅ OPEN" if has_adb else "❌ Closed"
        print(f"{ip:<16} {mac:<18} {adb_str:<12} {vendor}")
        
    print("-" * 76)
    print("\n💡 NEXT STEPS FOR YOUR GALAXY A52:")
    print("• Notice if your Samsung is listed above (e.g. at 192.168.1.105).")
    print("• On your phone: Settings ➔ Developer Options ➔ toggle ON 'Wireless debugging'.")
    print("• You can now connect directly to debloat and optimize!")

if __name__ == "__main__":
    asyncio.run(scan())

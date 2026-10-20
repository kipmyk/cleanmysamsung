"""
Wireless Discovery & Network Inspection Module
Author: Mike Kipruto (https://mike.co.ke/contact)

Passively discovers devices on the local subnet via ping and ARP table lookup,
and checks for accessible ADB debug ports. Does not execute unauthorized connections.
"""

import asyncio
import re
import socket
import subprocess
from typing import Dict, List, Optional, Tuple

OUI_TABLE: Dict[str, List[str]] = {
    "SAMSUNG": [
        "00:07:ab", "00:12:47", "00:15:99", "00:16:32", "00:1d:25", "00:21:19",
        "00:23:d7", "00:24:54", "00:26:37", "08:fc:52", "14:49:e0", "1c:66:aa",
        "28:ba:b5", "30:cd:a7", "34:23:ba", "48:44:f7", "50:01:d9", "5c:a6:e6",
        "78:47:1d", "84:25:db", "94:35:0a", "98:0d:2e", "a8:06:00", "bc:72:b9",
        "c4:73:1e", "dc:71:44", "e4:7c:f9", "f4:09:d8"
    ]
}

def get_local_ip_and_subnet() -> Tuple[str, str]:
    """Determine local network IP and class C subnet prefix."""
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

def parse_arp_output(text: str) -> Dict[str, str]:
    """Parse ARP command output into an IP -> MAC mapping."""
    entries: Dict[str, str] = {}
    for line in text.splitlines():
        ip_match = re.search(r'\(([\d\.]+)\)', line)
        mac_match = re.search(r'at\s+(([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2})', line)
        if ip_match and mac_match:
            ip = ip_match.group(1)
            mac_raw = mac_match.group(1).split(':')
            mac_norm = ':'.join([f"{int(x, 16):02x}" for x in mac_raw])
            entries[ip] = mac_norm
    return entries

def identify_vendor(mac: str) -> str:
    """Identify if a MAC address prefix corresponds to Samsung hardware."""
    if not mac or mac in ('(incomplete)', 'unknown') or ':' not in mac:
        return "Unknown"
    mac_lower = mac.lower()
    for vendor, prefixes in OUI_TABLE.items():
        if any(mac_lower.startswith(p) for p in prefixes):
            return "Samsung Galaxy Device"
    return "Other Network Device"

async def ping_ip(ip: str) -> Tuple[str, bool]:
    """Probe whether an IP responds to ICMP echo."""
    proc = await asyncio.create_subprocess_exec(
        'ping', '-c', '1', '-W', '300', ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()
    return ip, (proc.returncode == 0)

async def check_port(ip: str, port: int, timeout: float = 0.25) -> bool:
    """Check whether a TCP port is accepting connections without sending payloads."""
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

def run_network_discovery() -> None:
    """
    Execute passive discovery of local subnet hosts and check port 5555.
    Does not initiate automated connections or modifications.
    """
    local_ip, subnet = get_local_ip_and_subnet()
    print("=" * 72)
    print(" WIRELESS SAMSUNG GALAXY DEVICE DISCOVERY")
    print("=" * 72)
    print(f"Scanning Subnet: {subnet}.1 - {subnet}.254...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        ping_tasks = [ping_ip(f"{subnet}.{i}") for i in range(1, 255)]
        ping_results = loop.run_until_complete(asyncio.gather(*ping_tasks))
        live_ips = [ip for ip, is_live in ping_results if is_live]

        try:
            arp_out = subprocess.check_output(['arp', '-a'], text=True)
            arp_cache = parse_arp_output(arp_out)
        except Exception:
            arp_cache = {}

        all_ips = sorted(list(set(live_ips + list(arp_cache.keys()))), key=lambda x: [int(p) for p in x.split('.')])
        adb_tasks = [check_port(ip, 5555) for ip in all_ips]
        adb_results = loop.run_until_complete(asyncio.gather(*adb_tasks))
    finally:
        loop.close()

    print("\nDiscovered Devices:")
    print("-" * 72)
    print(f"{'IP Address':<16} {'MAC Address':<18} {'ADB (5555)':<12} {'Vendor'}")
    print("-" * 72)
    for ip, has_adb in zip(all_ips, adb_results):
        mac = arp_cache.get(ip, "Unknown")
        vendor = "This Machine" if ip == local_ip else identify_vendor(mac)
        adb_str = "OPEN" if has_adb else "Closed"
        print(f"{ip:<16} {mac:<18} {adb_str:<12} {vendor}")
    print("-" * 72)
    print("Note: Port 5555 reflects legacy ADB. Android 11+ Wireless Debugging uses dynamic ports.")
    print("Zero automated connections were made. Use 'adb connect <ip>:<port>' manually.\n")

#!/usr/bin/env python3
"""
adbscan.py - find wireless-debugging ADB devices on your network (Termux friendly)

Setup in Termux (install the Termux:API app from F-Droid too):
    apt install -y python curl
    pip install zeroconf
    curl -s https://raw.githubusercontent.com/nohajc/termux-adb/master/install.sh -o install.sh
    grep -n upgrade install.sh       # see if it upgrades anything
    sed -i '/upgrade/d' install.sh   # strip those lines
    bash install.sh                  # installs termux-adb

Usage:
    python adbscan.py            # list devices (IP + port)
    python adbscan.py -t 8       # scan for 8 seconds instead of 5
    python adbscan.py -c         # also try `adb connect` to check if you're paired
    python adbscan.py -p         # also show devices in pairing mode

Notes:
  * Devices with Wireless debugging ON advertise _adb-tls-connect._tcp.
    The port changes every time you toggle it, so rescan when needed.
  * The pairing port (_adb-tls-pairing._tcp) only shows while the
    "Pair device with pairing code" screen is open.
  * mDNS can't tell if THIS phone is paired; -c tests it by connecting.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time

ADB = None  # set in main(): termux-adb preferred, then adb, or --adb override

CONNECT_TYPE = "_adb-tls-connect._tcp.local."
PAIR_TYPE = "_adb-tls-pairing._tcp.local."


def scan_zeroconf(timeout, want_pairing):
    from zeroconf import ServiceBrowser, Zeroconf

    found = {}

    class Listener:
        def _handle(self, zc, type_, name):
            info = zc.get_service_info(type_, name, 3000)
            if not info:
                return
            for ip in info.parsed_addresses():
                if ":" in ip:  # skip IPv6
                    continue
                kind = "pairing" if type_ == PAIR_TYPE else "connect"
                found[(name, kind)] = (ip, info.port)

        def add_service(self, zc, type_, name):
            self._handle(zc, type_, name)

        def update_service(self, zc, type_, name):
            self._handle(zc, type_, name)

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    types = [CONNECT_TYPE] + ([PAIR_TYPE] if want_pairing else [])
    browsers = [ServiceBrowser(zc, t, Listener()) for t in types]
    time.sleep(timeout)
    for b in browsers:
        b.cancel()
    zc.close()

    return [
        (name.split(".")[0], kind, ip, port)
        for (name, kind), (ip, port) in found.items()
    ]


def scan_adb(want_pairing):
    try:
        out = subprocess.run(
            [ADB, "mdns", "services"], capture_output=True, text=True, timeout=15
        ).stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"{ADB} mdns failed: {e}")
        return []
    results = []
    for line in out.splitlines():
        m = re.match(r"(\S+)\s+_adb-tls-(connect|pairing)\._tcp\.?\s+(\d+\.\d+\.\d+\.\d+):(\d+)", line)
        if m:
            name, kind, ip, port = m.groups()
            if kind == "pairing" and not want_pairing:
                continue
            results.append((name, kind, ip, int(port)))
    return results


def try_connect(ip, port):
    try:
        r = subprocess.run(
            [ADB, "connect", f"{ip}:{port}"],
            capture_output=True, text=True, timeout=10,
        )
        text = (r.stdout + r.stderr).lower()
        bad = ("failed", "cannot", "unable", "error", "refused")
        return "connected" in text and not any(w in text for w in bad)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Find wireless ADB devices")
    ap.add_argument("-t", "--timeout", type=int, default=5, help="scan seconds")
    ap.add_argument("-c", "--check", action="store_true", help="try adb connect")
    ap.add_argument("--adb", help="adb binary to use (default: termux-adb, then adb)")
    ap.add_argument("-p", "--pairing", action="store_true", help="include pairing-mode devices")
    args = ap.parse_args()

    global ADB
    ADB = args.adb or shutil.which("termux-adb") or shutil.which("adb")
    have_adb = ADB is not None
    results = []

    try:
        print(f"Scanning {args.timeout}s via mDNS...")
        results = scan_zeroconf(args.timeout, args.pairing)
    except Exception as e:
        why = "zeroconf not installed" if isinstance(e, ImportError) else f"zeroconf failed ({e})"
        if have_adb:
            print(f"{why}, falling back to `{ADB} mdns services`")
            if isinstance(e, ImportError):
                print("(better: pip install zeroconf)")
            print()
            results = scan_adb(args.pairing)
        else:
            sys.exit(f"{why}. Install it with: pip install zeroconf")

    if not results:
        print("No devices found. Make sure Wireless debugging is ON and you're on the same Wi-Fi.")
        return

    print()
    for name, kind, ip, port in sorted(results, key=lambda r: (r[2], r[1])):
        line = f"{ip}:{port}   [{kind}]   {name}"
        if args.check and kind == "connect":
            if have_adb:
                ok = try_connect(ip, port)
                line += "   -> CONNECTED (paired)" if ok else "   -> not connected (not paired?)"
            else:
                line += "   -> adb not installed, can't check"
        print(line)


if __name__ == "__main__":
    main()


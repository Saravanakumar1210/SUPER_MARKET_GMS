"""Start the GMS World Foods site (single server for all users)."""

import argparse
import socket
import subprocess
import sys
import time

import uvicorn

from app.config import get_settings


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already accepting connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        try:
            return sock.connect_ex((host, port)) == 0
        except OSError:
            return False


def _pids_on_port(port: int) -> list[int]:
    """Return PIDs listening on a TCP port (Windows netstat)."""
    pids: list[int] = []
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        needle = f":{port}"
        for line in out.splitlines():
            if "LISTENING" not in line or needle not in line:
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid and pid not in pids:
                    pids.append(pid)
    except (subprocess.SubprocessError, OSError):
        pass
    return pids


def _stop_ports(ports: list[int]) -> None:
    """Stop processes listening on the given ports (Windows)."""
    stopped: set[int] = set()
    for port in ports:
        for pid in _pids_on_port(port):
            if pid in stopped or pid == 0:
                continue
            stopped.add(pid)
            print(f"  Stopping PID {pid} (port {port})…")
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    if stopped:
        time.sleep(1.0)


def _lan_ipv4() -> str | None:
    """Best-effort LAN IPv4 for phone/Wi-Fi testing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return None


def _setup_adb_reverse(port: int) -> bool:
    """Map phone localhost:port → PC localhost:port over USB (scrcpy/adb)."""
    candidates = [
        r"E:\scrcpy-win64-v4.0\adb.exe",
        "adb",
    ]
    for adb in candidates:
        try:
            subprocess.run(
                [adb, "reverse", f"tcp:{port}", f"tcp:{port}"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            continue
    return False


def _run_server() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level="info",
    )


def _report_port_conflict(label: str, port: int, host: str) -> None:
    pids = _pids_on_port(port)
    print(f"ERROR: Port {port} ({label}) is already in use.")
    if pids:
        print(f"       Process ID(s): {', '.join(str(p) for p in pids)}")
    print()
    print("  Fix options:")
    print("    1. Run:  python run.py --stop")
    print("    2. Or manually stop the old server (Ctrl+C in its terminal)")
    print(f"    3. Or change the port in .env (currently {port})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start GMS World Foods site")
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop any process using the server port, then start fresh",
    )
    args = parser.parse_args()

    settings = get_settings()
    host = settings.app_host
    port = settings.app_port
    # 0.0.0.0 is bind-all — browsers should use localhost / LAN IP, not 0.0.0.0
    local_url = f"http://127.0.0.1:{port}"
    ports = [port]
    # Port conflict check: probing 0.0.0.0 is unreliable on Windows
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host

    if args.stop:
        print("Stopping existing server on port", port, "…")
        _stop_ports(ports)

    if _port_in_use(probe_host, port):
        print("=" * 60)
        _report_port_conflict("GMS server", port, host)
        print("=" * 60)
        sys.exit(1)

    lan_ip = _lan_ipv4()
    adb_ok = _setup_adb_reverse(port)

    print("=" * 60)
    print("  GMS World Foods — Site Starting")
    print("=" * 60)
    print(f"  Site:           {local_url}")
    print(f"  API docs:       {local_url}/docs")
    print(f"  Bind address:   {host}:{port}")
    if lan_ip:
        print(f"  Phone (Wi-Fi):  http://{lan_ip}:{port}")
        print("                  (same Wi-Fi as this PC)")
    if adb_ok:
        print(f"  Phone (USB):    {local_url}")
        print("                  (adb reverse active — open that URL on the phone)")
    else:
        print("  Phone (USB):    connect phone + USB debugging, then:")
        print(f'                  adb reverse tcp:{port} tcp:{port}')
        print(f"                  then open {local_url} in Chrome on the phone")
    print("=" * 60)
    print("  Sign in once — customers shop; admins also get Manage store.")
    print("  Open the URL as soon as you see: Application startup complete")
    print("  (page HTML loads immediately; product data may follow a second later)")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Run uvicorn in this process (not a child Process) so Windows does not pay
    # a second full Python import before the port opens.
    try:
        _run_server()
    except KeyboardInterrupt:
        print("\nShutting down…")
        sys.exit(0)

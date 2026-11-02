#!/usr/bin/env python3
"""Find the MTProto endpoint of the custom server and read its RSA fingerprints.

The client can only log in if it reaches a *raw* MTProto port (abridged or
intermediate transport, no TLS in front) and if the RSA public key compiled
into the client matches one of the fingerprints the server reports.

This script tries every given port with both transports, and prints which
public key fingerprints the server offers.

Usage:
    python probe_mtproto.py --host 84.21.173.237 --ports 443,80,5222,8443
    python probe_mtproto.py --host 84.21.173.237 --ports 1-20000 --keys E:\\keys
"""
import argparse
import glob
import os
import socket
import struct
import sys
import time
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from key_fingerprint import fingerprint, modulus_and_exponent, read_pem  # noqa: E402

REQ_PQ_MULTI = 0xBE7E8EF1
RES_PQ = 0x05162463


def new_msg_id():
    now = time.time()
    return (int(now) << 32) | (int((now % 1) * (2 ** 32)) & 0xFFFFFFFC) | 4


def read_exact(sock, count):
    buf = b""
    while len(buf) < count:
        chunk = sock.recv(count - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def read_abridged_length(sock):
    first = read_exact(sock, 1)[0]
    if first < 0x7F:
        return first
    if first == 0x7F:
        return int.from_bytes(read_exact(sock, 3), "little")
    return int.from_bytes(bytes([first]) + read_exact(sock, 3), "little")


def read_intermediate_length(sock):
    return struct.unpack("<i", read_exact(sock, 4))[0]


def parse_res_pq(payload):
    ctor = struct.unpack("<I", payload[:4])[0]
    if ctor != RES_PQ:
        return None
    offset = 4
    nonce = payload[offset:offset + 16]
    offset += 16
    server_nonce = payload[offset:offset + 16]
    offset += 16
    pq_len = payload[offset]
    offset += 1 + pq_len
    count = struct.unpack("<I", payload[offset:offset + 4])[0]
    offset += 4
    fingerprints = [
        struct.unpack("<q", payload[offset + i * 8:offset + i * 8 + 8])[0]
        for i in range(count)
    ]
    return nonce, server_nonce, fingerprints


def try_transport(host, port, transport, timeout):
    """Returns ('ok', fingerprints) / ('not-mtproto', None) / ('error', text)."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except Exception as error:  # noqa: BLE001
        return "closed", str(error)

    try:
        sock.settimeout(timeout)
        body = struct.pack("<I", REQ_PQ_MULTI) + os.urandom(16)
        packet = struct.pack("<qqi", 0, new_msg_id(), len(body)) + body

        if transport == "abridged":
            sock.sendall(b"\xef" + packet)
            length = read_abridged_length(sock)
        else:
            sock.sendall(b"\xee\xee\xee\xee" + packet)
            length = read_intermediate_length(sock)

        data = read_exact(sock, length)
        parsed = parse_res_pq(data[20:20 + struct.unpack("<i", data[8:12])[0]])
        if parsed is None:
            return "not-mtproto", f"unexpected constructor {data[20:24].hex()}"
        return "ok", parsed
    except socket.timeout:
        return "silent", "no reply (TLS/HTTP server or filtered port)"
    except Exception as error:  # noqa: BLE001
        return "error", str(error)
    finally:
        sock.close()


def parse_ports(spec):
    ports = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            low, high = part.split("-")
            ports.extend(range(int(low), int(high) + 1))
        elif part:
            ports.append(int(part))
    return ports


def load_keys(directory):
    keys = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.pem"))):
        try:
            keys[os.path.basename(path)] = fingerprint(*modulus_and_exponent(read_pem(path)))
        except Exception:  # noqa: BLE001
            continue
    return keys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--ports", default="443,80,5222,8443")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--keys", help="folder with .pem keys to match fingerprints against")
    parser.add_argument("--scan", action="store_true", help="only look for open TCP ports")
    args = parser.parse_args()

    ports = parse_ports(args.ports)
    keys = load_keys(args.keys) if args.keys else {}

    if args.scan:
        def is_open(port):
            sock = socket.socket()
            sock.settimeout(0.5)
            try:
                sock.connect((args.host, port))
                return port
            except Exception:  # noqa: BLE001
                return None
            finally:
                sock.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=400) as pool:
            open_ports = [p for p in pool.map(is_open, ports) if p]
        print("open TCP ports:", open_ports)
        return 0

    found_any = False
    for port in ports:
        for transport in ("abridged", "intermediate"):
            status, payload = try_transport(args.host, port, transport, args.timeout)
            if status == "ok":
                found_any = True
                nonce, server_nonce, fingerprints = payload
                print(f"[MTProto OK] {args.host}:{port} ({transport} transport)")
                print(f"  server nonce: {server_nonce.hex()}")
                for fp in fingerprints:
                    unsigned = fp & 0xFFFFFFFFFFFFFFFF
                    match = [name for name, value in keys.items() if value == unsigned]
                    suffix = f"  <== matches {match[0]}" if match else ""
                    print(f"  fingerprint : 0x{unsigned:016x}{suffix}")
            else:
                print(f"[{status:11s}] {args.host}:{port} ({transport}) - {payload}")

    if not found_any:
        print(
            "\nNo raw MTProto listener found on these ports.\n"
            "The client cannot connect: raw MTProto must be reachable on some TCP\n"
            "port (no TLS/HTTP in front), or the server must expose an MTProto\n"
            "proxy / different port. Check the server config."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

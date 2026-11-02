#!/usr/bin/env python3
"""Check that the custom-server patch in the source tree is consistent.

Verifies that:
  1. kBuiltInDcs points at the expected IP/port (no Telegram DCs left);
  2. kPublicRSAKeys / kTestPublicRSAKeys parse as RSA keys;
  3. both keys match the private key of the server (fingerprint comparison).

Usage:
    python verify_patch.py --source E:\\tdesktop --key E:\\keys\\server_rsa.key
"""
import argparse
import base64
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from key_fingerprint import fingerprint, modulus_and_exponent, read_pem  # noqa: E402

DC_FILE = os.path.join("Telegram", "SourceFiles", "mtproto", "mtproto_dc_options.cpp")


def extract_literal(source, name):
    match = re.search(name + r'\[\]\s*=\s*\{\s*"(.*?)"\s*\};', source, re.S)
    if not match:
        raise SystemExit(f"could not find {name} in source")
    return match.group(1).replace("\\n\\\n", "\n").replace("\\n", "\n")


def pem_to_ne(pem_text):
    body = "".join(line for line in pem_text.splitlines() if "-----" not in line)
    pem = (
        "-----BEGIN RSA PUBLIC KEY-----\n"
        + base64.b64encode(base64.b64decode(body)).decode()
        + "\n-----END RSA PUBLIC KEY-----\n"
    )
    return modulus_and_exponent(pem)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".", help="path to the tdesktop checkout")
    parser.add_argument("--key", help="server private key (or its public .pem) to compare against")
    parser.add_argument("--ip", help="expected server IP")
    parser.add_argument("--port", type=int, default=None, help="expected server port")
    args = parser.parse_args()

    path = os.path.join(args.source, DC_FILE)
    with open(path, encoding="utf-8") as f:
        source = f.read()

    ok = True

    ip_match = re.search(r'kCustomServerIp\s*=\s*"([^"]+)"', source)
    port_match = re.search(r"kCustomServerPort\s*=\s*(\d+)", source)
    if not ip_match or not port_match:
        print("FAIL: kCustomServerIp / kCustomServerPort not found")
        return 1
    ip, port = ip_match.group(1), int(port_match.group(1))
    print(f"server endpoint : {ip}:{port}")
    if args.ip and args.ip != ip:
        print(f"FAIL: expected IP {args.ip}, patch has {ip}")
        ok = False
    if args.port and args.port != port:
        print(f"FAIL: expected port {args.port}, patch has {port}")
        ok = False

    leftover = re.findall(r"149\.154\.\d+\.\d+", source)
    if leftover:
        print(f"FAIL: real Telegram DC addresses still present: {leftover}")
        ok = False
    else:
        print("telegram DCs    : none left in dc options")

    v6 = re.findall(r"2001:0b28|2001:067c", source)
    print(f"ipv6 endpoints  : {'still present' if v6 else 'removed'}")

    expected = None
    if args.key:
        expected = modulus_and_exponent(read_pem(args.key))
        print(f"server key fp   : 0x{fingerprint(*expected):016x}")

    for name in ("kPublicRSAKeys", "kTestPublicRSAKeys"):
        literal = extract_literal(source, name)
        n, e = pem_to_ne(literal)
        fp = fingerprint(n, e)
        status = "ok"
        if expected and (n, e) != expected:
            status = "MISMATCH with server key"
            ok = False
        print(f"{name:22s}: bits={n.bit_length()} fp=0x{fp:016x} -> {status}")

    print("\nRESULT:", "PATCH OK" if ok else "PATCH HAS PROBLEMS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

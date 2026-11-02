#!/usr/bin/env python3
"""Print the Telegram Desktop fingerprint of an RSA public key.

Telegram Desktop computes the key fingerprint as
    uint64 = sha1(tl_bytes(n) || tl_bytes(e))[12:20]  (little endian)
where tl_bytes() is the TL "bytes" serialization: int32 length, payload,
zero padding to a 4 byte boundary.

Usage:
    python key_fingerprint.py E:\\keys\\server_rsa_public_pkcs1.pem
    python key_fingerprint.py E:\\keys\\server_rsa.key --private
"""
import base64
import hashlib
import struct
import sys


def read_pem(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def der_blob(pem):
    body = "".join(
        line for line in pem.splitlines()
        if "-----" not in line and line.strip()
    )
    return base64.b64decode(body)


def tlv(data, i=0):
    tag = data[i]
    i += 1
    length = data[i]
    i += 1
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[i:i + count], "big")
        i += count
    return tag, data[i:i + length], i + length


def sequence_items(value):
    items, offset = [], 0
    while offset < len(value):
        tag, chunk, offset = tlv(value, offset)
        items.append((tag, chunk))
    return items


def modulus_and_exponent(pem):
    """Works for PKCS#1 public, SPKI public and PKCS#1/PKCS#8 private keys."""
    _, body, _ = tlv(der_blob(pem), 0)
    items = sequence_items(body)

    # PKCS#1 RSAPublicKey: SEQUENCE { INTEGER n, INTEGER e }
    if len(items) == 2 and items[0][0] == 0x02:
        return int.from_bytes(items[0][1], "big"), int.from_bytes(items[1][1], "big")

    # SubjectPublicKeyInfo: SEQUENCE { AlgorithmIdentifier, BIT STRING }
    if len(items) == 2 and items[1][0] == 0x03:
        _, inner, _ = tlv(items[1][1][1:], 0)
        nested = sequence_items(inner)
        return int.from_bytes(nested[0][1], "big"), int.from_bytes(nested[1][1], "big")

    # PKCS#8 PrivateKeyInfo: SEQUENCE { INTEGER 0, AlgorithmIdentifier, OCTET STRING }
    if len(items) == 3 and items[2][0] == 0x04:
        _, inner, _ = tlv(items[2][1], 0)
        nested = sequence_items(inner)
        return int.from_bytes(nested[1][1], "big"), int.from_bytes(nested[2][1], "big")

    # PKCS#1 RSAPrivateKey: SEQUENCE { version, n, e, d, ... }
    if len(items) >= 9:
        return int.from_bytes(items[1][1], "big"), int.from_bytes(items[2][1], "big")

    raise ValueError("unknown key structure")


def tl_bytes(payload):
    return (
        struct.pack("<i", len(payload))
        + payload
        + b"\x00" * ((-len(payload)) % 4)
    )


def fingerprint(n, e):
    n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
    e_bytes = e.to_bytes((e.bit_length() + 7) // 8, "big")
    digest = hashlib.sha1(tl_bytes(n_bytes) + tl_bytes(e_bytes)).digest()
    return struct.unpack("<Q", digest[12:20])[0]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for path in sys.argv[1:]:
        if path.startswith("--"):
            continue
        n, e = modulus_and_exponent(read_pem(path))
        print(
            f"{path}\n"
            f"  bits       = {n.bit_length()}\n"
            f"  exponent   = {e}\n"
            f"  fingerprint= 0x{fingerprint(n, e):016x}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

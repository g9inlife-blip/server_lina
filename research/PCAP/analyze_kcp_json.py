#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decrypt/reassemble the game's 64-bit-KCP application messages from Wireshark JSON."""

from __future__ import annotations

import argparse
import gzip
import json
import struct
from collections import defaultdict
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError:
    raise SystemExit("PyCryptodome required: pip install pycryptodome")

KEY = bytes.fromhex("44f5f445808615fe1b2e224c5e05e718")
KCP_HDR = 28
KCP_CMD = 0x51
ENC_FLAGS = {0x80, 0x84, 0xC0, 0xC4}


def hx(s):
    return bytes.fromhex(s.replace(":", ""))


def varint(data, off):
    v = 0
    shift = 0
    while off < len(data):
        b = data[off]
        off += 1
        v |= (b & 0x7F) << shift
        if not b & 0x80:
            return v, off
        shift += 7
        if shift > 63:
            break
    raise ValueError("bad varint")


def protobuf_tree(data, depth=0, max_depth=6):
    out = []
    off = 0
    while off < len(data):
        start = off
        tag, off = varint(data, off)
        field, wire = tag >> 3, tag & 7
        if field <= 0:
            raise ValueError(f"invalid protobuf field at {start}: {tag:#x}")
        item = {"field": field, "wire": wire, "offset": start}

        if wire == 0:
            item["value"], off = varint(data, off)
        elif wire == 1:
            if off + 8 > len(data):
                raise ValueError("truncated fixed64")
            item["value_hex"] = data[off:off + 8].hex()
            off += 8
        elif wire == 2:
            n, off = varint(data, off)
            if off + n > len(data):
                raise ValueError("truncated length-delimited")
            b = data[off:off + n]
            off += n
            item["length"] = n
            item["prefix_hex"] = b[:96].hex()
            if n and depth < max_depth:
                try:
                    nested = protobuf_tree(b, depth + 1, max_depth)
                    if nested:
                        item["nested"] = nested
                except Exception:
                    pass
            if n and b[:2] == b"\x1f\x8b":
                try:
                    dec = gzip.decompress(b)
                    item["gzip_uncompressed_bytes"] = len(dec)
                    if depth < max_depth:
                        item["gzip_nested"] = protobuf_tree(dec, depth + 1, max_depth)
                except Exception:
                    pass
        elif wire == 5:
            if off + 4 > len(data):
                raise ValueError("truncated fixed32")
            item["value_hex"] = data[off:off + 4].hex()
            off += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")

        out.append(item)
    return out


def packet_layers(obj):
    return obj.get("_source", {}).get("layers", {})


def get_hex(layers, proto):
    p = layers.get(proto, {})
    for k, v in p.items():
        if k.endswith(".payload") and isinstance(v, (str, list)):
            return v[0] if isinstance(v, list) else v
    return None


def ip4(layers, key):
    return layers.get("ip", {}).get(key)


def port(layers, proto, key):
    v = layers.get(proto, {}).get(key)
    return int(v, 0) if isinstance(v, str) else v


def decrypt_app(data):
    if len(data) < 17 or data[0] not in ENC_FLAGS:
        return None

    flags = data[0]
    iv = data[1:17]
    ct = data[17:]
    if len(ct) % 16:
        raise ValueError(f"ciphertext not block aligned: {len(ct)}")

    pt = AES.new(KEY, AES.MODE_CBC, iv).decrypt(ct)
    pad = pt[-1]
    if not 1 <= pad <= 16 or not pt.endswith(bytes([pad]) * pad):
        raise ValueError("PKCS7 padding mismatch")
    return flags, iv, pt[:-pad]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    raw = json.loads(args.json.read_text(encoding="utf-8"))
    packets = raw if isinstance(raw, list) else raw.get("packets", [])
    out = args.out or args.json.with_name(args.json.stem + "_kcp")
    out.mkdir(parents=True, exist_ok=True)
    plain_dir = out / "plaintext"
    plain_dir.mkdir(exist_ok=True)

    segments = []
    for p in packets:
        l = packet_layers(p)
        payload = get_hex(l, "udp")
        if not payload:
            continue
        b = hx(payload)
        if len(b) < KCP_HDR:
            continue
        conv, cmd, frg, wnd, ts, sn, una, n = struct.unpack_from("<QBBHIIII", b, 0)
        if cmd != KCP_CMD or n > len(b) - KCP_HDR:
            continue
        segments.append({
            "packet": int(l.get("frame", {}).get("frame.number", 0)),
            "src": ip4(l, "ip.src"),
            "sport": port(l, "udp", "udp.srcport"),
            "dst": ip4(l, "ip.dst"),
            "dport": port(l, "udp", "udp.dstport"),
            "conv": conv, "frg": frg, "sn": sn, "una": una,
            "app": b[KCP_HDR:KCP_HDR + n],
        })

    groups = defaultdict(list)
    for s in segments:
        key = (s["conv"], s["src"], s["sport"], s["dst"], s["dport"])
        groups[key].append(s)

    results = []

    for _, ss in groups.items():
        ss.sort(key=lambda x: x["sn"])
        cur = []
        last_sn = None

        def flush():
            nonlocal cur, last_sn
            if not cur:
                return
            cur.sort(key=lambda x: x["sn"])
            data = b"".join(x["app"] for x in cur)
            first = cur[0]
            rec = {
                "packets": [x["packet"] for x in cur],
                "conv": first["conv"],
                "src": first["src"], "sport": first["sport"],
                "dst": first["dst"], "dport": first["dport"],
                "bytes": len(data),
                "hex_prefix": data[:96].hex(),
            }

            try:
                dec = decrypt_app(data)
            except Exception as e:
                rec["decrypt"] = "failed"
                rec["error"] = str(e)
                dec = None

            if dec:
                flags, iv, pt = dec
                rec.update({
                    "flags": flags,
                    "iv": iv.hex(),
                    "ciphertext_bytes": len(data) - 17,
                    "decrypt": "ok",
                    "plaintext_bytes": len(pt),
                    "plaintext_prefix": pt[:128].hex(),
                })

                name = f"{min(rec['packets']):06d}_{'c2s' if first['src'] == '10.215.173.1' else 's2c'}.bin"
                (plain_dir / name).write_bytes(pt)
                rec["plaintext_file"] = str(Path("plaintext") / name)

                try:
                    rec["protobuf"] = protobuf_tree(pt)
                except Exception as e:
                    rec["protobuf_error"] = str(e)

                if pt[:2] == b"\x1f\x8b":
                    try:
                        gz = gzip.decompress(pt)
                        rec["gzip_bytes"] = len(gz)
                        rec["gzip_prefix"] = gz[:128].hex()
                        rec["gzip_protobuf"] = protobuf_tree(gz)
                    except Exception as e:
                        rec["gzip_error"] = str(e)

            results.append(rec)
            cur = []
            last_sn = None

        for s in ss:
            if not cur:
                cur = [s]
                last_sn = s["sn"]
                continue

            contiguous = s["sn"] == last_sn + 1
            if not contiguous or (cur[-1]["frg"] == 0):
                flush()
                cur = [s]
            else:
                cur.append(s)
            last_sn = s["sn"]

            if s["frg"] == 0:
                flush()

        flush()

    results.sort(key=lambda r: min(r["packets"]))
    (out / "messages.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (out / "messages.txt").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                f"packets={r['packets']} {r['src']}:{r['sport']}->"
                f"{r['dst']}:{r['dport']} bytes={r['bytes']} "
                f"flags={r.get('flags')} decrypt={r.get('decrypt')}\n"
            )
            if r.get("decrypt") == "ok":
                f.write(
                    f"  plaintext={r['plaintext_bytes']} "
                    f"prefix={r['plaintext_prefix']}\n"
                )
            if "protobuf" in r:
                f.write("  protobuf=" + json.dumps(
                    r["protobuf"], ensure_ascii=False, separators=(",", ":")
                ) + "\n")

    print(f"[+] KCP segments={len(segments)} messages={len(results)} out={out}")


if __name__ == "__main__":
    main()

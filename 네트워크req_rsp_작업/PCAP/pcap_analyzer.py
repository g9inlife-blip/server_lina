#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCAP analyzer for the arme network reverse-engineering work.

Goals
-----
- Read classic PCAP files without requiring Wireshark/tshark.
- Summarize IPv4/TCP/UDP traffic and 4-tuple flows.
- Reassemble TCP application payloads from sequence numbers.
- Detect the known TCPTube DH handshake.
- Detect the known KCPTube handshake and KCP data packets.
- Extract post-handshake encrypted payload candidates:
    [optional frame/header][16-byte IV][ciphertext]
- Write deterministic JSON/NDJSON/text reports for later comparison.

This tool intentionally does NOT attempt to recover DH private values or decrypt
traffic from the PCAP alone. The next-stage runtime hook should capture the
session key at DH64.Secret() or RijndaelManaged.CreateDecryptor().
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional


ETH_IPV4 = 0x0800
IPPROTO_TCP = 6
IPPROTO_UDP = 17


@dataclass
class Packet:
    index: int
    ts: float
    link_type: int
    src: str
    dst: str
    sport: Optional[int]
    dport: Optional[int]
    proto: str
    payload: bytes
    seq: Optional[int] = None
    ack: Optional[int] = None


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def hexx(data: bytes, limit: int = 64) -> str:
    if len(data) <= limit:
        return data.hex()
    return data[:limit].hex() + f"...(+{len(data) - limit} bytes)"


def parse_pcap(path: Path) -> tuple[int, list[Packet]]:
    raw = path.read_bytes()
    if len(raw) < 24:
        raise ValueError("PCAP header is truncated")

    magic = raw[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian, nano = "<", False
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian, nano = ">", False
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian, nano = "<", True
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian, nano = ">", True
    else:
        raise ValueError(f"unsupported PCAP magic: {magic.hex()}")

    _major, _minor, _tz, _sig, _snap, network = struct.unpack_from(
        endian + "HHiiii", raw, 4
    )
    offset = 24
    packets: list[Packet] = []
    idx = 0

    while offset + 16 <= len(raw):
        ts_sec, ts_frac, incl_len, _orig_len = struct.unpack_from(
            endian + "IIII", raw, offset
        )
        offset += 16
        if offset + incl_len > len(raw):
            break
        frame = raw[offset:offset + incl_len]
        offset += incl_len
        idx += 1
        ts = ts_sec + (ts_frac / (1_000_000_000 if nano else 1_000_000))

        parsed = parse_frame(idx, ts, network, frame)
        if parsed:
            packets.append(parsed)

    return network, packets


def parse_frame(index: int, ts: float, link_type: int, frame: bytes) -> Optional[Packet]:
    # PCAPdroid captures are normally Ethernet (DLT_EN10MB) or raw IP.
    if link_type == 1:  # Ethernet
        if len(frame) < 14:
            return None
        eth_type = struct.unpack_from("!H", frame, 12)[0]
        if eth_type != ETH_IPV4:
            return None
        ip = frame[14:]
    elif link_type in (101, 228):  # raw IPv4 / Linux cooked variants used by some captures
        ip = frame
    else:
        # Try Ethernet as a pragmatic fallback.
        if len(frame) < 14:
            return None
        if struct.unpack_from("!H", frame, 12)[0] != ETH_IPV4:
            return None
        ip = frame[14:]

    if len(ip) < 20 or (ip[0] >> 4) != 4:
        return None
    ihl = (ip[0] & 0x0F) * 4
    total_len = struct.unpack_from("!H", ip, 2)[0]
    proto = ip[9]
    src = ".".join(map(str, ip[12:16]))
    dst = ".".join(map(str, ip[16:20]))
    if total_len < ihl or len(ip) < total_len:
        return None
    transport = ip[ihl:total_len]

    if proto == IPPROTO_TCP:
        if len(transport) < 20:
            return None
        sport, dport, seq, ack, off_flags = struct.unpack_from("!HHIIH", transport, 0)
        data_off = ((off_flags >> 12) & 0xF) * 4
        return Packet(index, ts, link_type, src, dst, sport, dport, "TCP",
                      transport[data_off:], seq, ack)

    if proto == IPPROTO_UDP:
        if len(transport) < 8:
            return None
        sport, dport, length = struct.unpack_from("!HHH", transport, 0)
        return Packet(index, ts, link_type, src, dst, sport, dport, "UDP",
                      transport[8:length], None, None)

    return None


def stream_key(p: Packet) -> tuple:
    a = (p.src, p.sport)
    b = (p.dst, p.dport)
    return (a, b) if a <= b else (b, a)


def endpoint_key(p: Packet) -> str:
    return f"{p.src}:{p.sport}->{p.dst}:{p.dport}"


def tcp_reassemble(packets: Iterable[Packet]) -> dict:
    streams = defaultdict(list)
    for p in packets:
        if p.proto == "TCP" and p.payload:
            streams[stream_key(p)].append(p)

    result = {}
    for key, ps in streams.items():
        directions = defaultdict(list)
        for p in ps:
            directions[(p.src, p.sport, p.dst, p.dport)].append(p)

        out = []
        for direction, dps in directions.items():
            dps.sort(key=lambda x: (x.seq or 0, x.index))
            chunks = []
            next_seq = None
            gaps = []
            for p in dps:
                if next_seq is None:
                    next_seq = p.seq
                if p.seq > next_seq:
                    gaps.append({"at_packet": p.index, "gap": p.seq - next_seq})
                    chunks.append(b"\x00" * (p.seq - next_seq))
                if p.seq < next_seq:
                    overlap = next_seq - p.seq
                    if overlap >= len(p.payload):
                        continue
                    chunks.append(p.payload[overlap:])
                    next_seq += len(p.payload) - overlap
                else:
                    chunks.append(p.payload)
                    next_seq = p.seq + len(p.payload)
            data = b"".join(chunks)
            out.append({
                "direction": endpoint_text(direction),
                "packets": len(dps),
                "bytes": len(data),
                "gaps": gaps,
                "hex_prefix": hexx(data),
                "data": data,
            })
        result[str(key)] = out
    return result


def endpoint_text(e):
    return f"{e[0]}:{e[1]}->{e[2]}:{e[3]}"


def try_tcptube_handshake(payload: bytes) -> Optional[dict]:
    if len(payload) < 29:
        return None
    # Client handshake: 8 zero bytes, uint32 length, marker 1,
    # public1, public2, param4.
    if payload[:8] != b"\x00" * 8 or payload[12] != 1:
        return None
    declared = struct.unpack_from("<I", payload, 8)[0]
    public1 = payload[13:21]
    public2 = payload[21:29]
    param4 = payload[29:]
    if declared != len(param4) + 17:
        return None
    return {
        "type": "TCPTube.Handshake1",
        "declared_length": declared,
        "public1_le": "0x" + public1[::-1].hex(),
        "public2_le": "0x" + public2[::-1].hex(),
        "public1_raw": public1.hex(),
        "public2_raw": public2.hex(),
        "param4_bytes": len(param4),
        "param4_base64": is_base64_ascii(param4),
        "param4_hex_prefix": hexx(param4),
    }


def try_tcptube_server(payload: bytes) -> Optional[dict]:
    if len(payload) < 29:
        return None
    if payload[:8] != b"\x00" * 8 or payload[12] != 1:
        return None
    declared = struct.unpack_from("<I", payload, 8)[0]
    if declared != 0x19 or len(payload) != 37:
        return None
    conv = payload[13:21]
    public1 = payload[21:29]
    public2 = payload[29:37]
    return {
        "type": "TCPTube.Handshake2",
        "declared_length": declared,
        "conv_id_le": "0x" + conv[::-1].hex(),
        "public1_le": "0x" + public1[::-1].hex(),
        "public2_le": "0x" + public2[::-1].hex(),
    }


def try_kcptube_handshake(payload: bytes) -> Optional[dict]:
    if len(payload) < 24:
        return None
    if payload[:8] != b"\x00" * 8:
        return None
    return {
        "type": "KCPTube.Handshake1 candidate",
        "public1_le": "0x" + payload[8:16][::-1].hex(),
        "public2_le": "0x" + payload[16:24][::-1].hex(),
        "param4_bytes": len(payload) - 24,
        "param4_base64": is_base64_ascii(payload[24:]),
        "payload_hex_prefix": hexx(payload),
    }


def is_base64_ascii(data: bytes) -> bool:
    if not data or len(data) % 4:
        return False
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n"
    return all(c in allowed for c in data)


def decode_base64_if_possible(data: bytes) -> Optional[dict]:
    if not is_base64_ascii(data):
        return None
    try:
        compact = b"".join(data.split())
        decoded = base64.b64decode(compact, validate=True)
        return {"decoded_bytes": len(decoded), "entropy": entropy(decoded), "hex_prefix": hexx(decoded)}
    except (ValueError, binascii.Error):
        return None


def parse_kcp_header(payload: bytes) -> Optional[dict]:
    # KCP header is 24 bytes:
    # conv(4), cmd(1), frg(1), wnd(2), ts(4), sn(4), una(4), len(4)
    if len(payload) < 24:
        return None
    conv, cmd, frg, wnd, ts, sn, una, length = struct.unpack_from("<IBBHIIII", payload, 0)
    if 24 + length > len(payload):
        return None
    return {
        "conv": f"0x{conv:08x}",
        "cmd": f"0x{cmd:02x}",
        "frg": frg,
        "wnd": wnd,
        "ts": ts,
        "sn": sn,
        "una": una,
        "length": length,
        "application_bytes": len(payload) - 24,
        "application_hex_prefix": hexx(payload[24:]),
    }


def analyze_encrypted_candidate(data: bytes) -> Optional[dict]:
    # Known game payload form is [16-byte IV][ciphertext], optionally preceded
    # by a one-byte application flag in KCP data.
    candidates = []
    for prefix in (0, 1):
        if len(data) <= prefix + 16:
            continue
        body = data[prefix:]
        cipher_len = len(body) - 16
        if cipher_len > 0 and cipher_len % 16 == 0:
            candidates.append({
                "prefix_bytes": prefix,
                "iv": body[:16].hex(),
                "ciphertext_bytes": cipher_len,
                "ciphertext_blocks": cipher_len // 16,
                "ciphertext_entropy": entropy(body[16:]),
                "layout": f"[{prefix}-byte prefix][16-byte IV][ciphertext]",
            })
    return {"candidates": candidates, "payload_bytes": len(data)} if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    out = args.out or args.pcap.with_name(args.pcap.stem + "_analysis")
    out.mkdir(parents=True, exist_ok=True)

    link_type, packets = parse_pcap(args.pcap)

    proto_counts = Counter(p.proto for p in packets)
    flow_counts = Counter(
        (p.proto, p.src, p.sport, p.dst, p.dport) for p in packets
    )

    report = {
        "pcap": str(args.pcap),
        "link_type": link_type,
        "packet_count": len(packets),
        "protocol_counts": dict(proto_counts),
        "flows": [
            {"proto": k[0], "src": k[1], "sport": k[2], "dst": k[3], "dport": k[4], "packets": v}
            for k, v in flow_counts.items()
        ],
        "tcptube_candidates": [],
        "kcptube_candidates": [],
        "encrypted_candidates": [],
    }

    # Analyze each TCP payload independently first, then reassembled streams.
    for p in packets:
        if p.proto == "TCP" and p.payload:
            h1 = try_tcptube_handshake(p.payload)
            h2 = try_tcptube_server(p.payload)
            if h1 or h2:
                report["tcptube_candidates"].append({
                    "packet": p.index,
                    "timestamp": p.ts,
                    "endpoint": endpoint_key(p),
                    "bytes": len(p.payload),
                    "analysis": h1 or h2,
                })

        if p.proto == "UDP" and p.payload:
            k = parse_kcp_header(p.payload)
            if k:
                app = p.payload[24:24 + k["length"]]
                if app:
                    enc = analyze_encrypted_candidate(app)
                    report["encrypted_candidates"].append({
                        "packet": p.index,
                        "timestamp": p.ts,
                        "endpoint": endpoint_key(p),
                        "kcp": k,
                        "encrypted_candidate": enc,
                    })
                    if app[:8] == b"\x00" * 8 and len(app) >= 24:
                        report["kcptube_candidates"].append({
                            "packet": p.index,
                            "timestamp": p.ts,
                            "endpoint": endpoint_key(p),
                            "bytes": len(app),
                            "analysis": try_kcptube_handshake(app),
                        })

    streams = tcp_reassemble(packets)
    stream_json = []
    for key, dirs in streams.items():
        for d in dirs:
            data = d.pop("data")
            stream_json.append({**d, "tcp_stream": str(key), "decoded_base64": decode_base64_if_possible(data)})
    report["tcp_reassembled"] = stream_json

    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out / "packets.ndjson").open("w", encoding="utf-8") as f:
        for p in packets:
            f.write(json.dumps({
                "packet": p.index, "ts": p.ts, "proto": p.proto,
                "src": p.src, "sport": p.sport, "dst": p.dst, "dport": p.dport,
                "bytes": len(p.payload), "hex_prefix": hexx(p.payload),
            }, ensure_ascii=False) + "\n")

    lines = [
        f"PCAP: {args.pcap}",
        f"LinkType: {link_type}",
        f"Packets: {len(packets)}",
        f"Protocols: {dict(proto_counts)}",
        "",
        "Flows:",
    ]
    for item in report["flows"]:
        lines.append(
            f"  {item['proto']} {item['src']}:{item['sport']} -> "
            f"{item['dst']}:{item['dport']} : {item['packets']} packets"
        )
    lines += ["", "TCPTube candidates:"]
    for x in report["tcptube_candidates"]:
        lines.append(f"  packet {x['packet']}: {json.dumps(x['analysis'], ensure_ascii=False)}")
    lines += ["", "KCP encrypted candidates:"]
    for x in report["encrypted_candidates"]:
        if x["encrypted_candidate"]:
            lines.append(
                f"  packet {x['packet']}: {json.dumps(x['encrypted_candidate'], ensure_ascii=False)}"
            )
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[+] packets={len(packets)} protocols={dict(proto_counts)}")
    print(f"[+] output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

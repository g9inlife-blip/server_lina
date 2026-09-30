#!/usr/bin/env python3
"""
pcap_dh_validator.py

TCP DH64 handshake 구조를 PCAP에서 1차 검증한다.

현재 버전:
- 표준 라이브러리만 사용
- classic PCAP(libpcap) 파일 직접 읽기
- Ethernet / RAW IPv4 / Linux SLL / Linux SLL2 + IPv4 + TCP payload 추출
- 기존에 확인된 server handshake 값 검색
- client handshake 후보 검색
- private key가 제공되면 public/secret/session key 계산

사용 예:
  python pcap_dh_validator.py capture.pcap
  python pcap_dh_validator.py capture.pcap --server-public1 ca4d30dba4429f27 --server-public2 7164b27b3d91d781
  python pcap_dh_validator.py capture.pcap --private1 0x... --private2 0x...

주의:
- 첫 버전은 TCP stream reassembly를 하지 않는다.
- 따라서 handshake가 여러 TCP segment로 분할된 경우 후보를 놓칠 수 있다.
- 실제 PCAP 구조 확인 후 reassembly를 추가한다.
"""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


P = 0xFFFFFFFFFFFFFFC5
G = 5

DEFAULT_SERVER_PUBLIC1 = 0xCA4D30DBA4429F27
DEFAULT_SERVER_PUBLIC2 = 0x7164B27B3D91D781
DEFAULT_CONV_ID = 0x632


@dataclass
class Packet:
    index: int
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    seq: int
    ack: int
    flags: int
    payload: bytes


def u16be(b: bytes) -> int:
    return struct.unpack(">H", b)[0]


def u32be(b: bytes) -> int:
    return struct.unpack(">I", b)[0]


def u64le(b: bytes) -> int:
    return int.from_bytes(b, "little")


def ip_text(b: bytes) -> str:
    return ".".join(str(x) for x in b)


def read_pcap(path: Path):
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError("파일이 classic PCAP 헤더보다 짧습니다.")

    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian = ">"
    else:
        raise ValueError(
            "classic PCAP이 아닙니다. pcapng이면 tshark/pyshark 또는 "
            "pcapng parser를 별도로 사용해야 합니다."
        )

    # PCAP global header는 7개 필드(IHHIIII)입니다.
    # 마지막 필드가 network/linktype입니다.
    _, _, _, _, _, _, network = struct.unpack(
        endian + "IHHIIII", data[:24]
    )
    print(
        f"[PCAP] linktype={network} "
        f"({linktype_name(network)}) size={len(data):,} bytes"
    )

    offset = 24
    index = 0

    while offset + 16 <= len(data):
        ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
            endian + "IIII", data[offset:offset + 16]
        )
        offset += 16

        if offset + incl_len > len(data):
            break

        frame = data[offset:offset + incl_len]
        offset += incl_len
        index += 1

        pkt = parse_linktype_ipv4_tcp(index, frame, network)
        if pkt:
            yield pkt


def linktype_name(network: int) -> str:
    return {
        1: "Ethernet",
        101: "RAW IPv4",
        113: "Linux SLL",
        276: "Linux SLL2",
    }.get(network, "unknown")


def parse_linktype_ipv4_tcp(index: int, frame: bytes, network: int):
    if network == 1:
        return parse_ethernet_ipv4_tcp(index, frame)
    if network == 101:
        return parse_ipv4_tcp(index, frame)
    if network == 113:
        if len(frame) < 16:
            return None
        proto = u16be(frame[14:16])
        if proto != 0x0800:
            return None
        return parse_ipv4_tcp(index, frame[16:])
    if network == 276:
        if len(frame) < 20:
            return None
        proto = u16be(frame[0:2])
        if proto != 0x0800:
            return None
        return parse_ipv4_tcp(index, frame[20:])
    return None


def parse_ethernet_ipv4_tcp(index: int, frame: bytes):
    if len(frame) < 14:
        return None

    eth_type = u16be(frame[12:14])
    if eth_type != 0x0800:
        return None

    return parse_ipv4_tcp(index, frame[14:])


def parse_ipv4_tcp(index: int, ip: bytes):
    if len(ip) < 20:
        return None

    version = ip[0] >> 4
    ihl = (ip[0] & 0x0F) * 4
    if version != 4 or ihl < 20 or len(ip) < ihl:
        return None

    protocol = ip[9]
    if protocol != 6:
        return None

    src_ip = ip_text(ip[12:16])
    dst_ip = ip_text(ip[16:20])

    tcp = ip[ihl:]
    if len(tcp) < 20:
        return None

    src_port = u16be(tcp[0:2])
    dst_port = u16be(tcp[2:4])
    seq = struct.unpack(">I", tcp[4:8])[0]
    ack = struct.unpack(">I", tcp[8:12])[0]
    flags = u16be(tcp[12:14]) & 0x01FF
    tcp_hlen = ((tcp[12] >> 4) & 0x0F) * 4
    if tcp_hlen < 20 or len(tcp) < tcp_hlen:
        return None

    return Packet(
        index=index,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        seq=seq,
        ack=ack,
        flags=flags,
        payload=tcp[tcp_hlen:],
    )


def find_server_candidates(pkt: Packet, pub1: int, pub2: int, conv_id: int):
    payload = pkt.payload
    p1 = pub1.to_bytes(8, "little")
    p2 = pub2.to_bytes(8, "little")
    cid = conv_id.to_bytes(8, "little")

    hits = []
    start = 0
    while True:
        pos = payload.find(p1, start)
        if pos < 0:
            break

        # 구조상 pos는 +0x15일 가능성이 가장 높다.
        base = pos - 0x15
        if base >= 0 and base + 0x25 <= len(payload):
            candidate = payload[base:base + 0x25]
            length = int.from_bytes(candidate[8:12], "little")
            marker = candidate[12]
            got_cid = u64le(candidate[13:21])
            got_p2 = u64le(candidate[0x1D:0x25])

            if length == 0x19 and marker == 1 and got_p2 == pub2:
                hits.append((base, length, marker, got_cid, got_p2))
        start = pos + 1

    return hits


def find_client_candidates(pkt: Packet):
    payload = pkt.payload
    hits = []

    # 첫 8바이트 zero + public1/public2라는 알려진 형태를
    # 너무 공격적으로 가정하지 않고 zero prefix만 후보로 사용한다.
    for base in range(max(0, len(payload) - 0x18 + 1)):
        if base + 0x18 > len(payload):
            break
        if payload[base:base + 8] != b"\x00" * 8:
            continue

        pub1 = u64le(payload[base + 8:base + 16])
        pub2 = u64le(payload[base + 16:base + 24])

        # 0/1/작은 값은 handshake public 후보에서 제외한다.
        if pub1 <= 1 or pub2 <= 1:
            continue

        hits.append((base, pub1, pub2, len(payload) - base))

    return hits


def reassemble_stream(packets):
    segments = [p for p in packets if p.payload]
    if not segments:
        return []
    segments.sort(key=lambda p: (p.seq, p.index))
    chunks = []
    cur_start = None
    cur_end = None
    cur = bytearray()
    for pkt in segments:
        start, data, end = pkt.seq, pkt.payload, pkt.seq + len(pkt.payload)
        if cur_start is None:
            cur_start, cur_end, cur = start, end, bytearray(data)
        elif start > cur_end:
            chunks.append((cur_start, bytes(cur)))
            cur_start, cur_end, cur = start, end, bytearray(data)
        elif end > cur_end:
            overlap = max(0, cur_end - start)
            cur.extend(data[overlap:])
            cur_end = end
    if cur_start is not None:
        chunks.append((cur_start, bytes(cur)))
    return chunks

def find_client_handshake_in_stream(stream: bytes):
    hits = []
    pos = 0
    zero8 = b"\x00" * 8
    while True:
        pos = stream.find(zero8, pos)
        if pos < 0 or pos + 24 > len(stream):
            break
        pub1 = u64le(stream[pos + 8:pos + 16])
        pub2 = u64le(stream[pos + 16:pos + 24])
        if 1 < pub1 < P and 1 < pub2 < P:
            hits.append((pos, pub1, pub2, len(stream) - pos))
        pos += 1
    return hits

def hex_preview(data: bytes, start: int, length: int = 48):
    return " ".join(f"{b:02x}" for b in data[start:start + length])

def parse_int(s: str) -> int:
    return int(s, 0)


def print_packet(pkt: Packet):
    print(
        f"packet={pkt.index} "
        f"{pkt.src_ip}:{pkt.src_port} -> {pkt.dst_ip}:{pkt.dst_port} "
        f"payload={len(pkt.payload)}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap", type=Path)
    ap.add_argument("--server-public1", type=parse_int, default=DEFAULT_SERVER_PUBLIC1)
    ap.add_argument("--server-public2", type=parse_int, default=DEFAULT_SERVER_PUBLIC2)
    ap.add_argument("--conv-id", type=parse_int, default=DEFAULT_CONV_ID)
    ap.add_argument("--private1", type=parse_int)
    ap.add_argument("--private2", type=parse_int)
    args = ap.parse_args()

    packets = list(read_pcap(args.pcap))

    print(f"[+] Parsed IPv4/TCP packets: {len(packets)}")
    print(f"[+] TCP packets with payload: {len([p for p in packets if p.payload])}")

    server_hits = []
    client_candidates = []

    target = ("10.215.173.1", 39490, "182.92.62.79", 8000)
    reverse = (target[2], target[3], target[0], target[1])
    target_packets = [p for p in packets if (p.src_ip, p.src_port, p.dst_ip, p.dst_port) in (target, reverse)]

    for pkt in target_packets:
        if pkt.payload:
            for hit in find_server_candidates(pkt, args.server_public1, args.server_public2, args.conv_id):
                server_hits.append((pkt, hit))

    client_packets = [p for p in target_packets if (p.src_ip, p.src_port, p.dst_ip, p.dst_port) == target]
    server_packets = [p for p in target_packets if (p.src_ip, p.src_port, p.dst_ip, p.dst_port) == reverse]
    client_chunks = reassemble_stream(client_packets)
    server_chunks = reassemble_stream(server_packets)
    for stream_seq, stream in client_chunks:
        for hit in find_client_handshake_in_stream(stream):
            client_candidates.append((stream_seq, stream, hit))

    print()
    print("[SERVER HANDSHAKE]")
    if not server_hits:
        print("  후보를 찾지 못했습니다.")
    else:
        for pkt, (base, length, marker, cid, p2) in server_hits:
            print_packet(pkt)
            print(f"  offset      = 0x{base:x}")
            print(f"  length      = 0x{length:x}")
            print(f"  marker      = {marker}")
            print(f"  TCPConvID   = 0x{cid:x}")
            print(f"  serverPub1  = 0x{args.server_public1:016x}")
            print(f"  serverPub2  = 0x{p2:016x}")

    print()
    print("[TCP STREAM REASSEMBLY]")
    print("  target = 10.215.173.1:39490 <-> 182.92.62.79:8000")
    print(f"  client payload segments = {len(client_packets)}")
    print(f"  server payload segments = {len(server_packets)}")
    print(f"  client contiguous chunks = {len(client_chunks)}")
    print(f"  server contiguous chunks = {len(server_chunks)}")
    for seq, stream in client_chunks:
        print(f"  client stream seq=0x{seq:08x} length={len(stream)}")
    for seq, stream in server_chunks:
        print(f"  server stream seq=0x{seq:08x} length={len(stream)}")

    print()
    print("[CLIENT HANDSHAKE CANDIDATES - REASSEMBLED]")
    if not client_candidates:
        print("  후보를 찾지 못했습니다.")
    else:
        for stream_seq, stream, (base, pub1, pub2, remaining) in client_candidates[:50]:
            print(f"  stream_seq  = 0x{stream_seq:08x}")
            print(f"  offset      = 0x{base:x}")
            print(f"  clientPub1  = 0x{pub1:016x}")
            print(f"  clientPub2  = 0x{pub2:016x}")
            print(f"  remaining   = {remaining}")
            print(f"  bytes       = {hex_preview(stream, base)}")

    if args.private1 is not None or args.private2 is not None:
        if args.private1 is None or args.private2 is None:
            raise SystemExit("--private1과 --private2를 함께 지정해야 합니다.")

        pub1 = pow(G, args.private1, P)
        pub2 = pow(G, args.private2, P)

        print()
        print("[DH PRIVATE/PUBLIC VALIDATION]")
        print(f"  private1 = 0x{args.private1:016x}")
        print(f"  public1  = 0x{pub1:016x}")
        print(f"  private2 = 0x{args.private2:016x}")
        print(f"  public2  = 0x{pub2:016x}")

        secret1 = pow(args.server_public1, args.private1, P)
        secret2 = pow(args.server_public2, args.private2, P)
        key = secret1.to_bytes(8, "little") + secret2.to_bytes(8, "little")

        print()
        print("[SESSION KEY]")
        print(f"  secret1 = 0x{secret1:016x}")
        print(f"  secret2 = 0x{secret2:016x}")
        print(f"  key     = {key.hex()}")

    print()
    print("[NOTE]")
    print("  TCP stream은 sequence 기준으로 재조립했습니다.")
    print("  현재 대상 연결은 게임 TCP 5-tuple로 제한했습니다.")
    print("  sequence gap은 임의의 0으로 채우지 않고 contiguous chunk로 분리합니다.")


if __name__ == "__main__":
    main()

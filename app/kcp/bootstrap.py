"""Bootstrap OpCode=2 응답 빌더 (자체 생성).

실측 기반: research/PCAP/.../plaintext/000192_s2c.bin 분석.
- 최상위 필드 순서: 1,2,21,35,37,38,39,40,43,44,45,48,49,51,56
- (4,5,12,13,14,15는 device echo, multifrag에서 불필요 확인됨)
- 각 필드는 {f1=ID, f2=nested} 패턴 (field 35=User는 예외)

작성일: 2026-10-02
"""

import gzip


def _varint(field_no: int, value: int) -> bytes:
    out = bytearray()
    out.append((field_no << 3) | 0)
    v = value
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _nested(field_no: int, payload: bytes) -> bytes:
    out = bytearray()
    tag = (field_no << 3) | 2
    while True:
        b = tag & 0x7F
        tag >>= 7
        if tag:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    ln = len(payload)
    while True:
        b = ln & 0x7F
        ln >>= 7
        if ln:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    out.extend(payload)
    return bytes(out)


def _string(field_no: int, s: str) -> bytes:
    return _nested(field_no, s.encode("utf-8"))


def build_user(user_id: int = 861197, username: str = "witchwind3") -> bytes:
    """Field 35 = User. 실측 구조 (33B)."""
    inner = b""
    inner += _varint(1, user_id)
    inner += _varint(3, 4)
    inner += _varint(4, 250)
    inner += _varint(7, 18100000)
    inner += _string(14, username)
    inner += _varint(20, 3)
    inner += _varint(21, 3)
    inner += _varint(22, 10)
    inner += _varint(24, 1)
    return _nested(35, inner)


def build_items(item_list=None) -> bytes:
    """Field 21 = Items (반복). 각 {f1=ID, f2=count}."""
    if item_list is None:
        # 최소 테스트용
        item_list = [(21000010, 1), (21000020, 1), (21000030, 5)]
    out = b""
    for item_id, count in item_list:
        inner = _varint(1, item_id) + _varint(2, count)
        out += _nested(21, inner)
    return out


def build_chapters(chapter_list=None) -> bytes:
    """Field 43 = Chapters (반복). 각 {f1=ID, f2=nested}."""
    if chapter_list is None:
        chapter_list = [(20300000, b""), (20300001, b"")]
    out = b""
    for ch_id, payload in chapter_list:
        inner = _varint(1, ch_id) + _nested(2, payload)
        out += _nested(43, inner)
    return out


def build_simple_field(field_no: int, id_value: int, nested_payload: bytes = b"") -> bytes:
    """일반적인 {f1=ID, f2=nested} 패턴의 필드."""
    inner = _varint(1, id_value) + _nested(2, nested_payload)
    return _nested(field_no, inner)


def build_bootstrap(serial: int, user_id: int = 861197, username: str = "witchwind3",
                    compress: bool = True) -> tuple[bytes, int]:
    """Bootstrap 응답 생성.

    Args:
        serial: 클라이언트 요청의 SerialNumber (반드시 매칭)
        user_id: User ID
        username: Username
        compress: gzip 압축 여부

    Returns:
        (protobuf_bytes 또는 gzip_bytes, flag)
        flag: 0xC4 (압축) 또는 0x84 (비압축)
    """
    # 실측 순서: 1, 2, 21, 35, 37, 38, 39, 40, 43, 44, 45, 48, 49, 51, 56
    probe = b""
    probe += _varint(1, serial)
    probe += _varint(2, 2)  # OpCode=2
    probe += build_items()
    probe += build_user(user_id, username)
    # 기타 필드 (최소 1개씩, 빈 nested)
    # 실측 ID 참고: 37=10000000, 38=18100000, 39=40000000, 48=49000000,
    #              49=60001000, 51=18000001, 56=90015100
    probe += build_simple_field(37, 10000000)
    probe += build_simple_field(38, 18100000)
    probe += build_simple_field(39, 40000000)
    probe += build_simple_field(40, 0)  # 실측 f1='#', 일단 0
    probe += build_chapters()
    probe += build_simple_field(44, 21000010)
    probe += build_simple_field(45, 1)
    probe += build_simple_field(48, 49000000)
    probe += build_simple_field(49, 60001000)
    probe += build_simple_field(51, 18000001)
    probe += build_simple_field(56, 90015100)

    if compress:
        compressed = gzip.compress(probe)
        return compressed, 0xC4
    else:
        return probe, 0x84


# 자가 테스트
if __name__ == "__main__":
    data, flag = build_bootstrap(serial=12345, compress=False)
    print(f"비압축: {len(data)}B, flag={flag:#x}")
    data2, flag2 = build_bootstrap(serial=12345, compress=True)
    print(f"압축: {len(data2)}B, flag={flag2:#x}")
    print(f"gzip 매직: {data2[:3].hex() == '1f8b08'}")
    # 압축 해제 검증
    assert gzip.decompress(data2) == data
    print("✓ 빌더 정상")

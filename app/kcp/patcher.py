"""Bootstrap surgical patch 시스템.

patches.json의 설정을 읽어 실측 protobuf에 적용.
GPT가 code_gen/에 분석한 결과를 여기에 반영하면 코드 수정 없이 패치 가능.

작성일: 2026-10-02
"""

import json
import os


def _encode_varint(v: int) -> bytes:
    out = b""
    while True:
        b = v & 0x7F; v >>= 7
        if v: out += bytes([b | 0x80])
        else: out += bytes([b]); break
    return out


def _parse_varint(d: bytes, pos: int) -> tuple[int, int]:
    v = 0; s = 0
    while pos < len(d):
        b = d[pos]; pos += 1
        v |= (b & 0x7F) << s
        if not (b & 0x80): break
        s += 7
    return v, pos


def _patch_currency(raw_pb: bytes, currency_id: int, new_amount: int) -> tuple[bytes, bool]:
    """field 38에서 currency_id를 찾아 f3 (amount)를 변경.
    
    구조: field 38 = {f1=currency ID, f2={f1=ID, f3=amount}}
    """
    tag38 = b"\xb2\x02"  # (38<<3)|2
    search_pos = 0
    while True:
        idx = raw_pb.find(tag38, search_pos)
        if idx == -1:
            return raw_pb, False
        # length 파싱
        lp = idx + 2
        ln, lp = _parse_varint(raw_pb, lp)
        entry_start = lp
        entry_end = lp + ln
        entry_pb = raw_pb[entry_start:entry_end]
        
        # f1 확인
        if len(entry_pb) > 1 and entry_pb[0] == 0x08:
            fv, fp = _parse_varint(entry_pb, 1)
            if fv == currency_id:
                # f2 찾기
                f2_idx = entry_pb.find(b"\x12", fp)
                if f2_idx != -1:
                    f2_lp = f2_idx + 1
                    f2_ln, f2_lp = _parse_varint(entry_pb, f2_lp)
                    f2_start = f2_lp
                    f2_end = f2_lp + f2_ln
                    f2_pb = entry_pb[f2_start:f2_end]
                    # field 3 찾기
                    f3_idx = f2_pb.find(b"\x18")
                    if f3_idx != -1:
                        _, vp = _parse_varint(f2_pb, f3_idx + 1)
                        new_amt = _encode_varint(new_amount)
                        new_f2 = f2_pb[:f3_idx+1] + new_amt + f2_pb[vp:]
                        new_f2_ln = _encode_varint(len(new_f2))
                        new_entry = entry_pb[:f2_idx+1] + new_f2_ln + new_f2 + entry_pb[f2_end:]
                        new_ln = _encode_varint(len(new_entry))
                        raw_pb = raw_pb[:idx+2] + new_ln + new_entry + raw_pb[entry_end:]
                        return raw_pb, True
        search_pos = idx + 2
    return raw_pb, False




def _patch_item(raw_pb: bytes, item_id: int, new_count: int) -> tuple[bytes, bool]:
    """field 21에서 item_id를 찾아 f2 (Count)를 변경.
    
    구조: field 21 = {f1=Item ID, f2=Count}
    GPT 분석: ProtoItem.Id → field 1, ProtoItem.Count → field 2
    """
    tag21 = b"\xa8\x01"  # (21<<3)|2 = 170
    search_pos = 0
    while True:
        idx = raw_pb.find(tag21, search_pos)
        if idx == -1:
            return raw_pb, False
        lp = idx + 2
        ln, lp = _parse_varint(raw_pb, lp)
        entry_start = lp
        entry_end = lp + ln
        entry_pb = raw_pb[entry_start:entry_end]
        
        if len(entry_pb) > 1 and entry_pb[0] == 0x08:
            fv, fp = _parse_varint(entry_pb, 1)
            if fv == item_id:
                # f2 찾기 (태그 0x10, varint)
                f2_idx = entry_pb.find(b"\x10", fp)
                if f2_idx != -1:
                    _, vp = _parse_varint(entry_pb, f2_idx + 1)
                    new_cnt = _encode_varint(new_count)
                    new_entry = entry_pb[:f2_idx+1] + new_cnt + entry_pb[vp:]
                    new_ln = _encode_varint(len(new_entry))
                    raw_pb = raw_pb[:idx+2] + new_ln + new_entry + raw_pb[entry_end:]
                    return raw_pb, True
        search_pos = idx + 2
    return raw_pb, False


def _patch_hero(raw_pb: bytes, hero_id: int, subfield: int, new_value: int) -> tuple[bytes, bool]:
    """field 37에서 hero_id를 찾아 ProtoHero의 subfield를 변경.
    
    구조: field 37 = {f1=Hero ID, f2=ProtoHero}
    ProtoHero: f1=Id, f3=Level, f4=Exp, f5=Star, f8=Belt, f14=Hole1Stigmata...
    GPT 분석: 강한 확정
    """
    tag37 = b"\xaa\x02"  # (37<<3)|2 = 298
    # subfield 태그 (varint wire type)
    sub_tag = bytes([(subfield << 3) | 0])
    search_pos = 0
    while True:
        idx = raw_pb.find(tag37, search_pos)
        if idx == -1:
            return raw_pb, False
        lp = idx + 2
        ln, lp = _parse_varint(raw_pb, lp)
        entry_start = lp
        entry_end = lp + ln
        entry_pb = raw_pb[entry_start:entry_end]
        
        if len(entry_pb) > 1 and entry_pb[0] == 0x08:
            fv, fp = _parse_varint(entry_pb, 1)
            if fv == hero_id:
                # f2 (ProtoHero) 찾기
                f2_idx = entry_pb.find(b"\x12", fp)
                if f2_idx != -1:
                    f2_lp = f2_idx + 1
                    f2_ln, f2_lp = _parse_varint(entry_pb, f2_lp)
                    f2_start = f2_lp
                    f2_end = f2_lp + f2_ln
                    f2_pb = entry_pb[f2_start:f2_end]
                    # subfield 찾기
                    sf_idx = f2_pb.find(sub_tag)
                    if sf_idx != -1:
                        _, vp = _parse_varint(f2_pb, sf_idx + 1)
                        new_val = _encode_varint(new_value)
                        new_f2 = f2_pb[:sf_idx+1] + new_val + f2_pb[vp:]
                        new_f2_ln = _encode_varint(len(new_f2))
                        new_entry = entry_pb[:f2_idx+1] + new_f2_ln + new_f2 + entry_pb[f2_end:]
                        new_ln = _encode_varint(len(new_entry))
                        raw_pb = raw_pb[:idx+2] + new_ln + new_entry + raw_pb[entry_end:]
                        return raw_pb, True
        search_pos = idx + 2
    return raw_pb, False

def apply_patches(raw_pb: bytes, config_path: str = None) -> tuple[bytes, list[str]]:
    """patches.json의 모든 패치를 적용.
    
    Returns:
        (수정된 protobuf, 적용된 패치 설명 리스트)
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "patches.json")
    
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    
    applied = []
    
    # Currency 패치 (field 38)
    for cur in config.get("currency", []):
        cid = cur["id"]
        amt = cur["amount"]
        name = cur.get("name", f"currency_{cid}")
        raw_pb, ok = _patch_currency(raw_pb, cid, amt)
        if ok:
            applied.append(f"currency[{cid}] ({name}) → {amt}")
        else:
            applied.append(f"currency[{cid}] ({name}) → 실패 (못 찾음)")
    
    # Item 패치 (field 21)
    for item in config.get("items", []):
        iid = item["id"]
        cnt = item["count"]
        name = item.get("name", f"item_{iid}")
        raw_pb, ok = _patch_item(raw_pb, iid, cnt)
        if ok:
            applied.append(f"item[{iid}] ({name}) count → {cnt}")
        else:
            applied.append(f"item[{iid}] ({name}) → 실패 (못 찾음)")
    
    # Hero 패치 (field 37)
    for hero in config.get("heroes", []):
        hid = hero["id"]
        sf = hero["field"]
        val = hero["value"]
        name = hero.get("name", f"hero_{hid}")
        fname = hero.get("field_name", f"f{sf}")
        raw_pb, ok = _patch_hero(raw_pb, hid, sf, val)
        if ok:
            applied.append(f"hero[{hid}] ({name}) {fname} → {val}")
        else:
            applied.append(f"hero[{hid}] ({name}) → 실패 (못 찾음)")
    
    return raw_pb, applied


# 자가 테스트
if __name__ == "__main__":
    import gzip
    # 실측 파일로 테스트 (없으면 스킵)
    try:
        with open("/tmp/000192_s2c.bin", "rb") as f:
            data = gzip.decompress(f.read())
        patched, log = apply_patches(data)
        for l in log:
            print(f"  {l}")
        print("✓ 패처 정상")
    except FileNotFoundError:
        print("테스트 파일 없음, 스킵")

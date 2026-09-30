#!/usr/bin/env python3
"""
Unity MonoBehaviour JSON -> Offline GameData 정규화 데이터셋 생성기.

목표:
- 원본 JSON을 수정하지 않는다.
- 의미를 추측하여 값을 바꾸지 않는다.
- Record/Field/Reference/Localization을 재사용하기 좋은 형태로 정리한다.
- 시스템 분류는 candidate로만 저장한다.
- unresolved 값은 그대로 보존한다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")
ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}
KR_SUFFIX = "__krRecord.json"

SYSTEM_RULES = {
    "gacha": ("draw", "gacha", "pumping"),
    "item_package": ("itempackage", "item_package", "package"),
    "item": ("itemrecord", "itemdata", "item"),
    "reward": ("reward", "drop", "loot"),
    "shop": ("shop", "store"),
    "daily": ("daily", "login", "attendance"),
    "achievement": ("achievement", "mission"),
    "event": ("event", "season", "limited"),
    "quest": ("quest",),
    "stage": ("stage", "dungeon", "wave"),
    "monster": ("monster", "boss", "enemy"),
    "character": ("character", "hero"),
    "equipment": ("equipment", "weapon", "armor", "accessory"),
    "skill": ("skill", "passive"),
    "currency": ("currency", "gold", "gem"),
}

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def decode_obscured_id(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    hidden = value.get("hiddenValue")
    key = value.get("currentCryptoKey")
    if isinstance(hidden, int) and isinstance(key, int):
        return hidden ^ key
    return None

def scalar_id(value: Any) -> str | None:
    decoded = decode_obscured_id(value)
    if decoded is not None:
        return str(decoded)
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        value = str(value).strip()
        return value or None
    return None

def find_record_id(obj: dict[str, Any]) -> str | None:
    for key, value in obj.items():
        if str(key).lower() in ID_KEYS:
            found = scalar_id(value)
            if found is not None:
                return found
    return None

def iter_records(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        rid = find_record_id(obj)
        if rid is not None:
            yield path, obj, rid
        for key, value in obj.items():
            yield from iter_records(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_records(value, f"{path}[{i}]")

def flatten_scalars(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        if decode_obscured_id(obj) is not None:
            yield path, obj
            return
        for key, value in obj.items():
            yield from flatten_scalars(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from flatten_scalars(value, f"{path}[{i}]")
    else:
        yield path, obj

def parse_code_value(value: Any):
    if not isinstance(value, str) or "|" not in value or "*" not in value:
        return []
    result = []
    for i, part in enumerate(value.split("|")):
        part = part.strip()
        if not part or "*" not in part:
            return []
        code, raw_value = part.split("*", 1)
        if not code or not raw_value:
            return []
        result.append({"index": i, "code": code.strip(), "value": raw_value.strip()})
    return result

def parse_multi_id(value: Any):
    if not isinstance(value, str) or "|" not in value or "*" in value:
        return []
    parts = [x.strip() for x in value.split("|")]
    if len(parts) < 2 or any(not x for x in parts):
        return []
    return [{"index": i, "value": x} for i, x in enumerate(parts)]

def classify_file(path: Path) -> list[str]:
    name = path.name.lower()
    if name.endswith(KR_SUFFIX.lower()):
        name = name[:-len(KR_SUFFIX)]
    labels = []
    for system, keywords in SYSTEM_RULES.items():
        if any(k in name for k in keywords):
            labels.append(system)
    return labels or ["other"]

def localized_name(record: dict[str, Any], path: Path):
    if path.name.lower().endswith(KR_SUFFIX.lower()):
        value = record.get("m_cn")
        if value not in (None, ""):
            return {"value": value, "source": "m_cn", "language": "ko"}
    for key in ("m_name", "name", "m_nameId", "nameId"):
        if key in record and record[key] not in (None, ""):
            return {"value": record[key], "source": key, "language": "unknown"}
    return None

def write_jsonl(handle, obj: Any):
    handle.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = (args.data_root or DEFAULT_DATA_ROOT).resolve()
    out = (args.output or script_dir / "output" / "normalized").resolve()

    if not root.exists():
        raise SystemExit(f"[오류] 데이터 경로가 없습니다: {root}")

    out.mkdir(parents=True, exist_ok=True)
    files = sorted(root.rglob("*.json"))

    all_path = out / "all_records.ndjson"
    system_path = out / "system_records.ndjson"
    loc_path = out / "localization.ndjson"
    refs_path = out / "references.ndjson"
    unresolved_path = out / "unresolved.ndjson"
    structured_path = out / "structured_values.ndjson"

    counts = Counter()
    system_counts = Counter()
    field_counts = Counter()
    file_counts = Counter()
    value_formats = Counter()
    parse_errors = []
    ids = defaultdict(list)
    record_count = 0

    with all_path.open("w", encoding="utf-8") as all_out, system_path.open("w", encoding="utf-8") as sys_out, loc_path.open("w", encoding="utf-8") as loc_out, structured_path.open("w", encoding="utf-8") as structured_out:
        for index, path in enumerate(files, 1):
            rel = path.relative_to(root).as_posix()
            try:
                data = load_json(path)
            except Exception as exc:
                parse_errors.append({"file": rel, "error_type": type(exc).__name__, "error": str(exc)})
                continue

            labels = classify_file(path)
            file_record_count = 0

            for record_path, record, rid in iter_records(data):
                record_count += 1
                file_record_count += 1
                counts["records"] += 1
                file_counts[rel] += 1
                ids[rid].append({"file": rel, "path": record_path})

                name_info = localized_name(record, path)
                write_jsonl(all_out, {
                    "record_id": rid,
                    "source_file": rel,
                    "source_path": record_path,
                    "system_candidates": labels,
                    "record": record,
                    "name_candidate": name_info,
                })

                for system in labels:
                    system_counts[system] += 1
                    write_jsonl(sys_out, {
                        "system": system,
                        "record_id": rid,
                        "source_file": rel,
                        "source_path": record_path,
                        "record": record,
                    })

                if name_info is not None:
                    write_jsonl(loc_out, {
                        "record_id": rid,
                        "source_file": rel,
                        "source_path": record_path,
                        **name_info,
                    })

                for field_path, value in flatten_scalars(record):
                    field = field_path.rsplit(".", 1)[-1]
                    field_counts[field] += 1
                    code_items = parse_code_value(value)
                    if code_items:
                        value_formats["CODE*VALUE"] += 1
                        write_jsonl(structured_out, {
                            "record_id": rid,
                            "source_file": rel,
                            "source_path": record_path,
                            "field": field_path,
                            "format": "CODE*VALUE",
                            "raw_value": value,
                            "items": code_items,
                        })
                    multi_items = parse_multi_id(value)
                    if multi_items:
                        value_formats["ID|ID"] += 1
                        write_jsonl(structured_out, {
                            "record_id": rid,
                            "source_file": rel,
                            "source_path": record_path,
                            "field": field_path,
                            "format": "ID|ID",
                            "raw_value": value,
                            "items": multi_items,
                        })

            print(f"[{index}/{len(files)}] {rel} | Record {file_record_count}")

    id_index = {rid: locations for rid, locations in ids.items()}
    ref_count = 0
    unresolved_count = 0

    with refs_path.open("w", encoding="utf-8") as refs_out, unresolved_path.open("w", encoding="utf-8") as unresolved_out:
        for path in files:
            rel = path.relative_to(root).as_posix()
            try:
                data = load_json(path)
            except Exception:
                continue

            for record_path, record, rid in iter_records(data):
                for field_path, value in flatten_scalars(record):
                    field = field_path.rsplit(".", 1)[-1]
                    if "id" not in field.lower():
                        continue

                    candidates = []
                    if isinstance(value, list):
                        candidates = [scalar_id(x) for x in value]
                    else:
                        candidate = scalar_id(value)
                        if candidate is not None:
                            candidates = [candidate]

                    for candidate in candidates:
                        if candidate is None or candidate == rid:
                            continue
                        row = {
                            "source_record_id": rid,
                            "source_file": rel,
                            "source_path": record_path,
                            "field": field_path,
                            "raw_value": value,
                            "candidate_id": candidate,
                        }
                        targets = id_index.get(candidate, [])
                        if targets:
                            ref_count += len(targets)
                            write_jsonl(refs_out, {**row, "targets": targets})
                        else:
                            unresolved_count += 1
                            write_jsonl(unresolved_out, row)

    duplicates = [
        {"record_id": rid, "locations": locations}
        for rid, locations in sorted(id_index.items())
        if len(locations) > 1
    ]

    inventory = {
        "stage": "normalized_game_data",
        "purpose": "local JSON facts normalized for later Offline GameData use",
        "json_file_count": len(files),
        "parsed_file_count": len(files) - len(parse_errors),
        "record_count": record_count,
        "unique_record_ids": len(id_index),
        "duplicate_record_ids": len(duplicates),
        "validated_reference_rows": ref_count,
        "unresolved_reference_rows": unresolved_count,
        "parse_errors": len(parse_errors),
        "system_record_counts": dict(system_counts),
        "value_format_counts": dict(value_formats),
        "files": dict(file_counts),
        "rules": {
            "record_id": "id/m_id/_id/recordid/record_id; hiddenValue XOR currentCryptoKey supported",
            "system_classification": "filename candidate only; not semantic confirmation",
            "localization": "__krRecord.json uses m_cn",
            "reference": "exact local logical-ID equality only",
            "unresolved": "preserved; absence from local data is not proof of nonexistence",
            "raw_record": "preserved without semantic rewriting",
            "probability_quantity_price": "not inferred",
            "server_data": "not inferred from local JSON",
        },
    }

    (out / "data_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "duplicate_ids.json").write_text(json.dumps(duplicates, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "field_inventory.json").write_text(json.dumps({"field_counts": field_counts.most_common()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "parse_errors.ndjson").write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in parse_errors), encoding="utf-8")

    unknown_md = f"""# Unknown / Server Candidate

이 결과는 로컬 클라이언트 JSON에서 확인된 사실의 정리본이다.

## 원칙

- 원본 JSON에 없는 데이터는 실제 게임에 없다고 판단하지 않는다.
- 서버가 계산하거나 반환할 수 있는 확률, Weight, Quantity, Reward Result는 임의 생성하지 않는다.
- unresolved.ndjson은 로컬 데이터에서 대상을 찾지 못한 참조를 그대로 보존한다.
- system_records.ndjson의 system 값은 파일명 기반 candidate이며 최종 게임 의미가 아니다.
- m_probability, itemWeight 등의 의미는 이 단계에서 확정하지 않는다.
- 이후 구현 단계에서 확인된 데이터만 별도 Confirmed Local Data로 승격한다.

## 현재 규모

- JSON: {len(files)}
- Record: {record_count:,}
- 고유 ID: {len(id_index):,}
- 중복 ID: {len(duplicates):,}
- 검증 참조: {ref_count:,}
- 미해결 참조: {unresolved_count:,}
- 파싱 오류: {len(parse_errors):,}

## 다음 단계

1. 정규화 데이터를 기반으로 필요한 시스템만 선택한다.
2. 실제 구현에 필요한 필드만 별도 GameData schema로 만든다.
3. 구현 중 부족한 데이터가 발견될 때만 원본/코드/네트워크를 추가 조사한다.
4. 추측 데이터와 원본 데이터를 같은 필드에 섞지 않는다.
"""
    (out / "unknown_data.md").write_text(unknown_md, encoding="utf-8")

    print("\n[완료]")
    print(f"  JSON: {len(files)}")
    print(f"  Record: {record_count:,}")
    print(f"  고유 ID: {len(id_index):,}")
    print(f"  검증 참조: {ref_count:,}")
    print(f"  미해결 참조: {unresolved_count:,}")
    print(f"  중복 ID: {len(duplicates):,}")
    print(f"  오류: {len(parse_errors):,}")
    print(f"  결과: {out}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
정규화된 Unity Record에서 Offline GameData 1차 시스템 데이터셋을 생성한다.

원칙:
- 원본/정규화 데이터를 수정하지 않는다.
- 파일명/필드 구조로 확인 가능한 연결만 기록한다.
- 의미가 확정되지 않은 필드는 raw에 보존하고 이름을 임의 변경하지 않는다.
- 모든 데이터셋은 source_file, record_id, raw를 유지한다.
- 로컬에서 대상을 찾지 못한 ID는 unresolved로 분리한다.
"""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SYSTEM_FILES = {
    "item": ["ItemRecord.json"],
    "equipment": ["EquipmentRecord.json"],
    "weapon": ["WeaponRecord.json"],
    "character": ["ActorRecord.json", "ActorshowRecord.json", "ActorbreachRecord.json"],
    "skill": ["SkillRecord.json", "SkilleffRecord.json", "SkillattackRecord.json", "SkillbuffRecord.json", "SkillshowRecord.json", "SkillrandRecord.json"],
}

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f: return json.load(f)

def decode_id(v: Any) -> str | None:
    if isinstance(v, dict):
        h, k = v.get("hiddenValue"), v.get("currentCryptoKey")
        if isinstance(h, int) and isinstance(k, int): return str(h ^ k)
    if isinstance(v, (int, str)) and not isinstance(v, bool):
        s = str(v).strip()
        return s or None
    return None

def find_id(record: dict[str, Any]) -> str | None:
    for k in ("id", "m_id", "_id", "recordid", "record_id"):
        if k in record:
            x = decode_id(record[k])
            if x is not None: return x
    return None

def iter_records(obj: Any):
    if isinstance(obj, dict):
        rid = find_id(obj)
        if rid is not None: yield obj, rid
        for v in obj.values(): yield from iter_records(v)
    elif isinstance(obj, list):
        for v in obj: yield from iter_records(v)

def read_normalized(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def scalar_ids(value: Any):
    if isinstance(value, list):
        for x in value:
            y = decode_id(x)
            if y is not None: yield y
    else:
        y = decode_id(value)
        if y is not None: yield y

def extract_refs(record: dict[str, Any], local_ids: set[str]):
    for field, value in record.items():
        if "id" not in str(field).lower(): continue
        for target in scalar_ids(value):
            yield {"field": field, "target_id": target,
                   "status": "confirmed_local" if target in local_ids else "unresolved_local"}

def build():
    ap = argparse.ArgumentParser()
    ap.add_argument("--normalized", type=Path, default=None)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    base = Path(__file__).resolve().parent
    normalized = (args.normalized or base / "output" / "normalized").resolve()
    output = (args.output or base / "output" / "gamedata").resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_records = normalized / "all_records.ndjson"
    if not all_records.exists(): raise SystemExit(f"[오류] 정규화 데이터가 없습니다: {all_records}")

    targets = {name for files in SYSTEM_FILES.values() for name in files}
    rows_by_system = defaultdict(list)
    source_counts = Counter()
    for row in read_normalized(all_records):
        source = Path(row["source_file"]).name
        if source in targets:
            rows_by_system[source].append(row)
            source_counts[source] += 1

    local_ids = {str(row["record_id"]) for row in read_normalized(all_records)}
    summary = {
        "stage": "gamedata_dataset_v1",
        "source": "normalized/all_records.ndjson",
        "semantic_inference": False,
        "systems": {},
        "rules": {
            "record_id": "normalized logical record_id",
            "references": "exact local logical-ID equality only",
            "raw": "complete normalized record preserved",
            "unresolved": "reference candidate not found in local ID index",
            "server_data": "not generated",
        },
    }

    for system, files in SYSTEM_FILES.items():
        system_rows = []
        for filename in files:
            for row in rows_by_system.get(filename, []):
                refs = list(extract_refs(row["record"], local_ids))
                system_rows.append({
                    "record_id": str(row["record_id"]),
                    "source_file": row["source_file"],
                    "source_path": row["source_path"],
                    "system": system,
                    "name_candidate": row.get("name_candidate"),
                    "references": refs,
                    "raw": row["record"],
                })
        out_file = output / f"{system}.ndjson"
        with out_file.open("w", encoding="utf-8") as f:
            for item in system_rows:
                f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        ref_total = sum(len(x["references"]) for x in system_rows)
        unresolved = sum(1 for x in system_rows for r in x["references"] if r["status"] == "unresolved_local")
        summary["systems"][system] = {
            "record_count": len(system_rows), "source_files": files,
            "reference_count": ref_total, "unresolved_reference_count": unresolved,
            "output": out_file.name,
        }

    (output / "gamedata_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Offline GameData 1차 데이터셋", "",
          "정규화된 로컬 JSON에서 실제 시스템별 Record를 추출한 1차 데이터셋이다.", "",
          "## 원칙",
          "- raw Record는 그대로 보존한다.",
          "- record_id는 정규화 단계에서 계산된 logical ID를 사용한다.",
          "- 확인 가능한 로컬 ID 연결만 confirmed_local로 기록한다.",
          "- 찾지 못한 ID는 unresolved_local로 남긴다.",
          "- 확률/수량/가격/서버 응답은 임의 생성하지 않는다.", "", "## 데이터셋"]
    for system, info in summary["systems"].items():
        md += [f"### {system}", f"- Record: {info['record_count']:,}",
               f"- Reference: {info['reference_count']:,}",
               f"- Unresolved: {info['unresolved_reference_count']:,}",
               f"- Source: {', '.join(info['source_files'])}",
               f"- Output: {info['output']}", ""]
    md += ["## 다음 단계",
           "1. Item/Equipment/Weapon의 실제 필드와 연결을 검증한다.",
           "2. Actor/Skill 계층을 연결하되 필드 의미는 원본 명칭을 우선한다.",
           "3. Stage/Monster/Reward/Package를 별도 데이터셋으로 추가한다.",
           "4. 이후 Gacha/Shop/Mission/Daily/Event를 연결한다.",
           "5. 구현에 필요한 데이터만 confirmed_local로 승격한다."]
    (output / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("[완료]")
    for system, info in summary["systems"].items(): print(f"  {system}: {info['record_count']:,}")
    print(f"  결과: {output}")

if __name__ == "__main__": build()

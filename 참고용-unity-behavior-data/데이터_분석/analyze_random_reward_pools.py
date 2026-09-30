#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7차: Package/Random Reward 공통사용 구조 탐색.

목적:
- Package를 Gacha 전용으로 가정하지 않고 Reward/Drop/Dungeon/Quest/Daily/Achievement/Event/Shop 등에서
  유사한 random-pool/lookup 구조가 사용되는지 원본 JSON 전체에서 탐색한다.
- m_itemPackageId는 Record FK로 확정하지 않고 opaque identifier로 유지한다.
- 의미를 임의 확정하지 않고 field/path/value/source evidence를 보존한다.

실행:
python analyze_random_reward_pools.py
python analyze_random_reward_pools.py --data-root <MonoBehaviour>
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}
OBSCURED = {"hiddenValue", "currentCryptoKey"}

PACKAGE_FIELDS = {
    "m_itemPackageId", "itemPackageId", "item_package_id",
    "packageId", "m_packageId", "PackageId",
}
POOL_FIELDS = {
    "m_poolId", "poolId", "m_dropPoolId", "dropPoolId",
    "m_dropGroup", "dropGroup", "m_randomGroup", "randomGroup",
    "m_rewardGroup", "rewardGroup", "m_rewardId", "rewardId",
    "m_dropTable", "dropTable", "m_tableId", "tableId",
    "m_boxId", "boxId", "m_contentId", "contentId",
}
REWARD_WORDS = re.compile(
    r"(reward|drop|loot|package|pool|random|lottery|draw|"
    r"dungeon|stage|quest|mission|achievement|daily|login|"
    r"event|shop|box|chest|pumping|bonus|gift)",
    re.I,
)
RANDOM_WORDS = re.compile(r"(random|lottery|draw|drop|loot|pool|package|box|chest)", re.I)
SYSTEM_WORDS = {
    "gacha": re.compile(r"(draw|gacha|pumping|lottery)", re.I),
    "reward": re.compile(r"(reward|drop|loot|bonus|gift)", re.I),
    "dungeon_stage": re.compile(r"(dungeon|stage|wave)", re.I),
    "quest": re.compile(r"(quest|mission|achievement)", re.I),
    "daily_login": re.compile(r"(daily|login|attendance)", re.I),
    "event": re.compile(r"(event|season|limited)", re.I),
    "shop": re.compile(r"(shop|store|purchase)", re.I),
}

def logical_id(v):
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.isdigit():
        try: return int(v)
        except Exception: return None
    if isinstance(v, dict) and set(v.keys()) >= OBSCURED:
        try:
            return int(v["hiddenValue"]) ^ int(v["currentCryptoKey"])
        except Exception:
            return None
    return None

def load_json(p):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def walk(v, path=()):
    yield path, v
    if isinstance(v, dict):
        for k, x in v.items():
            yield from walk(x, path + (str(k),))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk(x, path + (f"[{i}]",))

def classify_context(filename, path):
    s = filename + " " + ".".join(path)
    hits = [name for name, rx in SYSTEM_WORDS.items() if rx.search(s)]
    if not hits:
        hits = ["other"]
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=str(Path(__file__).parent.parent / "MonoBehaviour"))
    ap.add_argument("--output-root", default=str(Path(__file__).parent / "output" / "system_mapping" / "reward_pool"))
    args = ap.parse_args()
    root = Path(args.data_root)
    out = Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(root.glob("*.json"))
    id_index = {}
    records = []
    hits = []
    parse_errors = []
    package_values = set()
    field_counts = Counter()
    context_counts = Counter()
    target_field_context = defaultdict(Counter)

    for fp in files:
        try:
            data = load_json(fp)
        except Exception as e:
            parse_errors.append({"file": fp.name, "error": str(e)})
            continue
        for path, node in walk(data):
            if isinstance(node, dict):
                rid = None
                for k in ID_KEYS:
                    if k in node:
                        rid = logical_id(node[k])
                        if rid is not None:
                            break
                if rid is not None:
                    id_index.setdefault(rid, {"file": fp.name, "path": ".".join(path)})
                    records.append((fp.name, path, rid, node))
                for k, v in node.items():
                    lk = str(k)
                    if lk in PACKAGE_FIELDS:
                        pv = logical_id(v)
                        if pv is not None:
                            package_values.add(pv)
                            field_counts[lk] += 1
                            ctx = classify_context(fp.name, path)
                            for c in ctx:
                                context_counts[(lk, c)] += 1
                            hits.append({
                                "kind": "package_field",
                                "field": lk,
                                "value": pv,
                                "source_file": fp.name,
                                "record_id": rid,
                                "path": ".".join(path),
                                "context": ctx,
                                "raw_value": v,
                            })
                    elif lk in POOL_FIELDS:
                        pv = logical_id(v)
                        if pv is not None:
                            field_counts[lk] += 1
                            ctx = classify_context(fp.name, path)
                            for c in ctx:
                                context_counts[(lk, c)] += 1
                            hits.append({
                                "kind": "pool_field",
                                "field": lk,
                                "value": pv,
                                "source_file": fp.name,
                                "record_id": rid,
                                "path": ".".join(path),
                                "context": ctx,
                                "raw_value": v,
                            })
                    elif isinstance(v, (str, int, float)):
                        if RANDOM_WORDS.search(lk) or (isinstance(v, str) and RANDOM_WORDS.search(v)):
                            ctx = classify_context(fp.name, path)
                            hits.append({
                                "kind": "random_named_field",
                                "field": lk,
                                "value": v,
                                "source_file": fp.name,
                                "record_id": rid,
                                "path": ".".join(path),
                                "context": ctx,
                            })

    exact_package_defs = {x for x in package_values if x in id_index}
    package_contexts = defaultdict(Counter)
    package_files = defaultdict(set)
    for h in hits:
        if h["kind"] == "package_field":
            for c in h["context"]:
                package_contexts[h["value"]][c] += 1
            package_files[h["value"]].add(h["source_file"])

    # Candidate "reward pool" records: reward/random terminology in file/path OR package/pool fields.
    candidate_records = []
    for fp, path, rid, node in records:
        s = fp + " " + ".".join(path) + " " + " ".join(map(str, node.keys()))
        fields = [k for k in node if k in PACKAGE_FIELDS or k in POOL_FIELDS]
        if REWARD_WORDS.search(s) or fields:
            candidate_records.append({
                "record_id": rid,
                "source_file": fp,
                "path": ".".join(path),
                "candidate_fields": fields,
                "keys": list(node.keys()),
                "system_context": classify_context(fp, path),
            })

    summary = {
        "stage": "7",
        "json_file_count": len(files),
        "parsed_file_count": len(files) - len(parse_errors),
        "unique_record_ids": len(id_index),
        "package_field_occurrences": sum(1 for h in hits if h["kind"] == "package_field"),
        "unique_package_values": len(package_values),
        "package_values_with_exact_record_definition": len(exact_package_defs),
        "package_values_without_exact_record_definition": len(package_values - exact_package_defs),
        "pool_or_reward_field_occurrences": sum(1 for h in hits if h["kind"] in {"pool_field", "random_named_field"}),
        "candidate_reward_pool_records": len(candidate_records),
        "parse_errors": len(parse_errors),
        "field_counts": dict(field_counts),
        "context_counts": {f"{k[0]}::{k[1]}": v for k,v in context_counts.items()},
        "rules": {
            "package_is_gacha_only": False,
            "m_itemPackageId": "opaque identifier; not assumed to be Record FK",
            "semantic_inference": False,
            "server_only_reward": "not inferable from JSON alone",
        },
    }

    def dump(name, rows):
        with (out / name).open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    (out / "05_random_reward_pool_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dump("random_reward_pool_hits.ndjson", hits)
    dump("random_reward_pool_candidates.ndjson", candidate_records)
    dump("package_value_contexts.ndjson", [
        {"package_id": k, "contexts": dict(v), "files": sorted(package_files[k])}
        for k, v in sorted(package_contexts.items())
    ])
    (out / "parse_errors.ndjson").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in parse_errors),
        encoding="utf-8",
    )

    md = f"""# Random Reward Pool / Package 공통사용 7차 분석

## 실행 결과

- JSON: {len(files)}
- 정상 파싱: {len(files)-len(parse_errors)}
- 고유 Record ID: {len(id_index):,}
- Package 계열 필드 발생: {summary["package_field_occurrences"]:,}
- 고유 Package 값: {len(package_values):,}
- 정확한 Record 정의가 있는 Package 값: {len(exact_package_defs):,}
- 정확한 Record 정의가 없는 Package 값: {len(package_values-exact_package_defs):,}
- Pool/Reward 계열 후보 필드 발생: {summary["pool_or_reward_field_occurrences"]:,}
- Reward/Pool 후보 Record: {len(candidate_records):,}
- Parse errors: {len(parse_errors)}

## 목적

Package를 Gacha 전용으로 가정하지 않고, Dungeon/Stage/Quest/Daily/Achievement/Event/Shop/Reward 등에서
동일하거나 유사한 랜덤 보상 풀/lookup 구조가 재사용되는지 탐색한다.

## 해석 원칙

- Package ID는 Record FK로 자동 확정하지 않는다.
- 서버에서만 존재하는 보상 풀인지 여부는 JSON만으로 확정하지 않는다.
- m_probability, weight, quantity 등은 field/연결 구조가 검증되기 전까지 의미를 확정하지 않는다.
- 후보군은 evidence를 보존하고 이후 코드/IL2CPP 사용 추적으로 검증한다.

## 다음 단계

1. Package/Pool 후보가 실제 Reward/Dungeon/Quest 등의 입력으로 사용되는지 확인
2. 동일 Package/Pool 값의 다중 시스템 재사용 여부 확인
3. 보상 슬롯별 Package 호출 조합 구조 확인
4. 코드/디컴파일에서 resolver 및 서버 요청 여부 추적
"""
    (out / "random_reward_pool_analysis.md").write_text(md, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

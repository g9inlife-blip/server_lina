#!/usr/bin/env python3
"""6.6차 Gacha Package ID 호출/Lookup 구조 추적기."""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")
ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}

def load(p):
    with p.open("r", encoding="utf-8-sig") as f: return json.load(f)

def scalar(v):
    if isinstance(v, dict) and isinstance(v.get("hiddenValue"), int) and isinstance(v.get("currentCryptoKey"), int):
        return str(v["hiddenValue"] ^ v["currentCryptoKey"])
    if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
        return str(v).strip()
    return None

def rid(o):
    if not isinstance(o, dict): return None
    for k, v in o.items():
        if str(k).lower() in ID_KEYS:
            x = scalar(v)
            if x: return x
    return None

def walk(o, path="$"):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items(): yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, f"{path}[{i}]")

def flatten(o, prefix="$"):
    if scalar(o) is not None:
        yield prefix, scalar(o); return
    if isinstance(o, dict):
        for k, v in o.items(): yield from flatten(v, f"{prefix}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from flatten(v, f"{prefix}[{i}]")

def split_refs(v):
    parts = [str(v).strip()]
    for sep in ("|", ",", ";"):
        nxt = []
        for p in parts: nxt.extend(p.split(sep))
        parts = nxt
    return [p.strip() for p in parts if p.strip()]

def file_type(name):
    n = Path(name).name.lower()
    if "drawpreview" in n: return "DrawPreviewRecord"
    if "drawrecord" in n: return "DrawRecord"
    if "itempackage" in n or "item_package" in n or "itempack" in n: return "ItemPackage"
    if "itemrecord" in n: return "Item"
    if "reward" in n: return "Reward"
    if "weapon" in n: return "Weapon"
    if "character" in n or "hero" in n: return "Character"
    if "fragment" in n or "piece" in n or "shard" in n: return "Fragment"
    if "currency" in n or "wallet" in n: return "Currency"
    return "Unknown"

def context_kind(field, raw, owner_type, self_match):
    fl = field.rsplit(".", 1)[-1].lower()
    if owner_type == "DrawRecord" and fl == "m_itempackageid": return "DRAW_PACKAGE_CALL_VALUE"
    if self_match: return "RECORD_ID_SELF_MATCH"
    if "package" in fl: return "PACKAGE_NAMED_CONTEXT"
    if "key" in fl or fl == "id" or fl.endswith("id"): return "KEY_OR_ID_CONTEXT"
    if isinstance(raw, str) and any(x in raw for x in ("*", "|", ",", ";")): return "COMPOUND_VALUE_CONTEXT"
    if "[" in field: return "ARRAY_MEMBER_CONTEXT"
    return "GENERIC_VALUE_CONTEXT"

def write_ndjson(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    root = args.data_root.resolve()
    base = Path(__file__).resolve().parent
    out = (args.output or base / "output" / "system_mapping" / "gacha").resolve()
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(root.rglob("*.json"))
    records, by_id, errors = [], defaultdict(list), []
    for p in files:
        rel = p.relative_to(root).as_posix()
        try: data = load(p)
        except Exception as e:
            errors.append({"file": rel, "error": f"{type(e).__name__}: {e}"}); continue
        for path, obj in walk(data):
            x = rid(obj)
            if x is None: continue
            rec = {"id": x, "file": rel, "path": path, "type": file_type(rel), "object": obj}
            records.append(rec); by_id[x].append(rec)

    draws = []
    for r in records:
        if r["type"] != "DrawRecord": continue
        o = r["object"]; pid = scalar(o.get("m_itemPackageId"))
        if pid:
            draws.append({
                "draw_id": r["id"], "file": r["file"], "path": r["path"], "package_id": pid,
                "group": scalar(o.get("m_group")), "probability": scalar(o.get("m_probability")),
                "period": scalar(o.get("m_period")), "star": scalar(o.get("m_star")),
                "type": scalar(o.get("m_type")), "limit": scalar(o.get("m_limit"))
            })

    package_ids = sorted({d["package_id"] for d in draws}); package_set = set(package_ids)
    occurrences, parent_rows = [], []
    contexts = Counter(); files_by_pid = defaultdict(set); exact_record_hits = defaultdict(list)

    for r in records:
        for field, raw in flatten(r["object"]):
            hits = set()
            for part in split_refs(raw):
                if part in package_set: hits.add(part)
                if "*" in part:
                    left = part.split("*", 1)[0].strip()
                    if left in package_set: hits.add(left)
            for pid in sorted(hits):
                self_match = r["id"] == pid
                kind = context_kind(field, raw, r["type"], self_match)
                row = {
                    "package_id": pid, "owner_id": r["id"], "owner_file": r["file"],
                    "owner_path": r["path"], "owner_type": r["type"],
                    "field": field, "field_name": field.rsplit(".", 1)[-1],
                    "context_kind": kind, "raw_value": raw, "is_owner_id": self_match
                }
                occurrences.append(row); contexts[kind] += 1; files_by_pid[pid].add(r["file"])
                if self_match: exact_record_hits[pid].append(row)

    for r in records:
        for path, obj in walk(r["object"]):
            if not isinstance(obj, dict): continue
            direct = []
            for k, v in obj.items():
                for part in split_refs(v):
                    pid = part if part in package_set else (part.split("*", 1)[0].strip() if "*" in part else None)
                    if pid in package_set: direct.append({"field": k, "package_id": pid, "raw_value": v})
            if direct:
                parent_rows.append({
                    "owner_id": r["id"], "owner_file": r["file"], "owner_type": r["type"],
                    "object_path": path, "object_keys": list(obj.keys()), "package_fields": direct
                })

    usage = defaultdict(lambda: {"draws": [], "groups": set(), "periods": set(), "probabilities": set()})
    for d in draws:
        u = usage[d["package_id"]]; u["draws"].append(d["draw_id"])
        if d["group"] is not None: u["groups"].add(d["group"])
        if d["period"] is not None: u["periods"].add(d["period"])
        if d["probability"] is not None: u["probabilities"].add(d["probability"])

    usage_rows = []
    for pid in package_ids:
        u = usage[pid]
        usage_rows.append({
            "package_id": pid, "draw_count": len(u["draws"]), "draw_ids": sorted(u["draws"]),
            "groups": sorted(u["groups"]), "group_count": len(u["groups"]),
            "periods": sorted(u["periods"]), "probabilities": sorted(u["probabilities"]),
            "exact_record_definition_count": len(exact_record_hits[pid]),
            "occurrence_count": sum(x["package_id"] == pid for x in occurrences),
            "source_file_count": len(files_by_pid[pid])
        })

    evidence = []
    for pid in package_ids:
        occ = [x for x in occurrences if x["package_id"] == pid]
        kinds = Counter(x["context_kind"] for x in occ); reasons = []; score = 0
        if any(x["context_kind"] == "DRAW_PACKAGE_CALL_VALUE" for x in occ):
            score += 3; reasons.append("DrawRecord.m_itemPackageId directly carries this value")
        if any(x["context_kind"] == "KEY_OR_ID_CONTEXT" for x in occ):
            score += 2; reasons.append("value also appears in key/id-like field")
        if any(x["context_kind"] == "PACKAGE_NAMED_CONTEXT" for x in occ):
            score += 2; reasons.append("value appears in package-named field")
        if len(usage[pid]["groups"]) > 1:
            score += 1; reasons.append("same package value is reused across multiple Draw groups")
        evidence.append({
            "package_id": pid, "evidence_score": score, "evidence_level": "structural_candidate",
            "reasons": reasons, "context_counts": dict(kinds),
            "group_count": len(usage[pid]["groups"]), "draw_count": len(usage[pid]["draws"]),
            "exact_record_definition_count": len(exact_record_hits[pid])
        })

    write_ndjson(out / "gacha_package_call_occurrences.ndjson", occurrences)
    write_ndjson(out / "gacha_package_parent_context.ndjson", parent_rows)
    write_ndjson(out / "gacha_package_call_usage.ndjson", usage_rows)
    write_ndjson(out / "gacha_package_call_evidence.ndjson", evidence)

    summary = {
        "stage": "6.6", "json_file_count": len(files), "parsed_file_count": len(files) - len(errors),
        "unique_record_ids": len(by_id), "draw_records": len(draws), "unique_item_package_ids": len(package_ids),
        "total_package_id_occurrences": len(occurrences),
        "package_ids_with_exact_record_definition": sum(bool(exact_record_hits[p]) for p in package_ids),
        "package_ids_seen_in_key_or_id_context": sum(any(x["context_kind"] == "KEY_OR_ID_CONTEXT" for x in occurrences if x["package_id"] == p) for p in package_ids),
        "package_ids_seen_in_package_named_context": sum(any(x["context_kind"] == "PACKAGE_NAMED_CONTEXT" for x in occurrences if x["package_id"] == p) for p in package_ids),
        "package_ids_reused_across_multiple_groups": sum(len(usage[p]["groups"]) > 1 for p in package_ids),
        "compound_occurrence_rows": sum(any(x["context_kind"] == "COMPOUND_VALUE_CONTEXT" for x in occurrences if x["package_id"] == p) for p in package_ids),
        "parse_errors": len(errors), "context_counts": dict(contexts),
        "rules": {
            "m_itemPackageId": "opaque call/lookup candidate, not assumed to be a Record ID",
            "network_claim": "not confirmed by JSON alone",
            "lookup_claim": "structural candidate only",
            "id_restore": "hiddenValue XOR currentCryptoKey", "semantic_inference": False
        }
    }
    (out / "04_gacha_package_call_analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Gacha 6.6차 — m_itemPackageId 호출/Lookup 구조 추적", "",
          "## 목적",
          "- m_itemPackageId를 실제 Record ID 연결이라고 고정하지 않고 호출값/lookup key 후보로 추적한다.",
          "- JSON에서 확인 가능한 구조적 evidence와 실제 네트워크 호출 여부를 분리한다.", "",
          "## 결과"]
    md += [f"- {k}: {v}" for k, v in summary.items()]
    md += ["", "## 해석 규칙",
           "- DrawRecord.m_itemPackageId는 우선 opaque key/value로 보존한다.",
           "- JSON만으로 서버 API 호출이라고 확정하지 않는다.",
           "- 동일 값의 key/id/package/array/compound 문맥을 비교한다.",
           "- Package ID가 Record ID와 일치하지 않아도 정상 후보로 유지한다.",
           "- 실제 호출 여부는 코드/디컴파일 데이터에서 caller → parameter → resolver 흐름이 확인될 때 확정한다.",
           "", "## 다음 단계",
           "1. 반복되는 field/parent 구조를 확인한다.",
           "2. 코드/디컴파일 산출물에서 m_itemPackageId, ItemPackage, packageId 계열 사용처를 검색한다.",
           "3. 서버 요청 parameter와 연결되면 API/오프라인 resolver 구조를 복원한다.",
           "4. 연결되지 않으면 클라이언트 local table/index 구조를 우선 조사한다.",
           "5. 이후 Package → Item/Weapon/Fragment/Character/Reward 결과 풀을 복원한다."]
    (out / "gacha_package_call_analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

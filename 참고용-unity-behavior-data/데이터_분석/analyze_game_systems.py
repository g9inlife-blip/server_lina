#!/usr/bin/env python3
"""build_data_graph.py 1차 결과를 이용한 2차 게임 시스템 후보 분석기.

입력은 첫 번째 build_data_graph.py의 output/_work이다.
분석 결과는 원본 데이터와 섞이지 않도록 output/analyze_game_systems/에 저장한다.
후보 Record가 가리키는 원본 JSON은 명칭(name/title/displayName 등) 보강이 필요할 때만 읽는다.
"""

from __future__ import annotations
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")

SYSTEM_PATTERNS = {
    "gacha": ["drawrecord", "drawpreviewrecord", "draw", "gacha", "summon", "banner", "probability", "pool"],
    "item_package": ["itempackage", "package", "itempack"],
    "shop": ["shoprecord", "shop", "store", "purchase", "price", "currency"],
    "reward": ["reward", "rewardrecord", "rewardgroup", "drop"],
    "daily_login": ["daily", "login", "attendance", "checkin", "streak"],
    "achievement": ["achievement", "mission", "quest", "condition"],
    "event": ["event", "limited", "season", "period"],
    "character": ["character", "hero", "actor", "unit"],
    "equipment": ["equipment", "weapon", "armor", "accessory"],
    "skill": ["skill", "passive", "ability"],
    "stage": ["stage", "chapter", "wave", "level"],
    "monster": ["monster", "enemy", "boss", "spawn"],
    "currency": ["currency", "gold", "gem", "coin", "point"],
}

ID_KEY_RE = re.compile(r"(?:^|_)(?:m_)?[a-z0-9]*(?:id|ids)(?:$|_)", re.I)
CODE_VALUE_RE = re.compile(r"^[^|*\s]+\*[^|*\s]+(?:\|[^|*\s]+\*[^|*\s]+)+$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def find_id(obj: dict[str, Any]) -> str | None:
    for k in ("id", "m_id", "_id", "recordid", "record_id"):
        if k in obj:
            v = obj[k]
            if isinstance(v, (int, float, str)) and str(v).strip():
                return str(v).strip()
    return None


def classify_text(text: str) -> list[str]:
    n = norm(text)
    hits = []
    for system, words in SYSTEM_PATTERNS.items():
        if any(norm(w) in n for w in words):
            hits.append(system)
    return hits


def flatten_fields(obj: Any, prefix: str = "$", out: list[tuple[str, Any]] | None = None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}"
            out.append((p, v))
            flatten_fields(v, p, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten_fields(v, f"{prefix}[{i}]", out)
    return out


def collect_records(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        rid = find_id(obj)
        if rid is not None:
            yield path, rid, obj
        for k, v in obj.items():
            yield from collect_records(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from collect_records(v, f"{path}[{i}]")


def candidate_for_record(path: str, rid: str, obj: dict[str, Any], source_file: str):
    field_names = [str(k) for k in obj.keys()]
    text = " ".join(field_names + [path, source_file])
    systems = classify_text(text)
    code_values = []
    pipe_lists = []
    id_refs = []
    for fp, value in flatten_fields(obj):
        if isinstance(value, str):
            if CODE_VALUE_RE.fullmatch(value.strip()):
                code_values.append({"field": fp, "raw_value": value})
            if "|" in value and "*" not in value:
                parts = [x.strip() for x in value.split("|") if x.strip()]
                if len(parts) >= 2:
                    pipe_lists.append({"field": fp, "items": parts})
        key = fp.rsplit(".", 1)[-1]
        if ID_KEY_RE.search(key.lower()) and key.lower() not in {"id", "m_id", "_id", "recordid", "record_id"}:
            id_refs.append({"field": fp, "value": value})
    return {
        "id": rid,
        "source_file": source_file,
        "path": path,
        "systems": systems,
        "field_names": field_names,
        "reference_like_fields": id_refs,
        "code_value_fields": code_values,
        "pipe_id_fields": pipe_lists,
    }


def collect_name_values(
    obj: Any,
    prefix: str = "$",
    out: list[dict[str, Any]] | None = None,
    source_file: str = "",
):
    """Record 명칭 후보를 추출한다.

    Word__krRecord.json 계열은 m_name이 아니라 m_cn을 한국어 명칭으로 사용한다.
    따라서 해당 파일에서는 m_name을 이름 후보로 취급하지 않고 m_cn을 우선/전용으로 추출한다.
    """
    if out is None:
        out = []

    is_kr_record = bool(re.search(r"__krRecord\.json$", Path(source_file).name, re.I))

    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()

            if isinstance(value, str) and value.strip():
                if is_kr_record:
                    if key_l == "m_cn":
                        out.append({
                            "field": f"{prefix}.{key}",
                            "value": value.strip(),
                            "name_source": "m_cn",
                            "language": "ko",
                        })
                elif any(token in key_l for token in (
                    "name", "title", "display", "label", "desc", "description"
                )):
                    out.append({
                        "field": f"{prefix}.{key}",
                        "value": value.strip(),
                        "name_source": key,
                    })

            collect_name_values(value, f"{prefix}.{key}", out, source_file)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            collect_name_values(value, f"{prefix}[{i}]", out, source_file)

    return out


def get_json_path(obj: Any, path: str) -> Any:
    """build_data_graph.py의 $/foo[0]/bar 형태 Record path를 따라간다."""
    if path == "$":
        return obj
    current = obj
    tokens = re.findall(r"\.([^.\[\]]+)|\[(\d+)\]", path[1:])
    for key, index in tokens:
        if index:
            if not isinstance(current, list):
                return None
            current = current[int(index)]
        else:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
    return current


def read_ndjson(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"필수 1차 분석 파일이 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line=line.strip()
            if not line:
                continue
            try:
                row=json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"NDJSON 파싱 오류: {path} line {line_no}: {exc}") from exc
            if isinstance(row, dict):
                yield row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--work-dir",
        type=Path,
        default=Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\데이터_분석\output\_work"),
        help="build_data_graph.py가 생성한 첫 번째 _work 결과 경로",
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="명칭 보강에 사용할 원본 JSON 루트. 분석의 기준 데이터는 여전히 --work-dir이다.",
    )
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    work = args.work_dir.resolve()
    # 원본 output과 섞이지 않도록 2차 분석 전용 하위 폴더에 저장한다.
    out = (args.output or script_dir / "output" / "analyze_game_systems").resolve()
    out.mkdir(parents=True, exist_ok=True)
    out_work = out / "_work"
    out_work.mkdir(parents=True, exist_ok=True)

    required = [
        "records.ndjson",
        "references.ndjson",
        "unresolved.ndjson",
        "structured_code_values.ndjson",
        "structured_multi_ids.ndjson",
    ]
    missing = [name for name in required if not (work / name).exists()]
    if missing:
        raise SystemExit(
            "[오류] build_data_graph.py 1차 _work 결과가 완전하지 않습니다.\n"
            f"입력 경로: {work}\n"
            f"누락 파일: {', '.join(missing)}"
        )

    records = defaultdict(list)
    record_count = 0
    for row in read_ndjson(work / "records.ndjson"):
        rid = str(row.get("id", "")).strip()
        if rid:
            records[rid].append(row)
            record_count += 1

    candidates = {}
    system_counts = Counter()
    field_counts = Counter()

    def get_candidate(rid, source_file, source_path):
        key = (rid, source_file, source_path)
        if key not in candidates:
            systems, evidence = classify_text(" ".join([rid, source_file, source_path])), []
            candidates[key] = {
                "id": rid,
                "source_file": source_file,
                "path": source_path,
                "systems": systems,
                "evidence": evidence,
                "reference_count": 0,
                "validated_reference_count": 0,
                "unresolved_reference_count": 0,
                "reference_fields": Counter(),
                "reference_targets": Counter(),
                "structured_code_value_count": 0,
                "structured_code_value_items": 0,
                "structured_multi_id_count": 0,
                "structured_multi_id_items": 0,
                "structured_fields": Counter(),
            }
        return candidates[key]

    for rows in records.values():
        for row in rows:
            get_candidate(str(row["id"]), str(row.get("file", "")), str(row.get("path", "")))

    def apply_evidence(item, row):
        field = str(row.get("field", ""))
        text = " ".join([
            str(row.get("source_file", "")),
            str(row.get("source_path", "")),
            field,
            str(row.get("raw_value", ""))[:1000],
        ])
        systems = classify_text(text)
        for system in systems:
            if system not in item["systems"]:
                item["systems"].append(system)
            system_counts[system] += 1

        field_name = field.rsplit(".", 1)[-1]
        if field_name:
            field_counts[field_name] += 1
        if systems:
            item["evidence"].append({"field": field, "systems": systems, "raw_value": row.get("raw_value")})

    for row in read_ndjson(work / "references.ndjson"):
        item = get_candidate(str(row.get("source_record_id", "")), str(row.get("source_file", "")), str(row.get("source_path", "")))
        item["reference_count"] += 1
        item["validated_reference_count"] += 1
        field_name = str(row.get("field", "")).rsplit(".", 1)[-1]
        if field_name:
            item["reference_fields"][field_name] += 1
        target = str(row.get("target_file", ""))
        if target:
            item["reference_targets"][target] += 1
        apply_evidence(item, row)

    for row in read_ndjson(work / "unresolved.ndjson"):
        item = get_candidate(str(row.get("source_record_id", "")), str(row.get("source_file", "")), str(row.get("source_path", "")))
        item["reference_count"] += 1
        item["unresolved_reference_count"] += 1
        field_name = str(row.get("field", "")).rsplit(".", 1)[-1]
        if field_name:
            item["reference_fields"][field_name] += 1
        apply_evidence(item, row)

    for filename, kind in [
        ("structured_code_values.ndjson", "code"),
        ("structured_multi_ids.ndjson", "multi"),
    ]:
        for row in read_ndjson(work / filename):
            item = get_candidate(str(row.get("source_record_id", "")), str(row.get("source_file", "")), str(row.get("source_path", "")))
            field_name = str(row.get("field", "")).rsplit(".", 1)[-1]
            if field_name:
                item["structured_fields"][field_name] += 1
            count = len(row.get("items", [])) if isinstance(row.get("items"), list) else 0
            if kind == "code":
                item["structured_code_value_count"] += 1
                item["structured_code_value_items"] += count
            else:
                item["structured_multi_id_count"] += 1
                item["structured_multi_id_items"] += count
            apply_evidence(item, row)

    json_cache: dict[str, Any] = {}
    name_errors = []
    for item in candidates.values():
        source_file = str(item["source_file"])
        source_path = str(item["path"])
        if not source_file:
            continue
        if source_file not in json_cache:
            source_path_obj = (args.data_root / source_file).resolve()
            try:
                json_cache[source_file] = load_json(source_path_obj)
            except Exception as exc:
                json_cache[source_file] = None
                name_errors.append({"file": source_file, "error": f"{type(exc).__name__}: {exc}"})
        raw = json_cache.get(source_file)
        record_obj = get_json_path(raw, source_path) if raw is not None else None
        names = collect_name_values(record_obj, source_file=source_file) if record_obj is not None else []
        item["name_candidates"] = names[:50]
        item["has_human_readable_name"] = bool(names)

    inventory = []
    for item in candidates.values():
        inventory.append({
            **item,
            "reference_fields": dict(item["reference_fields"]),
            "reference_targets": dict(item["reference_targets"]),
            "structured_fields": dict(item["structured_fields"]),
            "evidence": item["evidence"][:50],
        })

    gacha = [x for x in inventory if "gacha" in x["systems"]]
    structured = [x for x in inventory if x["structured_code_value_count"] or x["structured_multi_id_count"]]

    with (out_work / "record_system_candidates.ndjson").open("w", encoding="utf-8") as f:
        for row in inventory:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    with (out_work / "gacha_candidates.ndjson").open("w", encoding="utf-8") as f:
        for row in gacha:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    with (out_work / "structured_system_candidates.ndjson").open("w", encoding="utf-8") as f:
        for row in structured:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "input_work_dir": str(work),
        "input_files": required,
        "record_count": record_count,
        "unique_id_count": len(records),
        "candidate_record_count": len(inventory),
        "gacha_candidate_count": len(gacha),
        "structured_candidate_count": len(structured),
        "system_candidate_counts": dict(system_counts.most_common()),
        "top_reference_fields": field_counts.most_common(100),
        "name_enrichment": {
            "data_root": str(args.data_root.resolve()),
            "source_files_loaded": len(json_cache),
            "errors": len(name_errors),
        },
        "notes": [
            "원본 JSON은 이 단계에서 다시 읽지 않는다.",
            "build_data_graph.py의 첫 번째 _work 결과만 입력으로 사용한다.",
            "검증된 Reference와 미해결 Reference를 구분한다.",
            "CODE*VALUE의 두 번째 값은 수량/확률/레벨 등으로 임의 확정하지 않는다.",
            "시스템 분류는 후보 탐색이며 게임 의미를 확정하지 않는다.",
            "Word__krRecord.json 계열은 m_cn을 한국어 명칭으로 사용한다.",
        ],
    }

    (out / "02_record_type_inventory.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 게임 시스템 후보 분석",
        "",
        "## 입력",
        "",
        f"- 1차 build_data_graph _work: {work}",
        "- 원본 JSON 재스캔: 하지 않음",
        "",
        "## 결과",
        "",
        f"- Record: {record_count:,}",
        f"- 고유 ID: {len(records):,}",
        f"- 후보 Record: {len(inventory):,}",
        f"- Gacha 후보: {len(gacha):,}",
        f"- 구조화 후보: {len(structured):,}",
        "",
        "## 시스템 후보 수",
        "",
    ]
    lines.extend(f"- {system}: {count}" for system, count in system_counts.most_common())
    lines += [
        "",
        "## 다음 분석 우선순위",
        "",
        "1. gacha",
        "2. item_package",
        "3. reward",
        "4. shop",
        "5. daily_login",
        "6. achievement",
        "7. event",
        "8. character / equipment / skill",
        "9. stage / monster",
        "",
        "분류 결과는 후보이며 Reference 연결과 반복 구조를 확인한 뒤 의미를 확정한다.",
    ]
    (out / "name_enrichment_errors.json").write_text(json.dumps(name_errors, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out_work / "record_names.ndjson").open("w", encoding="utf-8") as f:
        for item in inventory:
            if item.get("name_candidates"):
                f.write(json.dumps({
                    "id": item["id"],
                    "source_file": item["source_file"],
                    "path": item["path"],
                    "systems": item["systems"],
                    "name_candidates": item["name_candidates"],
                }, ensure_ascii=False, separators=(",", ":")) + "\n")

    (out / "07_system_candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[완료]")
    print(f"  입력 _work: {work}")
    print(f"  Record: {record_count:,}")
    print(f"  고유 ID: {len(records):,}")
    print(f"  후보 Record: {len(inventory):,}")
    print(f"  Gacha 후보: {len(gacha):,}")
    print(f"  구조화 후보: {len(structured):,}")
    print(f"  결과: {out}")


if __name__ == "__main__":
    main()

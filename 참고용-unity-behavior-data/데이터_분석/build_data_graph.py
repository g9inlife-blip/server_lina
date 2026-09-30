#!/usr/bin/env python3
"""
참고용-unity-behavior-data 자동 참조 그래프 분석기.

Python은 사실 추출/검증을 담당하고, 의미 해석은 별도 단계에서 수행한다.
API/Response/Research 구조는 생성하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")

ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}

REFERENCE_KEY_RE = re.compile(
    r"(?:^|_)(?:m_)?[a-z0-9]*?(?:id|ids)(?:$|_)",
    re.IGNORECASE,
)

MULTI_VALUE_RE = re.compile(
    r"(?P<id>[A-Za-z0-9_:.\\-]+)\s*[xX*]\s*(?P<count>\d+)"
)

CODE_VALUE_PAIR_RE = re.compile(
    r"^(?P<code>[^|*\s]+)\s*\*\s*(?P<value>[^|*\s]+)$"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def safe_load_json(path: Path, parse_errors: list[dict[str, str]]) -> Any | None:
    try:
        return load_json(path)
    except Exception as exc:
        parse_errors.append({
            "file": str(path),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return None


def decode_obscured_int(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    if "hiddenValue" not in value or "currentCryptoKey" not in value:
        return None
    hidden = value.get("hiddenValue")
    key = value.get("currentCryptoKey")
    if isinstance(hidden, int) and isinstance(key, int):
        return hidden ^ key
    return None


def is_id_key(key: str) -> bool:
    return str(key).lower() in ID_KEYS


REFERENCE_EXCLUDED_KEYS = {
    "id", "m_id", "_id", "recordid", "record_id",
    "fileid", "m_fileid", "pathid", "m_pathid",
}


def looks_like_reference_key(key: str) -> bool:
    normalized = str(key).lower()
    if normalized in REFERENCE_EXCLUDED_KEYS:
        return False
    return bool(REFERENCE_KEY_RE.search(normalized))


def parse_pipe_id_list(value: Any) -> list[str]:
    """ID|ID|ID 형태의 단순 다중 ID 목록을 분해한다.

    예:
        45080210|45080211|45080212|45080213

    *가 포함된 CODE*VALUE 구조는 여기서 제외한다.
    """
    if not isinstance(value, str):
        return []

    raw = value.strip()
    if "|" not in raw or "*" in raw:
        return []

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 2 or any(not part for part in parts):
        return []

    return parts


def parse_code_value_list(value: Any) -> list[dict[str, Any]]:
    """CODE*VALUE|CODE*VALUE 형태를 구조화한다."""
    if not isinstance(value, str):
        return []

    raw = value.strip()
    if "|" not in raw or "*" not in raw:
        return []

    parts = [part.strip() for part in raw.split("|") if part.strip()]
    if not parts:
        return []

    parsed: list[dict[str, Any]] = []
    for index, part in enumerate(parts):
        match = CODE_VALUE_PAIR_RE.fullmatch(part)
        if not match:
            return []

        parsed.append({
            "code": match.group("code"),
            "value": match.group("value"),
            "index": index,
        })

    return parsed


def scalar_candidates(value: Any) -> list[str]:
    if value is None or isinstance(value, bool):
        return []

    decoded = decode_obscured_int(value)
    if decoded is not None:
        return [str(decoded)]

    if isinstance(value, (int, float)):
        return [str(value)]

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []

        match = MULTI_VALUE_RE.fullmatch(value)
        if match:
            return [match.group("id")]

        code_values = parse_code_value_list(value)
        if code_values:
            # code만 Reference 후보로 연결하고 value는 ID로 취급하지 않는다.
            return [item["code"] for item in code_values]

        pipe_ids = parse_pipe_id_list(value)
        if pipe_ids:
            return pipe_ids

        if "," in value or ";" in value:
            return [x.strip() for x in re.split(r"[,;]", value) if x.strip()]

        return [value]

    return []


def find_id_in_record(obj: dict[str, Any]) -> str | None:
    for key, value in obj.items():
        if is_id_key(str(key)):
            candidates = scalar_candidates(value)
            if candidates:
                return candidates[0]
    return None


def iter_records(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        record_id = find_id_in_record(obj)
        if record_id is not None:
            yield path, obj, record_id
        for key, value in obj.items():
            yield from iter_records(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_records(value, f"{path}[{i}]")


def extract_references(record: dict[str, Any], source_file: str, record_path: str,
                       record_id: str, max_refs: int = 100_000):
    refs = []
    seen = set()

    def append_ref(field_path: str, raw: Any, candidate: str):
        if len(refs) >= max_refs:
            raise RuntimeError(
                f"Reference 폭증 감지: {source_file} / {record_path} "
                f"(한 Record에서 {max_refs:,}개 초과)"
            )

        dedupe_key = (field_path, str(candidate), json.dumps(
            raw, ensure_ascii=False, sort_keys=True, default=str
        ))
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)

        refs.append({
            "source_file": source_file,
            "source_record_id": record_id,
            "source_path": record_path,
            "field": field_path,
            "raw_value": raw,
            "candidate_id": str(candidate),
        })

    def walk(obj: Any, field_path: str, is_root: bool = False):
        if isinstance(obj, dict):
            if not is_root and find_id_in_record(obj) is not None:
                return

            for key, value in obj.items():
                key_s = str(key)
                next_path = f"{field_path}.{key_s}"

                if looks_like_reference_key(key_s):
                    values = value if isinstance(value, list) else [value]
                    for raw in values:
                        candidates = scalar_candidates(raw)
                        if not candidates and isinstance(raw, dict):
                            nested_id = find_id_in_record(raw)
                            if nested_id:
                                candidates = [nested_id]

                        for candidate in candidates:
                            append_ref(next_path, raw, candidate)

                walk(value, next_path)

        elif isinstance(obj, list):
            for i, child in enumerate(obj):
                walk(child, f"{field_path}[{i}]")

    walk(record, "$", is_root=True)
    return refs


def json_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def write_json(path: Path, data: Any):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_jsonl(handle, obj: Any):
    handle.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl_ids(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=None,
                        help="분석할 데이터 루트. 기본값은 로컬 Unity JSON 경로.")
    parser.add_argument("--output", type=Path, default=None,
                        help="결과 폴더. 기본값은 데이터_분석/output.")
    parser.add_argument("--max-refs-per-record", type=int, default=100_000,
                        help="Record 하나에서 허용할 최대 Reference 후보 수. 초과하면 중단한다.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_root = (args.data_root or DEFAULT_DATA_ROOT).resolve()
    output_dir = (args.output or script_dir / "output").resolve()

    if not data_root.exists():
        raise SystemExit(
            "[오류] JSON 데이터 경로를 찾을 수 없습니다:\n"
            f"{data_root}\n\n"
            "필요하면 --data-root 옵션으로 경로를 지정하세요."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(data_root.rglob("*.json"))
    json_files = [p for p in json_files if output_dir not in p.parents]

    record_file = work_dir / "records.ndjson"
    ref_file = work_dir / "references.ndjson"
    unresolved_file = work_dir / "unresolved.ndjson"
    parse_error_file = work_dir / "parse_errors.ndjson"
    structured_file = work_dir / "structured_code_values.ndjson"
    multi_id_file = work_dir / "structured_multi_ids.ndjson"

    record_count = 0
    parse_error_count = 0
    file_inventory = []

    print(f"[시작] JSON 파일: {len(json_files)}")
    print(f"[경로] {data_root}")
    print("[1/2] Record ID 추출 중...")

    with record_file.open("w", encoding="utf-8") as records_out,          parse_error_file.open("w", encoding="utf-8") as errors_out:
        for index, path in enumerate(json_files, 1):
            rel = json_rel(path, data_root)
            local_errors = []
            data = safe_load_json(path, local_errors)
            if data is None:
                parse_error_count += len(local_errors)
                for err in local_errors:
                    append_jsonl(errors_out, err)
                print(f"[{index}/{len(json_files)}] SKIP {rel} (JSON 오류)")
                continue

            records = 0
            for record_path, record, record_id in iter_records(data):
                append_jsonl(records_out, {
                    "id": str(record_id),
                    "file": rel,
                    "path": record_path,
                })
                records += 1
                record_count += 1

            file_inventory.append({
                "file": rel,
                "json_type": type(data).__name__,
                "record_count": records,
            })
            print(f"[{index}/{len(json_files)}] {rel} | Record {records}")
            del data

    id_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in read_jsonl_ids(record_file):
        id_index[item["id"]].append({
            "file": item["file"],
            "path": item["path"],
        })

    duplicate_ids = [
        {"id": key, "locations": locations}
        for key, locations in sorted(id_index.items())
        if len(locations) > 1
    ]

    print(f"[중간] 고유 ID: {len(id_index)} / 중복 ID: {len(duplicate_ids)}")
    print("[2/2] 참조 추출 및 구조화 데이터 추출 중...")

    valid_count = 0
    unresolved_count = 0
    structured_count = 0
    structured_item_count = 0
    multi_id_count = 0
    multi_id_item_count = 0
    field_stats = Counter()
    source_stats = Counter()
    target_stats = Counter()
    structured_field_stats = Counter()
    multi_id_field_stats = Counter()

    with ref_file.open("w", encoding="utf-8") as refs_out,          unresolved_file.open("w", encoding="utf-8") as unresolved_out,          structured_file.open("w", encoding="utf-8") as structured_out,          multi_id_file.open("w", encoding="utf-8") as multi_id_out,          parse_error_file.open("a", encoding="utf-8") as errors_out:

        for index, path in enumerate(json_files, 1):
            rel = json_rel(path, data_root)
            local_errors = []
            data = safe_load_json(path, local_errors)

            if data is None:
                parse_error_count += len(local_errors)
                for err in local_errors:
                    append_jsonl(errors_out, err)
                continue

            file_refs = 0
            file_valid = 0
            file_unresolved = 0
            file_structured = 0
            file_structured_items = 0
            file_multi_ids = 0
            file_multi_id_items = 0

            for record_path, record, record_id in iter_records(data):
                for ref in extract_references(
                    record, rel, record_path, str(record_id),
                    max_refs=args.max_refs_per_record,
                ):
                    file_refs += 1
                    matches = id_index.get(str(ref["candidate_id"]), [])

                    if matches:
                        for target in matches:
                            append_jsonl(refs_out, {
                                **ref,
                                "target_file": target["file"],
                                "target_path": target["path"],
                            })
                            valid_count += 1
                            file_valid += 1
                            source_stats[rel] += 1
                            target_stats[target["file"]] += 1
                            field_stats[ref["field"].split(".")[-1]] += 1
                    else:
                        append_jsonl(unresolved_out, {
                            **ref,
                            "target_matches": [],
                        })
                        unresolved_count += 1
                        file_unresolved += 1

                def walk_structured(obj: Any, field_path: str):
                    nonlocal structured_count, structured_item_count
                    nonlocal multi_id_count, multi_id_item_count
                    nonlocal file_structured, file_structured_items
                    nonlocal file_multi_ids, file_multi_id_items

                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            next_path = f"{field_path}.{key}"

                            parsed = parse_code_value_list(value)
                            if parsed:
                                append_jsonl(structured_out, {
                                    "source_file": rel,
                                    "source_record_id": str(record_id),
                                    "source_path": record_path,
                                    "field": next_path,
                                    "raw_value": value,
                                    "format": "code_value_pipe",
                                    "items": parsed,
                                })
                                structured_count += 1
                                file_structured += 1
                                structured_item_count += len(parsed)
                                file_structured_items += len(parsed)
                                structured_field_stats[str(key)] += 1

                            parsed_ids = parse_pipe_id_list(value)
                            if parsed_ids:
                                append_jsonl(multi_id_out, {
                                    "source_file": rel,
                                    "source_record_id": str(record_id),
                                    "source_path": record_path,
                                    "field": next_path,
                                    "raw_value": value,
                                    "format": "id_pipe_list",
                                    "items": [
                                        {"id": item, "index": i}
                                        for i, item in enumerate(parsed_ids)
                                    ],
                                })
                                multi_id_count += 1
                                file_multi_ids += 1
                                multi_id_item_count += len(parsed_ids)
                                file_multi_id_items += len(parsed_ids)
                                multi_id_field_stats[str(key)] += 1

                            walk_structured(value, next_path)

                    elif isinstance(obj, list):
                        for i, child in enumerate(obj):
                            walk_structured(child, f"{field_path}[{i}]")

                walk_structured(record, "$")

            if file_refs > 2_000_000:
                raise SystemExit(
                    f"[중단] Reference 폭증 감지: {rel} -> {file_refs:,}개. "
                    "extract_references 로직을 확인하세요."
                )

            print(
                f"[{index}/{len(json_files)}] {rel} | "
                f"Ref {file_refs:,} / OK {file_valid:,} / 미해결 {file_unresolved:,} | "
                f"CODE*VALUE {file_structured:,}개 / 항목 {file_structured_items:,}개 | "
                f"ID|ID {file_multi_ids:,}개 / 항목 {file_multi_id_items:,}개"
            )
            del data

    summary = {
        "data_root": str(data_root),
        "json_file_count": len(json_files),
        "parsed_file_count": len(file_inventory),
        "parse_error_count": parse_error_count,
        "record_count": record_count,
        "unique_id_count": len(id_index),
        "duplicate_id_count": len(duplicate_ids),
        "reference_candidate_count": valid_count + unresolved_count,
        "validated_reference_count": valid_count,
        "unresolved_reference_count": unresolved_count,
        "structured_code_value_count": structured_count,
        "structured_code_value_item_count": structured_item_count,
        "structured_multi_id_count": multi_id_count,
        "structured_multi_id_item_count": multi_id_item_count,
        "top_source_files": source_stats.most_common(30),
        "top_target_files": target_stats.most_common(30),
        "top_reference_fields": field_stats.most_common(50),
        "top_structured_code_value_fields": structured_field_stats.most_common(50),
        "top_structured_multi_id_fields": multi_id_field_stats.most_common(50),
        "reference_extraction_rules": {
            "record_id_keys": sorted(ID_KEYS),
            "excluded_reference_keys": sorted(REFERENCE_EXCLUDED_KEYS),
            "max_refs_per_record": args.max_refs_per_record,
            "nested_record_boundary": True,
            "pipe_id_list": "ID|ID|ID values are split into individual reference candidates",
        },
        "structured_value_rules": {
            "code_value_format": "CODE*VALUE|CODE*VALUE",
            "code_value_separator": "*",
            "item_separator": "|",
            "value_semantics": "preserve_as_value_until_semantic_analysis",
            "output": "_work/structured_code_values.ndjson",
            "multi_id_format": "ID|ID|ID",
            "multi_id_output": "_work/structured_multi_ids.ndjson",
        },
    }

    write_json(output_dir / "04_duplicate_ids.json", duplicate_ids)
    write_json(output_dir / "05_reference_summary.json", summary)

    with (output_dir / "01_record_inventory.json").open("w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "files": file_inventory,
            "record_data_file": str(record_file),
            "reference_data_file": str(ref_file),
            "unresolved_data_file": str(unresolved_file),
            "structured_code_value_file": str(structured_file),
            "structured_multi_id_file": str(multi_id_file),
            "parse_errors_file": str(parse_error_file),
        }, f, ensure_ascii=False, indent=2)

    graph_md = output_dir / "06_data_graph.md"
    lines = [
        "# 실제 데이터 참조 그래프 분석 결과", "",
        f"- 분석 대상: {data_root}",
        f"- JSON: {summary['json_file_count']}개",
        f"- Record: {summary['record_count']}개",
        f"- 고유 ID: {summary['unique_id_count']}개",
        f"- 검증된 참조: {summary['validated_reference_count']}개",
        f"- 미해결 참조: {summary['unresolved_reference_count']}개",
        f"- CODE*VALUE 구조: {summary['structured_code_value_count']}개",
        f"- CODE*VALUE 항목: {summary['structured_code_value_item_count']}개",
        f"- ID|ID 다중 목록: {summary['structured_multi_id_count']}개",
        f"- ID|ID 다중 목록 항목: {summary['structured_multi_id_item_count']}개",
        f"- 중복 ID: {summary['duplicate_id_count']}개",
        f"- JSON 파싱 오류: {summary['parse_error_count']}개", "",
        "## 대용량 원본 결과", "",
        "- _work/records.ndjson: Record ID 목록",
        "- _work/references.ndjson: 검증된 참조",
        "- _work/unresolved.ndjson: 미해결 참조",
        "- _work/structured_code_values.ndjson: CODE*VALUE|CODE*VALUE 구조",
        "- _work/structured_multi_ids.ndjson: ID|ID|ID 다중 ID 구조",
        "- _work/parse_errors.ndjson: 파일별 파싱 오류", "",
        "## 주요 참조 필드", "",
    ]

    for field, count in field_stats.most_common(50):
        lines.append(f"- {field} : {count}")

    lines += ["", "## 주요 CODE*VALUE 필드", ""]
    for field, count in structured_field_stats.most_common(50):
        lines.append(f"- {field} : {count}")

    lines += ["", "## 주요 ID|ID 다중 목록 필드", ""]
    for field, count in multi_id_field_stats.most_common(50):
        lines.append(f"- {field} : {count}")

    lines += ["", "## 주요 출발 파일", ""]
    for file_name, count in source_stats.most_common(30):
        lines.append(f"- {file_name} : {count}")

    lines += ["", "## 주요 대상 파일", ""]
    for file_name, count in target_stats.most_common(30):
        lines.append(f"- {file_name} : {count}")

    lines += [
        "", "## 해석 주의", "",
        "- Python은 JSON 원본에서 기계적으로 ID, Reference, CODE*VALUE, ID|ID 구조를 추출한다.",
        "- ID|ID|ID 문자열은 각 항목을 개별 Reference 후보로 취급한다.",
        "- CODE*VALUE의 두 번째 값은 수량/확률/레벨 등으로 임의 확정하지 않고 원본 value로 보존한다.",
        "- 대용량 참조는 메모리에 누적하지 않고 NDJSON 파일에 순차 기록한다.",
        "- 필드명이 ID처럼 보여도 게임 의미가 확정되는 것은 아니다.",
        "- Response/API/Research 구조는 이 단계에서 생성하지 않는다.",
    ]
    graph_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print("[완료]")
    print(f"  JSON: {len(json_files)}")
    print(f"  Record: {record_count}")
    print(f"  고유 ID: {len(id_index)}")
    print(f"  검증된 참조: {valid_count}")
    print(f"  미해결 참조: {unresolved_count}")
    print(f"  CODE*VALUE 구조: {structured_count}")
    print(f"  CODE*VALUE 항목: {structured_item_count}")
    print(f"  ID|ID 다중 목록: {multi_id_count}")
    print(f"  ID|ID 다중 목록 항목: {multi_id_item_count}")
    print(f"  중복 ID: {len(duplicate_ids)}")
    print(f"  JSON 오류: {parse_error_count}")
    print(f"[결과] {output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze server_lina.code_mapping.v1 code_catalog.json.

The input catalog is expected to contain:
  {"schema": "...", "record_count": N, "records": [...]}

Outputs:
  code_catalog_analysis.json
  code_catalog_analysis.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_catalog(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("invalid code_catalog.json: records[] not found")
    return data


def as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.isdigit():
            return int(s)
    return None


def code_family(network_id: int) -> dict[str, Any]:
    s = str(network_id)
    # Known mapping convention: 1xxxxxxx, 2xxxxxxx, 3xxxxxxx ... -> base xxxxxxx.
    # Only treat a leading family digit as such for IDs with at least 2 digits.
    if len(s) >= 2 and s[0].isdigit() and s[0] in "123456789":
        return {
            "family": int(s[0]),
            "base_code": int(s[1:]),
            "raw_length": len(s),
        }
    return {"family": None, "base_code": network_id, "raw_length": len(s)}


def pct(n: int, d: int) -> float:
    return round((n / d * 100.0), 4) if d else 0.0


def top_dict(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [{"key": k, "count": v} for k, v in counter.most_common(limit)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    data = load_catalog(args.input)
    records = data["records"]
    total = len(records)

    zero_records = []
    valid_records = []
    id_counter: Counter[int] = Counter()
    source_counter: Counter[str] = Counter()
    table_counter: Counter[str] = Counter()
    field_counter: Counter[str] = Counter()
    family_counter: Counter[int | str] = Counter()
    family_bases: dict[int, set[int]] = defaultdict(set)
    base_variants: dict[int, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    network_sources: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for rec in records:
        nid = as_int(rec.get("network_id"))
        if nid is None:
            continue

        id_counter[nid] += 1
        sources = rec.get("sources") or []
        if nid == 0:
            zero_records.append(rec)
        else:
            valid_records.append(rec)

        for src in sources:
            if not isinstance(src, dict):
                continue
            fn = str(src.get("file", ""))
            path = str(src.get("path", ""))
            source_counter[fn] += 1
            if path:
                # First component generally identifies the Unity table.
                table = path.split(".", 1)[0]
                table_counter[table] += 1

        # Count catalog value fields that are present.
        for k in rec.keys():
            if k not in {"network_id", "sources"}:
                field_counter[k] += 1

        if nid > 0:
            fam = code_family(nid)
            if fam["family"] is None:
                family_counter["none"] += 1
            else:
                family_counter[fam["family"]] += 1
                family_bases[fam["family"]].add(fam["base_code"])
                base_variants[fam["base_code"]][fam["family"]].add(nid)

            network_sources[nid].extend(
                s for s in sources if isinstance(s, dict)
            )

    duplicate_ids = {nid: count for nid, count in id_counter.items() if count > 1}
    multi_source = sorted(
        (
            {
                "network_id": nid,
                "source_count": len(srcs),
                "sources": srcs[:args.top],
            }
            for nid, srcs in network_sources.items()
            if len(srcs) > 1
        ),
        key=lambda x: (-x["source_count"], x["network_id"]),
    )

    # A family group is useful only when multiple family variants exist.
    family_groups = []
    for base, variants in base_variants.items():
        fams = sorted(variants)
        if len(fams) >= 2:
            family_groups.append(
                {
                    "base_code": base,
                    "families": fams,
                    "variant_count": len(fams),
                    "variants": {
                        str(f): sorted(variants[f]) for f in fams
                    },
                }
            )
    family_groups.sort(key=lambda x: (-x["variant_count"], x["base_code"]))

    analysis = {
        "schema": "server_lina.code_mapping.analysis.v1",
        "input": str(args.input),
        "catalog_schema": data.get("schema"),
        "catalog_record_count": data.get("record_count"),
        "actual_record_count": total,
        "record_count_matches_catalog": data.get("record_count") == total,
        "network_id": {
            "records_with_numeric_id": sum(id_counter.values()),
            "network_id_zero_count": len(zero_records),
            "network_id_zero_percent": pct(len(zero_records), total),
            "valid_positive_count": len(valid_records),
            "valid_positive_percent": pct(len(valid_records), total),
            "unique_id_count": len(id_counter),
            "duplicate_id_value_count": len(duplicate_ids),
            "duplicate_record_count": sum(
                c for c in id_counter.values() if c > 1
            ),
            "min_positive_id": min((n for n in id_counter if n > 0), default=None),
            "max_positive_id": max((n for n in id_counter if n > 0), default=None),
        },
        "zero_id": {
            "count": len(zero_records),
            "top_files": top_dict(
                Counter(
                    s.get("file", "")
                    for r in zero_records
                    for s in (r.get("sources") or [])
                    if isinstance(s, dict)
                ),
                args.top,
            ),
            "top_tables": top_dict(
                Counter(
                    str(s.get("path", "")).split(".", 1)[0]
                    for r in zero_records
                    for s in (r.get("sources") or [])
                    if isinstance(s, dict) and s.get("path")
                ),
                args.top,
            ),
            "sample_records": zero_records[:20],
        },
        "duplicates": {
            "count": len(duplicate_ids),
            "top": [
                {"network_id": nid, "record_count": count}
                for nid, count in sorted(
                    duplicate_ids.items(),
                    key=lambda x: (-x[1], x[0]),
                )[:args.top]
            ],
        },
        "source_distribution": top_dict(source_counter, args.top),
        "table_distribution": top_dict(table_counter, args.top),
        "field_distribution": top_dict(field_counter, args.top),
        "code_family": {
            "distribution": [
                {"family": k, "record_count": v}
                for k, v in sorted(
                    family_counter.items(),
                    key=lambda x: str(x[0]),
                )
            ],
            "unique_base_count_by_family": {
                str(k): len(v) for k, v in sorted(family_bases.items())
            },
            "multi_family_base_count": len(family_groups),
            "multi_family_examples": family_groups[:args.top],
        },
        "network_ids_with_multiple_sources": {
            "count": len(multi_source),
            "top": multi_source[:args.top],
        },
        "top_network_ids_by_source_count": [
            {
                "network_id": nid,
                "source_count": len(srcs),
                "sources": srcs[:args.top],
            }
            for nid, srcs in sorted(
                network_sources.items(),
                key=lambda x: (-len(x[1]), x[0]),
            )[:args.top]
        ],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    json_out = args.output / "code_catalog_analysis.json"
    csv_out = args.output / "code_catalog_analysis.csv"
    json_out.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with csv_out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["network_id", "record_count", "family", "base_code", "source_count"])
        for nid, count in sorted(id_counter.items()):
            if nid <= 0:
                fam, base = "", nid
            else:
                cf = code_family(nid)
                fam, base = cf["family"], cf["base_code"]
            w.writerow([nid, count, fam, base, len(network_sources.get(nid, []))])

    print(f"input={args.input}")
    print(f"records={total}")
    print(f"network_id=0={len(zero_records)} ({pct(len(zero_records), total)}%)")
    print(f"valid_positive={len(valid_records)} ({pct(len(valid_records), total)}%)")
    print(f"unique_ids={len(id_counter)}")
    print(f"duplicate_id_values={len(duplicate_ids)}")
    print(f"multi_family_bases={len(family_groups)}")
    print(f"wrote={json_out}")
    print(f"wrote={csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

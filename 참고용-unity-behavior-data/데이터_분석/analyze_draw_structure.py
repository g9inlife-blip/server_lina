#!/usr/bin/env python3
"""4차 Gacha/Draw 구조 분석기.

원본 Unity JSON을 스캔하여 DrawRecord/DrawPreviewRecord와
ItemPackage/Item/Reward/Currency/Event 후보의 실제 Reference 구조를 조사한다.
확률/수량/가격의 의미는 숫자만으로 확정하지 않고 evidence를 보존한다.
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")
ID_KEYS = {"id", "m_id", "_id", "recordid", "record_id"}
PROB_RE = re.compile(r"(prob|probability|rate|weight|percent|percentage|ratio|chance|odds)", re.I)
COST_RE = re.compile(r"(cost|price|consume|currency|ticket|point|gem|diamond|coin|gold|paid|fee)", re.I)
PERIOD_RE = re.compile(r"(start|end|begin|finish|from|to|open|close|date|time|duration|period)", re.I)
PITY_RE = re.compile(r"(pity|guarantee|ceiling|assure|protect)", re.I)
COUNT_RE = re.compile(r"(count|num|number|amount|quantity|qty|times)", re.I)

def load(p: Path):
    with p.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def scalar(v):
    if isinstance(v, dict) and isinstance(v.get("hiddenValue"), int) and isinstance(v.get("currentCryptoKey"), int):
        return str(v["hiddenValue"] ^ v["currentCryptoKey"])
    if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
        return str(v).strip()
    return None

def rid(o):
    if not isinstance(o, dict):
        return None
    for k, v in o.items():
        if str(k).lower() in ID_KEYS:
            x = scalar(v)
            if x:
                return x
    return None

def walk(o, path="$"):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")

def flatten(o, prefix="$"):
    # obscured ID object ({hiddenValue,currentCryptoKey}) is an atomic value.
    # Yield it before recursive descent so ID references inside lists/dicts are preserved.
    if scalar(o) is not None:
        yield prefix, o
        return
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flatten(v, f"{prefix}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from flatten(v, f"{prefix}[{i}]")

def file_types(name):
    n = name.lower()
    out = []
    if "drawpreviewrecord" in n or "drawpreview" in n:
        out.append("DrawPreviewRecord")
    elif "drawrecord" in n:
        out.append("DrawRecord")
    if "itempackage" in n or "itempack" in n:
        out.append("ItemPackage")
    if "itemrecord" in n:
        out.append("Item")
    if "rewardrecord" in n or "rewardgroup" in n:
        out.append("Reward")
    if any(x in n for x in ("currency", "currencyrecord", "wallet")):
        out.append("Currency")
    if any(x in n for x in ("event", "season", "limited")):
        out.append("Event")
    return out

def kr_name(obj, file):
    if not isinstance(obj, dict):
        return None
    if re.search(r"__krRecord\.json$", Path(file).name, re.I):
        v = obj.get("m_cn")
        return v.strip() if isinstance(v, str) and v.strip() else None
    return None

def classify_field(field):
    key = field.rsplit(".", 1)[-1].lower()
    tags = []
    if PROB_RE.search(key):
        tags.append("probability_candidate")
    if COST_RE.search(key):
        tags.append("cost_candidate")
    if PERIOD_RE.search(key):
        tags.append("period_candidate")
    if PITY_RE.search(key):
        tags.append("pity_candidate")
    if COUNT_RE.search(key):
        tags.append("quantity_candidate")
    return tags

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--output", type=Path, default=None)
    a = ap.parse_args()
    root = a.data_root.resolve()
    base = Path(__file__).resolve().parent
    out = (a.output or base / "output" / "system_mapping" / "gacha").resolve()
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(root.rglob("*.json"))
    index = defaultdict(list)
    parsed = 0
    errors = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            data = load(p)
            parsed += 1
        except Exception as e:
            errors.append({"file": rel, "error": f"{type(e).__name__}: {e}"})
            continue
        for path, obj in walk(data):
            x = rid(obj)
            if x is not None:
                index[x].append({
                    "id": x, "file": rel, "path": path,
                    "types": file_types(rel), "object": obj
                })

    def targets(obj):
        result = []
        for field, v in flatten(obj):
            key = field.rsplit(".", 1)[-1]
            if not re.search(r"(id|ids|item|package|reward|draw|pool|currency|cost|ticket|price)", key, re.I):
                continue
            s = scalar(v)
            if s is None:
                continue
            for part in re.split(r"[|,;]", s):
                part = part.strip()
                if part and part in index:
                    for t in index[part]:
                        result.append({
                            "field": field,
                            "target_id": part,
                            "target_file": t["file"],
                            "target_path": t["path"],
                            "target_types": t["types"]
                        })
        # target_types는 list이므로 tuple(r.items())로 set key를 만들면
        # TypeError가 발생한다. JSON canonical 문자열을 dedupe key로 사용한다.
        seen = set()
        out2 = []
        for r in result:
            k = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if k not in seen:
                seen.add(k)
                out2.append(r)
        return out2

    draws = []
    prob = []
    costs = []
    periods = []
    unresolved = []
    counts = Counter()
    target_types = Counter()
    field_counts = Counter()

    draw_entries = []
    for entries in index.values():
        for e in entries:
            if "DrawRecord" in e["types"] or "DrawPreviewRecord" in e["types"]:
                draw_entries.append(e)

    for e in draw_entries:
        obj = e["object"]
        edges = targets(obj)
        direct_types = Counter()
        for edge in edges:
            for t in edge["target_types"]:
                direct_types[t] += 1
                target_types[t] += 1

        row = {
            "id": e["id"],
            "record_type": e["types"],
            "source_file": e["file"],
            "path": e["path"],
            "name_ko": kr_name(obj, e["file"]),
            "fields": list(obj.keys()),
            "edges": edges,
            "direct_target_types": dict(direct_types)
        }
        draws.append(row)
        counts.update(e["types"])

        for field, value in flatten(obj):
            tags = classify_field(field)
            if not tags:
                continue
            item = {
                "id": e["id"],
                "record_type": e["types"],
                "source_file": e["file"],
                "path": e["path"],
                "field": field,
                "raw_value": value,
                "tags": tags
            }
            field_counts[field.rsplit(".", 1)[-1]] += 1
            if "probability_candidate" in tags:
                prob.append(item)
            if "cost_candidate" in tags:
                costs.append(item)
            if "period_candidate" in tags:
                periods.append(item)

        if not edges:
            unresolved.append({
                "id": e["id"],
                "record_type": e["types"],
                "source_file": e["file"],
                "path": e["path"],
                "reason": "no resolved ID-like reference found"
            })

    def write(name, rows):
        with (out / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")

    write("draw_structure.ndjson", draws)
    write("draw_candidates.ndjson", draws)
    write("draw_unresolved.ndjson", unresolved)
    write("probability_fields.ndjson", prob)
    write("cost_fields.ndjson", costs)
    write("period_fields.ndjson", periods)

    (out / "field_semantics_inventory.json").write_text(
        json.dumps({
            "probability_candidates": len(prob),
            "cost_candidates": len(costs),
            "period_candidates": len(periods),
            "top_fields": field_counts.most_common(100),
            "note": "field name alone does not confirm semantic meaning"
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    summary = {
        "json_file_count": len(files),
        "parsed_file_count": parsed,
        "unique_record_ids": len(index),
        "draw_record_candidates": counts["DrawRecord"],
        "draw_preview_candidates": counts["DrawPreviewRecord"],
        "draw_total_entries": len(draws),
        "resolved_draw_entries": len(draws) - len(unresolved),
        "unresolved_draw_entries": len(unresolved),
        "target_type_counts": dict(target_types),
        "probability_field_occurrences": len(prob),
        "cost_field_occurrences": len(costs),
        "period_field_occurrences": len(periods),
        "parse_errors": len(errors),
        "rules": {
            "obscured_id": "hiddenValue XOR currentCryptoKey",
            "kr_name_field": "m_cn",
            "semantic_inference": False
        }
    }

    (out / "00_draw_analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "README.md").write_text(
        """# Gacha / Draw 4차 분석

DrawRecord와 DrawPreviewRecord의 실제 Reference를 조사하는 단계다.

확률/수량/가격은 필드명만으로 확정하지 않는다. 각 NDJSON에는 원본 파일/Record path/field와 대상 Reference evidence를 보존한다.

다음 단계는 반복 구조를 이용해 실제 Draw → Preview → ItemPackage → Item 체인을 정제하고, 확률/비용/기간/천장 필드의 의미를 교차 검증하는 것이다.
""",
        encoding="utf-8"
    )

    md = [
        "# Gacha 4차 구조 분석", "",
        "## 실행 요약",
        f"- JSON: {len(files):,} / 파싱: {parsed:,}",
        f"- 고유 ID: {len(index):,}",
        f"- DrawRecord 후보: {counts['DrawRecord']:,}",
        f"- DrawPreviewRecord 후보: {counts['DrawPreviewRecord']:,}",
        f"- Draw 계열 전체: {len(draws):,}",
        f"- Reference가 하나 이상 해결된 Draw 계열: {len(draws) - len(unresolved):,}",
        f"- 미해결 Draw 계열: {len(unresolved):,}",
        f"- 확률 필드 후보 발생: {len(prob):,}",
        f"- 비용 필드 후보 발생: {len(costs):,}",
        f"- 기간 필드 후보 발생: {len(periods):,}", "",
        "## 대상 Record 종류"
    ]
    md += [f"- {k}: {v:,}" for k, v in target_types.most_common()]
    md += [
        "", "## 해석 주의",
        "- 현재 결과는 구조 후보다.",
        "- 숫자 하나만으로 확률/수량/가격을 확정하지 않는다.",
        "- 다음 단계에서 Draw/Preview/ItemPackage/Item의 반복 Reference 체인을 교차 검증한다."
    ]
    (out / "gacha_tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

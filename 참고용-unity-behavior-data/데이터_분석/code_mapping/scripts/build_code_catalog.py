#!/usr/bin/env python3
"""Build a reproducible server-oriented Unity code-data catalog."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, Iterable

def walk(obj: Any, path: str = "") -> Iterable[tuple[str, Dict[str, Any]]]:
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            child = f"{path}.{k}" if path else k
            yield from walk(v, child)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def decrypt_record(record: Dict[str, Any]) -> int | None:
    hidden, key = record.get("hiddenValue"), record.get("currentCryptoKey")
    if isinstance(hidden, int) and isinstance(key, int):
        return hidden ^ key
    return None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mono", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    catalog: Dict[str, Dict[str, Any]] = {}
    fields = ("m_nameId","m_describeId","m_groupNameId","m_subNameId",
              "m_icon","m_code","m_weaponId","m_user","m_type","m_quality","m_star")
    for path in sorted(args.mono.rglob("*.json")):
        try:
            data = load_json(path)
        except Exception:
            continue
        for json_path, obj in walk(data):
            rid = decrypt_record(obj)
            if rid is None:
                raw = obj.get("m_id", obj.get("id"))
                if isinstance(raw, int):
                    rid = raw
                elif isinstance(raw, str) and raw.isdigit():
                    rid = int(raw)
            if rid is None:
                continue
            entry = catalog.setdefault(str(rid), {"network_id": rid, "sources": []})
            entry["sources"].append({"file": path.name, "path": json_path})
            for field in fields:
                if field in obj:
                    entry.setdefault(field, obj[field])
    records = [catalog[k] for k in sorted(catalog, key=lambda x: int(x))]
    out = args.output / "code_catalog.json"
    out.write_text(json.dumps({
        "schema": "server_lina.code_mapping.v1",
        "record_count": len(records),
        "records": records
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(records)} records)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse, json
from collections import Counter
from pathlib import Path

def rows(path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=None)
    p.add_argument("--output",type=Path,default=None)
    a=p.parse_args()
    base=Path(__file__).resolve().parent
    src=(a.input or base/"output"/"normalized").resolve()
    out=(a.output or base/"output"/"data_catalog").resolve()
    out.mkdir(parents=True,exist_ok=True)

    systems=Counter(); fields=Counter(); files=Counter()
    refs=Counter(); unresolved=Counter(); formats=Counter(); ids=set(); records=0

    for r in rows(src/"all_records.ndjson"):
        records += 1
        if r.get("record_id") is not None: ids.add(str(r["record_id"]))
        files[r.get("source_file","")] += 1
        for s in (r.get("system_candidates") or ["other"]): systems[s] += 1
        for k in (r.get("record") or {}): fields[k] += 1
    for r in rows(src/"references.ndjson"): refs[r.get("field","")] += 1
    for r in rows(src/"unresolved.ndjson"): unresolved[r.get("field","")] += 1
    for r in rows(src/"structured_values.ndjson"): formats[r.get("format","unknown")] += 1

    summary={
      "stage":"data_catalog",
      "records":records,
      "unique_record_ids":len(ids),
      "source_files":len(files),
      "system_candidates":systems.most_common(),
      "fields":fields.most_common(),
      "reference_fields":refs.most_common(),
      "unresolved_fields":unresolved.most_common(),
      "structured_formats":dict(formats),
      "rules":{
        "semantic_inference":False,
        "system_classification":"candidate only",
        "reference":"exact local logical-ID only",
        "server_data":"not generated"
      }
    }
    (out/"00_catalog_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"01_system_candidates.json").write_text(json.dumps(dict(systems),ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"02_field_inventory.json").write_text(json.dumps(dict(fields),ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"03_reference_fields.json").write_text(json.dumps(dict(refs),ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"04_unresolved_fields.json").write_text(json.dumps(dict(unresolved),ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"05_structured_formats.json").write_text(json.dumps(dict(formats),ensure_ascii=False,indent=2),encoding="utf-8")

    md=["# Local Data Catalog","","정규화 데이터의 실제 구조를 요약한 카탈로그이다.","","## 규모",
        f"- Record: {records:,}",f"- 고유 ID: {len(ids):,}",f"- 원본 파일: {len(files):,}","","## System candidate"]
    md += [f"- {k}: {v:,}" for k,v in systems.most_common()]
    md += ["","## 주요 Field"]
    md += [f"- {k}: {v:,}" for k,v in fields.most_common(100)]
    md += ["","## 규칙","- 의미를 새로 추론하지 않는다.","- 미해결 참조를 오류로 취급하지 않는다.","- 서버 데이터를 생성하지 않는다.","- 구현에 필요한 시스템만 이후 GameData schema로 추출한다."]
    (out/"data_catalog.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(f"Record: {records:,}")
    print(f"Unique ID: {len(ids):,}")
    print(f"Output: {out}")

if __name__=="__main__": main()

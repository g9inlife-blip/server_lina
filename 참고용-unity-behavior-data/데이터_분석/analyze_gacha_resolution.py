#!/usr/bin/env python3
"""6차 Gacha resolution analyzer.

Resolves DrawRecord.m_itemPackageId and m_group by exact Record ID, builds
reverse links around DrawPreviewRecord, clusters DrawRecords by group, and
validates probability sums. It never assigns semantic meaning from numbers
alone; all conclusions are emitted as structural candidates with evidence.
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT=Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")
ID_KEYS={"id","m_id","_id","recordid","record_id"}

def load(p):
    with p.open("r",encoding="utf-8-sig") as f:return json.load(f)

def scalar(v):
    if isinstance(v,dict) and isinstance(v.get("hiddenValue"),int) and isinstance(v.get("currentCryptoKey"),int):
        return str(v["hiddenValue"] ^ v["currentCryptoKey"])
    if isinstance(v,(str,int,float)) and not isinstance(v,bool) and str(v).strip():
        return str(v).strip()
    return None

def rid(o):
    if not isinstance(o,dict): return None
    for k,v in o.items():
        if str(k).lower() in ID_KEYS:
            x=scalar(v)
            if x:return x
    return None

def walk(o,path="$"):
    if isinstance(o,dict):
        yield path,o
        for k,v in o.items():yield from walk(v,f"{path}.{k}")
    elif isinstance(o,list):
        for i,v in enumerate(o):yield from walk(v,f"{path}[{i}]")

def flatten(o,prefix="$"):
    if scalar(o) is not None:
        yield prefix,scalar(o);return
    if isinstance(o,dict):
        for k,v in o.items():yield from flatten(v,f"{prefix}.{k}")
    elif isinstance(o,list):
        for i,v in enumerate(o):yield from flatten(v,f"{prefix}[{i}]")

def file_types(name):
    n=Path(name).name.lower()
    out=[]
    if "drawpreviewrecord" in n or "drawpreview" in n:out.append("DrawPreviewRecord")
    elif "drawrecord" in n:out.append("DrawRecord")
    if "itempackage" in n or "item_package" in n or "itempack" in n or "package" in n:out.append("ItemPackage")
    if "itemrecord" in n:out.append("Item")
    if "rewardrecord" in n or "rewardgroup" in n or "reward" in n:out.append("Reward")
    if "currency" in n or "wallet" in n:out.append("Currency")
    if "event" in n or "season" in n or "limited" in n:out.append("Event")
    if "__krrecord.json" in n:out.append("KoreanLocalization")
    return sorted(set(out))

def write_ndjson(path,rows):
    with path.open("w",encoding="utf-8") as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")

def number(v):
    if isinstance(v,bool):return None
    if isinstance(v,(int,float)):return float(v)
    try:return float(str(v).strip())
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-root",type=Path,default=DEFAULT_ROOT)
    ap.add_argument("--output",type=Path,default=None)
    a=ap.parse_args()
    root=a.data_root.resolve()
    base=Path(__file__).resolve().parent
    out=(a.output or base/"output"/"system_mapping"/"gacha").resolve()
    out.mkdir(parents=True,exist_ok=True)

    files=sorted(root.rglob("*.json")); index=defaultdict(list); parsed=0; errors=[]
    for p in files:
        rel=p.relative_to(root).as_posix()
        try:data=load(p);parsed+=1
        except Exception as e:
            errors.append({"file":rel,"error":f"{type(e).__name__}: {e}"});continue
        for path,o in walk(data):
            x=rid(o)
            if x is not None:
                index[x].append({"id":x,"file":rel,"path":path,"types":file_types(rel),"object":o})

    def exact(target):
        return index.get(str(target),[])

    draw=[]; previews=[]; all_by_id={}
    for entries in index.values():
        for e in entries:
            all_by_id[(e["file"],e["path"])]=e
            ts=set(e["types"])
            if "DrawRecord" in ts:draw.append(e)
            if "DrawPreviewRecord" in ts:previews.append(e)

    # Extract direct structural fields without assuming their semantics.
    draw_rows=[]; preview_rows=[]
    for e in draw:
        o=e["object"]
        row={"draw_id":e["id"],"source_file":e["file"],"path":e["path"],
             "m_group":scalar(o.get("m_group")),"m_itemPackageId":scalar(o.get("m_itemPackageId")),
             "m_probability":number(o.get("m_probability")),"m_period":scalar(o.get("m_period")),
             "m_limit":scalar(o.get("m_limit")),"m_type":scalar(o.get("m_type")),
             "m_star":scalar(o.get("m_star"))}
        pkg=exact(row["m_itemPackageId"]) if row["m_itemPackageId"] else []
        row["item_package_matches"]=[{"id":x["id"],"file":x["file"],"path":x["path"],"types":x["types"]} for x in pkg]
        draw_rows.append(row)
    for e in previews:
        o=e["object"]
        preview_rows.append({"preview_id":e["id"],"source_file":e["file"],"path":e["path"],
            "m_group":scalar(o.get("m_group")),"m_probability":number(o.get("m_probability")),
            "m_period":scalar(o.get("m_period")),"m_articleID":scalar(o.get("m_articleID"))})

    # Reverse references to all Preview IDs: parent records that point to previews.
    preview_ids={x["id"] for x in previews}; preview_incoming=defaultdict(list)
    ref_key_re=re.compile(r"(id|ids|group|draw|preview|pool|table|package|item|reward|article)",re.I)
    for entries in index.values():
        for e in entries:
            for field,value in flatten(e["object"]):
                key=field.rsplit(".",1)[-1]
                if not ref_key_re.search(key):continue
                for part in re.split(r"[|,;]",value):
                    part=part.strip()
                    if part in preview_ids:
                        preview_incoming[part].append({"from_id":e["id"],"from_file":e["file"],"from_path":e["path"],"field":field})

    # Group DrawRecords by m_group.
    groups=defaultdict(list)
    for r in draw_rows:
        if r["m_group"] is not None:groups[r["m_group"]].append(r)

    group_rows=[]
    for g,rows in sorted(groups.items(),key=lambda kv:str(kv[0])):
        probs=[r["m_probability"] for r in rows if r["m_probability"] is not None]
        pkg_ids=sorted({r["m_itemPackageId"] for r in rows if r["m_itemPackageId"]})
        limits=Counter(str(r["m_limit"]) for r in rows if r["m_limit"] is not None)
        periods=Counter(str(r["m_period"]) for r in rows if r["m_period"] is not None)
        group_rows.append({"group":g,"draw_count":len(rows),"probability_count":len(probs),
            "probability_sum":sum(probs) if probs else None,
            "probability_sum_distance_from_1":abs(sum(probs)-1.0) if probs else None,
            "unique_item_package_ids":len(pkg_ids),"item_package_ids":pkg_ids,
            "limit_values":dict(limits),"period_values":dict(periods),
            "draw_ids":[r["draw_id"] for r in rows]})

    package_rows=[]
    package_to_draws=defaultdict(list)
    for r in draw_rows:
        if r["m_itemPackageId"]:package_to_draws[r["m_itemPackageId"]].append(r["draw_id"])
    for pid,ids in sorted(package_to_draws.items()):
        matches=exact(pid)
        package_rows.append({"item_package_id":pid,"draw_count":len(ids),"draw_ids":ids,
            "resolved_matches":[{"file":x["file"],"path":x["path"],"types":x["types"]} for x in matches]})

    write_ndjson(out/"gacha_resolution.ndjson",draw_rows)
    write_ndjson(out/"gacha_groups.ndjson",group_rows)
    write_ndjson(out/"gacha_packages.ndjson",package_rows)
    write_ndjson(out/"gacha_preview_reverse.ndjson",
                 [{"preview_id":p["id"],"incoming":preview_incoming.get(p["id"],[])} for p in previews])
    write_ndjson(out/"gacha_probability_validation.ndjson",
                 [{"group":r["group"],"draw_count":r["draw_count"],"probability_count":r["probability_count"],
                   "probability_sum":r["probability_sum"],"distance_from_1":r["probability_sum_distance_from_1"]}
                  for r in group_rows])

    resolved_pkg=sum(1 for r in draw_rows if r["item_package_matches"])
    nonzero_groups=sum(1 for r in group_rows if r["probability_sum"] is not None)
    summary={
        "stage":6,"json_file_count":len(files),"parsed_file_count":parsed,
        "unique_record_ids":len(index),"draw_records":len(draw_rows),"draw_previews":len(previews),
        "unique_draw_groups":len(group_rows),"unique_item_package_ids":len(package_to_draws),
        "resolved_item_package_ids":resolved_pkg,
        "unresolved_item_package_ids":len(package_to_draws)-resolved_pkg,
        "preview_records_with_incoming_refs":sum(1 for p in previews if preview_incoming.get(p["id"])),
        "probability_groups_with_values":nonzero_groups,
        "groups_probability_sum_exact_1":sum(1 for r in group_rows if r["probability_sum"] is not None and abs(r["probability_sum"]-1.0)<1e-9),
        "groups_probability_sum_near_1":sum(1 for r in group_rows if r["probability_sum"] is not None and abs(r["probability_sum"]-1.0)<1e-3),
        "parse_errors":len(errors),
        "rules":{"id_resolution":"exact logical Record ID","obscured_id":"hiddenValue XOR currentCryptoKey",
                 "grouping":"DrawRecord.m_group","probability_validation":"sum only; semantic meaning not auto-confirmed"}}
    (out/"02_gacha_resolution_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Gacha 6차 구조 해석","",
        "## 목적","DrawRecord의 m_itemPackageId와 m_group을 실제 Record ID 기준으로 해석하고, DrawPreviewRecord의 역참조를 찾으며, 그룹별 확률 합계를 구조적으로 검증한다.","",
        "## 실행 결과"]
    for k,v in summary.items():md.append(f"- {k}: {v}")
    md += ["","## 해석 원칙","- ItemPackage는 파일명만으로 확정하지 않고 ID로 역검색한다.",
           "- m_group은 우선 그룹화 키로만 사용하며 Gacha Pool이라는 의미는 구조 검증 후 확정한다.",
           "- m_probability는 그룹 합계 검증만 수행하며 실제 확률/가중치 여부는 추가 증거가 필요하다.",
           "- 원본에 없는 비용/수량/천장 값은 생성하지 않는다."]
    (out/"gacha_resolution_tables.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()

#!/usr/bin/env python3
"""6.5차 Gacha Package structure analyzer.

Package is treated as a generic collection of related result references, not as
a fixed Character/Weapon/Item type. The analyzer starts from DrawRecord.m_itemPackageId,
then reverse-searches those 214 IDs across every field in all raw JSON records.
It inventories candidate package definitions, their referenced IDs, member types,
cross-Gacha/Group reuse, and package-vs-draw relationships without assigning
semantic meaning from names or numbers alone.
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
        for k,v in o.items(): yield from walk(v,f"{path}.{k}")
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from walk(v,f"{path}[{i}]")

def flatten(o,prefix="$"):
    if scalar(o) is not None:
        yield prefix,scalar(o); return
    if isinstance(o,dict):
        for k,v in o.items(): yield from flatten(v,f"{prefix}.{k}")
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from flatten(v,f"{prefix}[{i}]")

def file_types(name):
    n=Path(name).name.lower()
    out=[]
    if "drawpreviewrecord" in n or "drawpreview" in n: out.append("DrawPreviewRecord")
    if "drawrecord" in n: out.append("DrawRecord")
    if "itempackage" in n or "item_package" in n or "itempack" in n or "package" in n: out.append("ItemPackage")
    if "itemrecord" in n: out.append("Item")
    if "rewardrecord" in n or "rewardgroup" in n or "reward" in n: out.append("Reward")
    if "weapon" in n: out.append("Weapon")
    if "equipment" in n: out.append("Equipment")
    if "character" in n or "hero" in n: out.append("Character")
    if "fragment" in n or "piece" in n or "shard" in n: out.append("Fragment")
    if "currency" in n or "wallet" in n: out.append("Currency")
    return sorted(set(out))

def split_refs(v):
    s=str(v).strip()
    # Preserve simple scalar IDs while also exposing common compound ID forms.
    parts=[s]
    for sep in ("|",",",";"):
        nxt=[]
        for p in parts: nxt.extend(p.split(sep))
        parts=nxt
    out=[]
    for p in parts:
        p=p.strip()
        if p: out.append(p)
    return out

def extract_embedded_ids(value, known_ids):
    hits=[]
    for part in split_refs(value):
        if part in known_ids: hits.append(part)
        # CODE*VALUE / ID*VALUE: if the left side is a known Record ID.
        if "*" in part:
            left=part.split("*",1)[0].strip()
            if left in known_ids: hits.append(left)
    return sorted(set(hits))

def write_ndjson(path,rows):
    with path.open("w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-root",type=Path,default=DEFAULT_ROOT)
    ap.add_argument("--output",type=Path,default=None)
    a=ap.parse_args()
    root=a.data_root.resolve()
    base=Path(__file__).resolve().parent
    out=(a.output or base/"output"/"system_mapping"/"gacha").resolve()
    out.mkdir(parents=True,exist_ok=True)

    files=sorted(root.rglob("*.json")); records=[]; by_id=defaultdict(list); errors=[]
    for p in files:
        rel=p.relative_to(root).as_posix()
        try:data=load(p)
        except Exception as e:
            errors.append({"file":rel,"error":f"{type(e).__name__}: {e}"}); continue
        for path,o in walk(data):
            x=rid(o)
            if x is None: continue
            e={"id":x,"file":rel,"path":path,"types":file_types(rel),"object":o}
            records.append(e); by_id[x].append(e)

    draws=[]
    for e in records:
        if "DrawRecord" in e["types"]:
            o=e["object"]
            draws.append({
                "draw_id":e["id"],"source_file":e["file"],"path":e["path"],
                "group":scalar(o.get("m_group")),"package_id":scalar(o.get("m_itemPackageId")),
                "probability":scalar(o.get("m_probability")),"period":scalar(o.get("m_period")),
                "limit":scalar(o.get("m_limit")),"type":scalar(o.get("m_type")),"star":scalar(o.get("m_star"))
            })
    package_ids=sorted({d["package_id"] for d in draws if d["package_id"]})
    package_id_set=set(package_ids)

    # Search every scalar field, not only fields whose names look like references.
    incoming=defaultdict(list)
    packageish=defaultdict(list)
    for e in records:
        for field,value in flatten(e["object"]):
            hits=extract_embedded_ids(value,package_id_set)
            if not hits: continue
            key=field.rsplit(".",1)[-1]
            for pid in hits:
                incoming[pid].append({
                    "from_id":e["id"],"from_file":e["file"],"from_path":e["path"],
                    "field":field,"field_name":key,"raw_value":value,
                    "is_self_id":e["id"]==pid
                })
                if e["id"]==pid: packageish[pid].append({"field":field,"raw_value":value})

    # Candidate definitions are exact-ID records; their own object is inspected
    # for all references to known Record IDs. This reveals the package member list
    # even when the filename is not called ItemPackage.
    package_defs=[]; member_links=[]
    known_ids=set(by_id)
    for pid in package_ids:
        defs=by_id.get(pid,[])
        for d in defs:
            members=[]
            for field,value in flatten(d["object"]):
                hits=extract_embedded_ids(value,known_ids)
                for target in hits:
                    if target==pid: continue
                    for t in by_id.get(target,[]):
                        member={
                            "package_id":pid,"package_file":d["file"],"package_path":d["path"],
                            "field":field,"raw_value":value,"target_id":target,
                            "target_file":t["file"],"target_path":t["path"],"target_types":t["types"]
                        }
                        members.append(member); member_links.append(member)
            package_defs.append({
                "package_id":pid,"definition_file":d["file"],"definition_path":d["path"],
                "definition_types":d["types"],"definition_found":True,
                "member_reference_count":len(members),
                "unique_member_ids":sorted({m["target_id"] for m in members}),
                "member_links":members
            })
        if not defs:
            package_defs.append({
                "package_id":pid,"definition_file":None,"definition_path":None,
                "definition_types":[],"definition_found":False,"member_reference_count":0,
                "unique_member_ids":[],"member_links":[]
            })

    # Package reuse across Draw groups is a structural fact, not a semantic label.
    pkg_draws=defaultdict(list)
    for d in draws:
        if d["package_id"]: pkg_draws[d["package_id"]].append(d)
    package_usage=[]
    for pid in package_ids:
        ds=pkg_draws[pid]
        groups=sorted({d["group"] for d in ds if d["group"] is not None})
        package_usage.append({
            "package_id":pid,"draw_count":len(ds),"draw_ids":[d["draw_id"] for d in ds],
            "groups":groups,"group_count":len(groups),
            "probabilities":sorted({d["probability"] for d in ds if d["probability"] is not None}),
            "periods":sorted({d["period"] for d in ds if d["period"] is not None}),
            "limits":sorted({d["limit"] for d in ds if d["limit"] is not None})
        })

    # Summarize member types by exact target Record file classification.
    package_summaries=[]
    for pd in package_defs:
        mids=pd["unique_member_ids"]
        types=Counter()
        files=Counter()
        for mid in mids:
            for t in by_id.get(mid,[]):
                for typ in t["types"]: types[typ]+=1
                files[t["file"]]+=1
        usage=next(x for x in package_usage if x["package_id"]==pd["package_id"])
        package_summaries.append({
            "package_id":pd["package_id"],
            "definition_found":pd["definition_found"],
            "definition_files":sorted({pd["definition_file"]} if pd["definition_file"] else set()),
            "member_count":len(mids),
            "member_type_evidence":dict(types),
            "member_file_evidence":dict(files),
            "draw_count":usage["draw_count"],"group_count":usage["group_count"],
            "groups":usage["groups"],"probabilities":usage["probabilities"]
        })

    write_ndjson(out/"gacha_package_reverse_refs.ndjson",
                 [{"package_id":pid,"incoming_refs":incoming.get(pid,[])} for pid in package_ids])
    write_ndjson(out/"gacha_package_definitions.ndjson",package_defs)
    write_ndjson(out/"gacha_package_members.ndjson",member_links)
    write_ndjson(out/"gacha_package_usage.ndjson",package_usage)
    write_ndjson(out/"gacha_package_summary.ndjson",package_summaries)

    definition_found=sum(1 for p in package_summaries if p["definition_found"])
    with_members=sum(1 for p in package_summaries if p["member_count"]>0)
    reused=sum(1 for p in package_usage if p["group_count"]>1)
    multi_type=sum(1 for p in package_summaries if len(p["member_type_evidence"])>1)

    summary={
        "stage":"6.5","json_file_count":len(files),"parsed_file_count":len(files)-len(errors),
        "unique_record_ids":len(by_id),"draw_records":len(draws),
        "unique_item_package_ids":len(package_ids),
        "package_ids_with_exact_record_definition":definition_found,
        "package_ids_with_member_references":with_members,
        "package_ids_reused_across_multiple_groups":reused,
        "packages_with_multiple_evidence_types":multi_type,
        "incoming_reference_rows":sum(len(incoming[p]) for p in package_ids),
        "member_reference_rows":len(member_links),"parse_errors":len(errors),
        "rules":{
            "package_model":"generic related-data collection; no fixed Character/Weapon/Item package type",
            "package_resolution":"exact logical Record ID first; all-field reverse search",
            "member_resolution":"exact logical Record ID where possible",
            "compound_values":"ID|ID, comma, semicolon, and CODE*VALUE-left-ID candidates preserved",
            "semantic_inference":False
        }
    }
    (out/"03_gacha_package_analysis_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Gacha 6.5차 — ItemPackage 구조 복원","",
        "## 핵심 모델",
        "Package를 Character/Weapon/Item 같은 고정 타입으로 분류하지 않는다.",
        "Package는 DrawRecord가 참조하는 하나의 관련 데이터 묶음 후보이며, 실제 성격은 내부에 연결된 Record 목록으로 후처리한다.",
        "",
        "## 실행 결과"]
    for k,v in summary.items(): md.append(f"- {k}: {v}")
    md += ["","## 해석 원칙",
           "- Package 상위 객체(Gacha/CharacterPackage/WeaponPackage 등)를 데이터에 없는 상태에서 생성하지 않는다.",
           "- Package 내부 구성은 실제 ID 연결과 파일/Record 구조를 통해서만 확인한다.",
           "- 한 Package 안에 Character, Weapon, Item, Fragment 등이 함께 있어도 배제하지 않는다.",
           "- m_probability는 Package 구성원 각각의 확률이라고 자동 해석하지 않는다.",
           "- 10회 뽑기는 데이터 구조와 코드 호출 관계를 확인하기 전까지 별도 Package로 만들지 않는다.",
           "- 일반/한정 가챠의 차이는 Package 이름이 아니라 실제 연결 후보 목록의 차이로 검증한다.",
           "",
           "## 출력",
           "- gacha_package_reverse_refs.ndjson: 214개 Package ID의 전역 역참조",
           "- gacha_package_definitions.ndjson: Package ID와 정확히 일치하는 Record 정의 및 내부 참조",
           "- gacha_package_members.ndjson: Package → 후보 Record 연결 evidence",
           "- gacha_package_usage.ndjson: Package의 Draw/Group 재사용 현황",
           "- gacha_package_summary.ndjson: Package별 구성/타입 evidence 요약"]
    (out/"gacha_package_analysis.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7.1차 Package Record 구조 및 역참조 분석."""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

ID_KEYS={"id","m_id","_id","recordid","record_id"}
OBSCURED={"hiddenValue","currentCryptoKey"}
PACKAGE_FIELDS={"m_itemPackageId","itemPackageId","item_package_id","packageId","m_packageId","PackageId"}
POOL_FIELDS={"m_poolId","poolId","m_dropPoolId","dropPoolId","m_dropGroup","dropGroup","m_randomGroup","randomGroup","m_rewardGroup","rewardGroup","m_rewardId","rewardId","m_dropTable","dropTable","m_tableId","tableId","m_boxId","boxId","m_contentId","contentId"}
REWARD_FIELDS={"m_rewardId","rewardId","m_rewardGroup","rewardGroup","m_reward"}
SYSTEM_RX={
"gacha":re.compile(r"(draw|gacha|pumping|lottery)",re.I),
"reward":re.compile(r"(reward|drop|loot|bonus|gift)",re.I),
"dungeon_stage":re.compile(r"(dungeon|stage|wave)",re.I),
"quest":re.compile(r"(quest|mission|achievement)",re.I),
"daily_login":re.compile(r"(daily|login|attendance)",re.I),
"event":re.compile(r"(event|season|limited)",re.I),
"shop":re.compile(r"(shop|store|purchase)",re.I)}

def logical_id(v):
    if isinstance(v,int): return v
    if isinstance(v,str) and v.isdigit():
        try:return int(v)
        except Exception:return None
    if isinstance(v,dict) and set(v.keys())>=OBSCURED:
        try:return int(v["hiddenValue"]) ^ int(v["currentCryptoKey"])
        except Exception:return None
    return None

def walk(v,path=()):
    yield path,v
    if isinstance(v,dict):
        for k,x in v.items(): yield from walk(x,path+(str(k),))
    elif isinstance(v,list):
        for i,x in enumerate(v): yield from walk(x,path+(f"[{i}]",))

def contexts(file_name,path,keys=()):
    s=file_name+" "+".".join(path)+" "+" ".join(keys)
    h=[n for n,rx in SYSTEM_RX.items() if rx.search(s)]
    return h or ["other"]

def scalar_refs(node):
    for p,v in walk(node):
        x=logical_id(v)
        if x is not None: yield ".".join(p),x,v

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-root",default=str(Path(__file__).parent.parent/"MonoBehaviour"))
    ap.add_argument("--output-root",default=str(Path(__file__).parent/"output"/"system_mapping"/"reward_pool"))
    a=ap.parse_args(); root=Path(a.data_root); out=Path(a.output_root); out.mkdir(parents=True,exist_ok=True)
    files=sorted(root.glob("*.json")); id_index={}; records=[]; errors=[]
    for fp in files:
        try:data=json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e: errors.append({"file":fp.name,"error":str(e)}); continue
        for path,node in walk(data):
            if not isinstance(node,dict): continue
            rid=None
            for k in ID_KEYS:
                if k in node:
                    rid=logical_id(node[k])
                    if rid is not None: break
            if rid is not None:
                id_index.setdefault(rid,{"file":fp.name,"path":".".join(path)})
                records.append((fp.name,path,rid,node))
    package_ids=set()
    for fp,path,rid,node in records:
        for k,v in node.items():
            if k in PACKAGE_FIELDS:
                x=logical_id(v)
                if x is not None: package_ids.add(x)
    exact=package_ids & set(id_index); missing=package_ids-exact
    incoming=defaultdict(list)
    for fp,path,rid,node in records:
        for field_path,target,raw in scalar_refs(node):
            if target in exact and target!=rid:
                incoming[target].append({"source_record_id":rid,"source_file":fp,"source_path":".".join(path),"field_path":field_path,"raw_value":raw,"context":contexts(fp,path,node.keys())})
    package_rows=[]; members=[]; usage=[]
    for fp,path,rid,node in records:
        if rid not in exact: continue
        direct=[]
        for field_path,target,raw in scalar_refs(node):
            if target!=rid and target in id_index:
                direct.append({"path":field_path,"target_id":target,"target_file":id_index[target]["file"],"raw_value":raw})
                members.append({"package_id":rid,"member_id":target,"member_file":id_index[target]["file"],"source_file":fp,"path":".".join(path),"field_path":field_path,"raw_value":raw})
        candidate_fields=[k for k in node if k in PACKAGE_FIELDS or k in POOL_FIELDS or k in REWARD_FIELDS]
        semantic=[]
        for k,v in node.items():
            if isinstance(v,str) and re.search(r"\d+\*[-+]?\d+(?:\.\d+)?",v): semantic.append("CODE_VALUE_STRING")
            if isinstance(v,str) and re.fullmatch(r"\d+(?:\|\d+)+",v): semantic.append("ID_LIST_STRING")
        package_rows.append({"package_id":rid,"source_file":fp,"path":".".join(path),"context":contexts(fp,path,node.keys()),"keys":list(node.keys()),"direct_record_refs":direct,"incoming_reference_count":len(incoming[rid]),"incoming_contexts":sorted({c for x in incoming[rid] for c in x["context"]}),"candidate_fields":candidate_fields,"semantic_candidates":sorted(set(semantic))})
    for pid in sorted(exact):
        cs=Counter(c for x in incoming[pid] for c in x["context"])
        usage.append({"package_id":pid,"definition":id_index[pid],"incoming_reference_count":len(incoming[pid]),"contexts":dict(cs),"cross_system":len(cs)>1,"incoming_examples":incoming[pid][:25]})
    summary={"stage":"7.1","json_file_count":len(files),"parsed_file_count":len(files)-len(errors),"unique_record_ids":len(id_index),"package_values_found":len(package_ids),"package_values_with_exact_record_definition":len(exact),"package_values_without_exact_record_definition":len(missing),"package_records_analyzed":len(package_rows),"incoming_reference_rows":sum(len(x) for x in incoming.values()),"package_records_with_incoming_refs":sum(1 for p in exact if incoming[p]),"package_records_with_multiple_system_contexts":sum(1 for p in exact if len({c for x in incoming[p] for c in x["context"]})>1),"package_member_reference_rows":len(members),"parse_errors":len(errors),"rules":{"package_semantics":"generic candidate; not fixed to gacha","record_fk":"exact logical-ID equality only","probability_quantity_price":"not inferred","server_only":"not inferable from JSON alone"}}
    def dump(name,rows):
        with (out/name).open("w",encoding="utf-8") as f:
            for x in rows:f.write(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n")
    (out/"06_package_record_analysis_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    dump("package_records.ndjson",package_rows); dump("package_members.ndjson",members); dump("package_incoming_refs.ndjson",[x for p in sorted(exact) for x in incoming[p]]); dump("package_cross_system_usage.ndjson",usage); dump("package_missing_definitions.ndjson",[{"package_id":x} for x in sorted(missing)])
    (out/"package_record_parse_errors.ndjson").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in errors),encoding="utf-8")
    md=f"""# 7.1 Package Record 구조 / 역참조 분석

- JSON: {len(files)}
- 정상 파싱: {len(files)-len(errors)}
- 고유 Record ID: {len(id_index):,}
- Package 값: {len(package_ids):,}
- 정확한 Package Record 정의: {len(exact):,}
- 정의 미확인 Package 값: {len(missing):,}
- 분석 Package Record: {len(package_rows):,}
- 역참조: {sum(len(x) for x in incoming.values()):,}
- 역참조가 있는 Package: {sum(1 for p in exact if incoming[p]):,}
- 다중 시스템 문맥 Package: {sum(1 for p in exact if len({c for x in incoming[p] for c in x["context"]})>1):,}

이 단계는 Package 의미를 미리 확정하지 않는다. 정확한 Record 정의와 실제 역참조를 우선한다. 7차에서 정의가 확인된 Package 값과 Gacha의 214개 m_itemPackageId 미정의 값은 별도 집합으로 유지한다. 확률, weight, quantity, price 및 서버 전용 여부는 추정하지 않는다.

다음: 다중 시스템 재사용 Package의 실제 source Record 조사 → 내부 member 타입 분류 → IL2CPP/decompile에서 caller/resolver 추적 → 서버 요청인지 로컬 lookup인지 검증.
"""
    (out/"package_record_analysis.md").write_text(md,encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()

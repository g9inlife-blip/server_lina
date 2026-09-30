#!/usr/bin/env python3
"""5차 Gacha chain analyzer.

4차 분석 결과를 바탕으로 Draw 계열 Record의 실제 연결 그래프를 정제한다.
Draw -> Preview -> Package/Reward/Item 등의 체인을 관찰하고, 필드 구조와
CODE*VALUE/다중 ID 후보를 함께 보존한다. 숫자의 의미는 자동 확정하지 않는다.
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT=Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")
ID_KEYS={"id","m_id","_id","recordid","record_id"}
REF_RE=re.compile(r"(id|ids|item|package|pack|reward|draw|preview|pool|drop|table|group|currency|ticket|cost|price)",re.I)
SEM_RE={
 "probability":re.compile(r"(prob|probability|rate|weight|percent|percentage|ratio|chance|odds)",re.I),
 "cost":re.compile(r"(cost|price|consume|currency|ticket|point|gem|diamond|coin|gold|paid|fee)",re.I),
 "period":re.compile(r"(start|end|begin|finish|from|to|open|close|date|time|duration|period)",re.I),
 "pity":re.compile(r"(pity|guarantee|ceiling|assure|protect)",re.I),
 "quantity":re.compile(r"(count|num|number|amount|quantity|qty|times)",re.I),
}

def load(p):
    with p.open("r",encoding="utf-8-sig") as f:return json.load(f)

def scalar(v):
    if isinstance(v,dict) and isinstance(v.get("hiddenValue"),int) and isinstance(v.get("currentCryptoKey"),int):
        return str(v["hiddenValue"]^v["currentCryptoKey"])
    if isinstance(v,(str,int,float)) and not isinstance(v,bool) and str(v).strip():return str(v).strip()
    return None

def rid(o):
    if not isinstance(o,dict):return None
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
    return sorted(set(out))

def name_ko(o,file):
    if re.search(r"__krRecord\.json$",Path(file).name,re.I):
        v=o.get("m_cn")
        return v.strip() if isinstance(v,str) and v.strip() else None
    return None

def ref_values(o):
    for field,value in flatten(o):
        key=field.rsplit(".",1)[-1]
        if not REF_RE.search(key):continue
        s=value
        parts=[p.strip() for p in re.split(r"[|,;]",s)]
        for part in parts:
            if part:yield field,part

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-root",type=Path,default=DEFAULT_ROOT)
    ap.add_argument("--output",type=Path,default=None)
    a=ap.parse_args()
    root=a.data_root.resolve()
    base=Path(__file__).resolve().parent
    out=(a.output or base/"output"/"system_mapping"/"gacha").resolve()
    out.mkdir(parents=True,exist_ok=True)

    files=sorted(root.rglob("*.json"));index=defaultdict(list);parsed=0;errors=[]
    for p in files:
        rel=p.relative_to(root).as_posix()
        try:data=load(p);parsed+=1
        except Exception as e:
            errors.append({"file":rel,"error":f"{type(e).__name__}: {e}"});continue
        for path,o in walk(data):
            x=rid(o)
            if x is not None:index[x].append({"id":x,"file":rel,"path":path,"types":file_types(rel),"object":o})

    def edge_rows(e):
        result=[];seen=set()
        for field,target_id in ref_values(e["object"]):
            for t in index.get(target_id,[]):
                k=(field,target_id,t["file"],t["path"])
                if k not in seen:
                    seen.add(k)
                    result.append({"field":field,"target_id":target_id,"target_file":t["file"],"target_path":t["path"],"target_types":t["types"]})
        return result

    draws=[]
    field_inventory=Counter()
    semantic=Counter()
    file_targets=Counter()
    chain_rows=[]
    for entries in index.values():
        for e in entries:
            if not ({"DrawRecord","DrawPreviewRecord"} & set(e["types"])):continue
            edges=edge_rows(e)
            for f,v in flatten(e["object"]):
                field_inventory[(tuple(e["types"]),f.rsplit(".",1)[-1])]+=1
                for tag,rx in SEM_RE.items():
                    if rx.search(f.rsplit(".",1)[-1]):semantic[(tuple(e["types"]),f.rsplit(".",1)[-1],tag)]+=1
            for ed in edges:file_targets[(tuple(ed["target_types"]),Path(ed["target_file"]).name)]+=1
            draws.append({"id":e["id"],"record_type":e["types"],"source_file":e["file"],"path":e["path"],"name_ko":name_ko(e["object"],e["file"]),"fields":list(e["object"].keys()),"edges":edges})

    # BFS from each Draw candidate, capped to keep output finite.
    def bfs(start):
        q=[(start,0)];seen={(start["id"],start["file"],start["path"])};rows=[]
        while q:
            e,d=q.pop(0)
            if d>=5:continue
            for ed in edge_rows(e):
                for t in index.get(ed["target_id"],[]):
                    key=(t["id"],t["file"],t["path"])
                    if key in seen:continue
                    seen.add(key)
                    rows.append({"depth":d+1,"from_id":e["id"],"from_file":e["file"],"from_path":e["path"],"field":ed["field"],"to_id":t["id"],"to_file":t["file"],"to_path":t["path"],"to_types":t["types"]})
                    q.append((t,d+1))
        return rows

    for d in draws:
        entries=index[d["id"]]
        start=next((e for e in entries if e["file"]==d["source_file"] and e["path"]==d["path"]),None)
        if start:chain_rows.append({"draw_id":d["id"],"draw_type":d["record_type"],"source_file":d["source_file"],"edges":bfs(start)})

    def write(name,rows):
        with (out/name).open("w",encoding="utf-8") as f:
            for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")

    write("gacha_chain_candidates.ndjson",chain_rows)
    write("gacha_draw_inventory.ndjson",draws)
    write("gacha_field_inventory.ndjson",[{"record_type":list(k[0]),"field":k[1],"count":v} for k,v in field_inventory.most_common()])
    write("gacha_target_file_inventory.ndjson",[{"target_types":list(k[0]),"target_file":k[1],"count":v} for k,v in file_targets.most_common()])
    write("gacha_semantic_candidates.ndjson",[{"record_type":list(k[0]),"field":k[1],"tag":k[2],"count":v} for k,v in semantic.most_common()])

    summary={
      "json_file_count":len(files),"parsed_file_count":parsed,"unique_record_ids":len(index),
      "draw_records":sum(1 for d in draws if "DrawRecord" in d["record_type"]),
      "draw_previews":sum(1 for d in draws if "DrawPreviewRecord" in d["record_type"]),
      "draw_entries":len(draws),"chain_entries":len(chain_rows),
      "edge_count":sum(len(x["edges"]) for x in chain_rows),
      "direct_target_types":Counter(t for d in draws for e in d["edges"] for t in e["target_types"]),
      "target_files":len(file_targets),"parse_errors":len(errors),
      "rules":{"obscured_id":"hiddenValue XOR currentCryptoKey","kr_name_field":"m_cn","max_chain_depth":5,"semantic_inference":False}
    }
    (out/"01_gacha_chain_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Gacha 5차 체인 분석","","## 실행 요약"]
    for k,v in summary.items():
        if k not in ("direct_target_types","target_files","rules"):lines.append(f"- {k}: {v}")
    lines += ["","## 직접 연결 타입"]
    lines += [f"- {k}: {v:,}" for k,v in summary["direct_target_types"].most_common()]
    lines += ["","## 해석 주의","- Draw 후보 수는 실제 가챠 배너 수가 아니다.","- 파일명으로 분류된 타입은 후보이며 구조 검증이 필요하다.","- 확률/가격/수량/기간은 필드명만으로 확정하지 않는다."]
    (out/"gacha_tables.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()

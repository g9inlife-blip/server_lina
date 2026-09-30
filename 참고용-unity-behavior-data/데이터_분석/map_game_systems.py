#!/usr/bin/env python3
"""3차 게임 시스템 매퍼: 1차 graph와 원본 JSON을 언어/시스템 단위로 연결."""
from __future__ import annotations
import argparse,json,re
from collections import defaultdict,Counter
from pathlib import Path

TYPE_PATTERNS={"item":["itemrecord","item_record"],"item_package":["itempackage","item_package","itempack"],"reward":["rewardrecord","rewardgroup","reward"],"draw":["drawrecord","drawpreviewrecord","drawpreview"],"shop":["shoprecord"],"daily":["daily","login","attendance","checkin","streak"],"achievement":["achievement","mission","quest"],"event":["event","season","limited"]}
NAME_KEYS={"name","m_name","title","displayname","display_name","label"}
ID_KEYS={"id","m_id","_id","recordid","record_id"}

def load_json(p):
    with p.open("r",encoding="utf-8-sig") as f:return json.load(f)
def norm(s):return re.sub(r"[^a-z0-9]+","",str(s).lower())
def types_for_file(name):
    n=norm(name);return[t for t,ps in TYPE_PATTERNS.items() if any(norm(p) in n for p in ps)]
def kr_file(name):return bool(re.search(r"__krRecord\.json$",Path(name).name,re.I))
def scalar(v):
    if isinstance(v,dict) and isinstance(v.get("hiddenValue"),int) and isinstance(v.get("currentCryptoKey"),int):
        return str(v["hiddenValue"]^v["currentCryptoKey"])
    if isinstance(v,(str,int,float)) and not isinstance(v,bool) and str(v).strip():return str(v).strip()
    return None
def record_id(obj):
    if not isinstance(obj,dict):return None
    for k,v in obj.items():
        if str(k).lower() in ID_KEYS:
            x=scalar(v)
            if x:return x
    return None
def walk(obj,path="$"):
    if isinstance(obj,dict):
        yield path,obj
        for k,v in obj.items():yield from walk(v,f"{path}.{k}")
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from walk(v,f"{path}[{i}]")
def names(obj,file):
    out=[]
    for k,v in obj.items():
        if not isinstance(v,str) or not v.strip():continue
        kl=str(k).lower()
        if kr_file(file):
            if kl=="m_cn":out.append({"value":v.strip(),"field":k,"language":"ko"})
        elif kl in NAME_KEYS:out.append({"value":v.strip(),"field":k,"language":"raw"})
    return out
def flatten(obj,prefix="$"):
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}"
            if isinstance(v,(str,int,float,bool)):yield p,str(v)
            else:yield from flatten(v,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from flatten(v,f"{prefix}[{i}]")
def id_refs(obj):
    for field,value in flatten(obj):
        key=field.rsplit(".",1)[-1].lower()
        if not any(x in key for x in ("id","item","reward","package","draw","shop")):continue
        for part in re.split(r"[|,;]",value):
            part=part.strip()
            if part and re.fullmatch(r"[A-Za-z0-9_.:-]{2,}",part):yield field,part
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--work-dir",type=Path);ap.add_argument("--data-root",type=Path);ap.add_argument("--output",type=Path);a=ap.parse_args()
    base=Path(__file__).resolve().parent;data=(a.data_root or Path(r"C:\Users\USER\Documents\GitHub\arme\참고용-unity-behavior-data\MonoBehaviour")).resolve();out=(a.output or base/"output"/"system_mapping").resolve();out.mkdir(parents=True,exist_ok=True)
    raw=defaultdict(list);files=sorted(data.rglob("*.json"));parsed=0
    for p in files:
        rel=p.relative_to(data).as_posix()
        try:root=load_json(p);parsed+=1
        except Exception:continue
        for path,obj in walk(root):
            rid=record_id(obj)
            if rid is not None:raw[rid].append({"id":rid,"file":rel,"path":path,"types":types_for_file(rel),"names":names(obj,rel),"object":obj})
    def write(path,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",encoding="utf-8") as f:
            for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")
    loc=[];conf=[]
    for rid,es in raw.items():
        ko=sorted({n["value"] for e in es for n in e["names"] if n["language"]=="ko"})
        if len(ko)>1:conf.append({"id":rid,"ko_names":ko})
        loc.append({"id":rid,"name_ko":ko[0] if ko else None,"source_files":sorted({e["file"] for e in es}),"types":sorted({t for e in es for t in e["types"]})})
    write(out/"localization"/"localization_index.ndjson",loc);write(out/"localization"/"localization_conflicts.ndjson",conf)
    bytype=defaultdict(list)
    for rid,es in raw.items():
        for t in {t for e in es for t in e["types"]}:bytype[t].append(rid)
    mappings=[]
    for system in ("item","item_package","reward","draw","shop","daily","achievement","event"):
        for rid in bytype.get(system,[]):
            es=raw[rid];edges=[];seen=set();q=[(e,0) for e in es]
            while q:
                e,d=q.pop(0)
                if d>=4:continue
                for field,target_id in id_refs(e["object"]):
                    for target in raw.get(target_id,[]):
                        k=(e["id"],e["file"],field,target["id"],target["file"],target["path"])
                        if k in seen:continue
                        seen.add(k);edge={"from_id":e["id"],"from_file":e["file"],"field":field,"to_id":target["id"],"to_file":target["file"],"to_path":target["path"],"depth":d+1};edges.append(edge);q.append((target,d+1))
            ko=next((n["value"] for e in es for n in e["names"] if n["language"]=="ko"),None)
            mappings.append({"system":system,"id":rid,"name_ko":ko,"source_files":sorted({e["file"] for e in es}),"edges":edges,"confidence":"observed" if edges else "candidate"})
    write(out/"all_system_mappings.ndjson",mappings)
    for system in ("item","item_package","reward","draw","shop","daily","achievement","event"):
        rows=[r for r in mappings if r["system"]==system];write(out/system/(system+"_mapping.ndjson"),rows)
        lines=["# "+system+" mapping","","- Record: {:,}".format(len(rows)),"","| ID | 한국어명 | 연결 수 |","|---|---|---:|"]
        lines += ["| {} | {} | {:,} |".format(r["id"],r["name_ko"] or "-",len(r["edges"])) for r in rows[:3000]]
        lines += ["","","## 해석 규칙","","- Reference 연결만으로 의미를 확정하지 않는다.","- 확률/수량/가격은 자동 추정하지 않는다.","- 한국어 이름은 *__krRecord.json의 m_cn을 사용한다.","- 동일 ID는 언어별 Record를 하나의 논리 ID로 묶는다."]
        (out/system/(system+"_tables.md")).write_text("\n".join(lines)+"\n",encoding="utf-8")
    summary={"json_file_count":len(files),"parsed_file_count":parsed,"unique_record_ids":len(raw),"mapping_rows":len(mappings),"localization_rows":len(loc),"localization_conflicts":len(conf),"system_counts":dict(Counter(r["system"] for r in mappings)),"rules":{"kr_name_field":"m_cn","obscured_id":"hiddenValue XOR currentCryptoKey","max_chain_depth":4,"probability_inference":False,"quantity_inference":False,"price_inference":False}}
    (out/"00_mapping_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("[완료] JSON {} / 파싱 {} / ID {} / 매핑 {} / 결과 {}".format(len(files),parsed,len(raw),len(mappings),out))
if __name__=="__main__":main()

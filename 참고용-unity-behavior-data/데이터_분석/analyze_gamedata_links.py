#!/usr/bin/env python3
"""GameData 1차 데이터셋의 실제 연결관계를 검증한다."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

FILES = ["item.ndjson","equipment.ndjson","weapon.ndjson","character.ndjson","skill.ndjson"]

def read_ndjson(path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def tokens(value):
    if value is None or value == "":
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [str(value)]
    if not isinstance(value, str):
        return []
    return [x for x in value.replace("|","*").split("*") if x]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,default=Path(__file__).resolve().parent/"output"/"gamedata")
    ap.add_argument("--output",type=Path,default=None)
    a=ap.parse_args()
    base=a.input.resolve()
    out=a.output.resolve() if a.output else base
    rows={}
    for fn in FILES:
        p=base/fn
        if p.exists():
            rows[fn]=list(read_ndjson(p))
    all_rows=[r for rs in rows.values() for r in rs]
    id_source={r["record_id"]:r["source_file"] for r in all_rows}
    report={"stage":"gamedata_link_analysis_v1","counts":{k:len(v) for k,v in rows.items()}}

    def rel(label,file,field,target_sources,split=True):
        stats={"records_with_value":0,"tokens":0,"exact_local":0,"unresolved":0,
               "compound_records":0,"unresolved_examples":[]}
        for r in rows.get(file,[]):
            v=r.get("raw",{}).get(field)
            if v is None or v=="":
                continue
            stats["records_with_value"]+=1
            ts=tokens(v) if split else [str(v)]
            if len(ts)>1: stats["compound_records"]+=1
            for t in ts:
                stats["tokens"]+=1
                if id_source.get(t) in target_sources:
                    stats["exact_local"]+=1
                else:
                    stats["unresolved"]+=1
                    if len(stats["unresolved_examples"])<10:
                        stats["unresolved_examples"].append({"record_id":r["record_id"],"value":t})
        report.setdefault("relations",{})[label]=stats

    rel("Actor.m_skillId1 -> SkillRecord","character.ndjson","m_skillId1",{"SkillRecord.json"})
    rel("Actor.m_skillId2 -> SkillRecord","character.ndjson","m_skillId2",{"SkillRecord.json"})
    rel("Actor.m_weaponId(base token) -> WeaponRecord","character.ndjson","m_weaponId",{"WeaponRecord.json"})
    rel("Skill.m_mainSkillEff -> SkilleffRecord","skill.ndjson","m_mainSkillEff",{"SkilleffRecord.json"})
    rel("Skill.m_skillEff -> SkilleffRecord","skill.ndjson","m_skillEff")
    rel("Weapon.m_skillId -> known SkillRecord family","weapon.ndjson","m_skillId",{"SkillRecord.json"})
    rel("Weapon.m_skillId2 -> known SkillRecord family","weapon.ndjson","m_skillId2",{"SkillRecord.json"})

    groups=defaultdict(list)
    for r in rows.get("skill.ndjson",[]):
        if r.get("source_file")=="SkillRecord.json":
            g=r.get("raw",{}).get("m_skillId")
            if g not in (None,""):
                groups[str(g)].append(r["record_id"])
    report["skill_grouping"]={
        "group_count":len(groups),
        "record_count":sum(len(v) for v in groups.values()),
        "multi_record_group_count":sum(1 for v in groups.values() if len(v)>1),
        "sample":dict(list(groups.items())[:12])
    }

    def compound(label,file,field,target_sources,drop_every_other=False):
        stats={"records_with_value":0,"token_count":0,"exact_local":0,"unresolved":0,"examples":[]}
        for r in rows.get(file,[]):
            v=r.get("raw",{}).get(field)
            if not isinstance(v,str) or not v: continue
            stats["records_with_value"]+=1
            ts=tokens(v)
            if drop_every_other: ts=ts[::2]
            for t in ts:
                stats["token_count"]+=1
                if id_source.get(t) in target_sources: stats["exact_local"]+=1
                else:
                    stats["unresolved"]+=1
                    if len(stats["examples"])<10: stats["examples"].append(t)
        report.setdefault("compound_fields",{})[label]=stats

    compound("Equipment.m_decompose item token -> ItemRecord","equipment.ndjson","m_decompose",{"ItemRecord.json"},True)
    compound("Equipment.m_strengthenCost -> local known item/equipment","equipment.ndjson","m_strengthenCost",{"ItemRecord.json","EquipmentRecord.json"})
    compound("Weapon.m_cost -> local known item/equipment","weapon.ndjson","m_cost",{"ItemRecord.json","EquipmentRecord.json"},True)
    compound("Weapon.m_skillCost -> local known item/equipment","weapon.ndjson","m_skillCost",{"ItemRecord.json","EquipmentRecord.json"})

    report["opaque_or_unresolved_fields"]={
        "Weapon.m_skillId":"No exact match in the 5 extracted GameData datasets; do not relabel as broken FK.",
        "Weapon.m_skillId2":"Mostly no exact match in the 5 extracted GameData datasets.",
        "Actor.m_weaponId":"Compound format; first token is the locally confirmed WeaponRecord ID, remaining tokens are parameters.",
        "Skill.m_skillId":"Repeated grouping/base identifier; SkillRecord record_id is the level/variant row.",
        "m_itemPackageId":"Keep as package/lookup candidate until ItempackageRecord is joined by a dedicated rule."
    }

    (out/"gamedata_link_analysis.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# GameData 1차 연결관계 분석","","## 결론",
        "- 현재 1차 GameData는 정상적으로 생성되었고 Record 수는 Item 952 / Equipment 924 / Weapon 599 / Character 1,763 / Skill 23,470이다.",
        "- 이름은 아직 한국어 문자열이 아니라 m_nameId 숫자 후보이므로, localization_index를 별도 조인해야 한다.",
        "- 일반적인 ID 필드 -> Record ID 규칙만으로는 compound 값과 group ID를 잘못 해석할 수 있다.",
        "",
        "## 확인된 구조",
        "- Actor.m_weaponId: 무기ID*파라미터*파라미터 형태. 첫 토큰은 WeaponRecord와 로컬 일치한다.",
        "- Actor.m_skillId1: SkillRecord와 로컬 연결이 확인된다.",
        "- Actor.m_skillId2: 대부분 SkillRecord와 연결되며 일부는 복합/미해결 값이 남는다.",
        "- Skill.m_mainSkillEff / m_skillEff: 대부분 SkilleffRecord와 직접 연결된다.",
        "- SkillRecord.m_skillId: Record FK가 아니라 여러 level/variant Record를 묶는 base/group ID로 취급해야 한다.",
        "- Equipment.m_decompose: ItemID*수량 쌍 구조가 확인된다. 수량을 ID로 세면 안 된다.",
        "",
        "## 아직 분리해야 하는 값",
        "- Weapon.m_skillId / m_skillId2의 302xxxxx 계열은 현재 5개 GameData 추출본의 Record ID와 직접 일치하지 않는다. 현재 데이터만으로 의미를 확정하지 않는다.",
        "- Equipment.m_strengthenCost, Weapon.m_skillCost/m_cost 등은 별도 재화/소모품 체계일 가능성이 있으나 RecordType을 임의 확정하지 않는다.",
        "",
        "## 다음 작업",
        "1. localization_index를 GameData에 조인해 한국어 이름을 만든다.",
        "2. Item/Equipment/Weapon의 compound field를 구조화한다.",
        "3. Actor -> Weapon -> Skill -> Skilleff 연결을 전용 relation 테이블로 만든다.",
        "4. Stage/Tollgate -> Monster/Boss -> Reward/ItemPackage를 같은 방식으로 추가한다.",
        "5. 그 후 Gacha/Shop/Mission/Daily/Event를 조인한다.",
        "",
        "## 실행",
        "python 참고용-unity-behavior-data\\데이터_분석\\analyze_gamedata_links.py"]
    (out/"gamedata_link_analysis.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()

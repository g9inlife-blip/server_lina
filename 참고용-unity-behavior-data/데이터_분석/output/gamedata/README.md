# Offline GameData 1차 데이터셋

정규화된 로컬 JSON에서 실제 시스템별 Record를 추출한 1차 데이터셋이다.

## 원칙
- raw Record는 그대로 보존한다.
- record_id는 정규화 단계에서 계산된 logical ID를 사용한다.
- 확인 가능한 로컬 ID 연결만 confirmed_local로 기록한다.
- 찾지 못한 ID는 unresolved_local로 남긴다.
- 확률/수량/가격/서버 응답은 임의 생성하지 않는다.

## 데이터셋
### item
- Record: 952
- Reference: 4,129
- Unresolved: 1,080
- Source: ItemRecord.json
- Output: item.ndjson

### equipment
- Record: 924
- Reference: 5,001
- Unresolved: 2,292
- Source: EquipmentRecord.json
- Output: equipment.ndjson

### weapon
- Record: 599
- Reference: 4,251
- Unresolved: 3,265
- Source: WeaponRecord.json
- Output: weapon.ndjson

### character
- Record: 1,763
- Reference: 17,026
- Unresolved: 10,989
- Source: ActorRecord.json, ActorshowRecord.json, ActorbreachRecord.json
- Output: character.ndjson

### skill
- Record: 23,470
- Reference: 137,714
- Unresolved: 84,330
- Source: SkillRecord.json, SkilleffRecord.json, SkillattackRecord.json, SkillbuffRecord.json, SkillshowRecord.json, SkillrandRecord.json
- Output: skill.ndjson

## 다음 단계
1. Item/Equipment/Weapon의 실제 필드와 연결을 검증한다.
2. Actor/Skill 계층을 연결하되 필드 의미는 원본 명칭을 우선한다.
3. Stage/Monster/Reward/Package를 별도 데이터셋으로 추가한다.
4. 이후 Gacha/Shop/Mission/Daily/Event를 연결한다.
5. 구현에 필요한 데이터만 confirmed_local로 승격한다.

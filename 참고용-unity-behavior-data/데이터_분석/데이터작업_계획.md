# 데이터 작업 계획

## 1. 현재 목표

이 폴더의 작업 목적은 Unity MonoBehaviour JSON 원본을 단순히 ID 목록으로 만드는 것이 아니라, **실제 게임 데이터의 구조와 시스템 간 연결 관계를 복원**하는 것이다.

최종적으로 다음 단계의 오프라인 게임 구현에 사용할 수 있도록:

- 데이터 구조
- Record 종류
- Record 간 참조
- 보상/패키지 구성
- 가챠/상점/이벤트 구조
- 캐릭터/장비/스킬
- 스테이지/몬스터/전투 관련 수치
- 재화와 소비 구조

를 단계적으로 추출한다.

---

## 2. 지금까지 완료한 작업

### 2.1 원본 JSON 분석 기반 구축

현재 분석 대상은 약 166MB 규모의 Unity JSON 데이터이며, 최초 확인 기준 약 81개 파일이었다.

초기 분석에서 Reference 추출 오류로 `references.ndjson`이 약 14.4GB까지 커지는 문제가 있었다.

원인은 다음과 같았다.

- ID와 Reference의 판정 기준이 너무 넓었음
- `m_itemPackageId`, `m_skillId` 등의 필드를 Record ID처럼 취급할 가능성
- 중첩 Record를 부모 Record에서 반복 탐색
- 동일 Reference의 반복 생성

이를 수정하여 현재 Python 분석기는:

- Record ID 키를 제한
- Reference 추출과 Record ID 추출을 분리
- 중첩 Record 경계를 인식
- Reference 중복 제거
- NDJSON 스트리밍 출력
- Record/파일 단위 폭증 제한

을 적용한다.

### 2.2 현재 Record ID 규칙

Record ID로 인정하는 키:

```text
id
m_id
_id
recordid
record_id
```

현재 재분석 결과:

```text
JSON:              74
Record:            118,015
고유 ID:           118,015
중복 ID:           0
JSON 오류:         0
```

즉, 현재 확보된 데이터 집합에서는 **중복 ID나 JSON 파싱 문제는 확인되지 않았다.**

### 2.3 Reference 그래프

현재 확인된 결과:

```text
검증된 참조:       118,539
미해결 참조:       355,001
```

미해결 Reference는 현재 데이터에 대상 Record가 없다는 뜻이며, 반드시 데이터 오류를 의미하지 않는다.

현재 데이터가 게임 전체 데이터가 아닐 수 있고, 서버 데이터/런타임 생성 데이터/누락된 원본 등을 참조할 가능성이 있으므로 **미해결 Reference를 억지로 채우지 않는다.**

현재 단계에서는 검증된 Reference를 중심으로 실제 구조를 복원한다.

---

## 3. 복합 데이터 구조 분석

### 3.1 CODE*VALUE

다음과 같은 구조를 확인했다.

```text
45201501*1600|45200402*200
```

해석 단계에서는:

```text
code     value
45201501 1600
45200402 200
```

으로 분리한다.

현재 결과:

```text
CODE*VALUE 구조:    21,694
CODE*VALUE 항목:    111,187
```

중요한 원칙:

> value가 수량인지 확률인지 레벨인지 가중치인지 Python 단계에서 임의 확정하지 않는다.

필드와 연결 Record를 확인한 후 의미를 결정한다.

출력:

```text
output/_work/structured_code_values.ndjson
```

### 3.2 ID|ID 다중 목록

다음과 같은 구조도 확인했다.

```text
45080210|45080211|45080212|45080213
```

이를 네 개의 독립적인 ID 후보로 분리한다.

현재 결과:

```text
ID|ID 다중 목록:       86,776
ID|ID 다중 목록 항목: 375,927
```

원본 문자열과 순서도 별도 보존한다.

출력:

```text
output/_work/structured_multi_ids.ndjson
```

---

## 4. 현재 판단

현재 단계에서 **전체 미해결 Reference를 해결하는 작업은 우선순위가 아니다.**

중요한 것은:

1. 고유 Record ID가 안정적으로 만들어졌는가
2. 실제 존재하는 Record 간 연결이 잡히는가
3. 복합 데이터 구조가 보존되는가
4. 원본 데이터의 반복 패턴을 이용해 게임 시스템을 분류할 수 있는가

이다.

현재 결과는 이 조건을 만족하므로 다음 단계로 진행한다.

---

# 5. 다음 작업: 게임 시스템 구조화

다음부터는 단순 Reference 분석에서 **의미 기반 Record 분류**로 넘어간다.

우선순위는 다음과 같다.

## 5.1 가챠 / 뽑기

가장 먼저 분석한다.

대상:

```text
DrawRecord
DrawpreviewRecord
ItemPackage
Draw Pool
Probability
Grade/Rarity
Reward
```

목표 구조:

```text
DrawRecord
    |
    +-- Preview
    |
    +-- ItemPackage
    |      |
    |      +-- Item / Character / Equipment
    |
    +-- Pool
    |
    +-- Grade
    |
    +-- Probability / Weight
```

특히 다음을 찾는다.

- 일반 가챠
- 10연차
- 무료 뽑기
- 재화 소모형 뽑기
- 한정 가챠
- 기간 한정 Pool
- 등급별 확률
- 천장/보장
- 중복 보상
- 패키지 보상

**확률 값은 원본 필드와 연결 구조를 확인한 후 확정한다.**

---

## 5.2 보상 / ItemPackage

가챠와 동시에 분석한다.

목표:

```text
ItemPackage
    |
    +-- item
    +-- character
    +-- equipment
    +-- currency
    +-- quantity
```

CODE*VALUE 구조와 가장 강하게 연결될 가능성이 높은 영역이다.

예:

```text
CODE*VALUE
    |
    +-- code -> 실제 Item/Reward Record
    |
    +-- value -> 수량/확률/기타 값
```

---

## 5.3 상점

대상:

```text
ShopRecord
ShopItem
ShopPackage
Purchase
Price
Currency
Limit
```

목표:

```text
Shop
  |
  +-- 상품
  |     +-- ItemPackage
  |     +-- Price
  |     +-- Currency
  |     +-- Purchase Limit
  |
  +-- Refresh
```

---

## 5.4 출석 / Daily Login

다음 구조를 찾는다.

```text
Daily
Attendance
LoginReward
Day
Reward
Streak
```

목표:

- 1일차~N일차 보상
- 반복 출석
- 누적 출석
- 특별 출석 이벤트
- 무료 보상과 유료 보상 구분

---

## 5.5 업적

대상:

```text
Achievement
Mission
Quest
Condition
Reward
```

목표:

```text
Condition
    |
    +-- 목표값
    +-- 현재값
    +-- 완료조건
    |
    +-- Reward
```

---

## 5.6 이벤트 / 한정 콘텐츠

대상:

```text
Event
Limited
Season
Banner
Period
EventReward
```

목표:

- 시작/종료 시간
- 이벤트 전용 상점
- 이벤트 전용 가챠
- 이벤트 보상
- 이벤트 미션
- 이벤트 재화

---

## 5.7 캐릭터 / 장비 / 스킬

가챠/보상 구조를 확보한 다음 분석한다.

대상:

```text
Character
Hero
Equipment
Weapon
Armor
Accessory
Skill
Passive
Stat
```

목표:

```text
Character
  |
  +-- Stats
  +-- Equipment
  +-- Skill
  +-- Passive
```

---

## 5.8 스테이지 / 몬스터 / 보스

그 다음 전투 데이터를 분석한다.

대상:

```text
Stage
Wave
Monster
Boss
Spawn
Reward
EXP
```

목표:

- 스테이지 구성
- 웨이브
- 몬스터 종류
- 보스
- HP
- 공격력
- 방어력
- 보상
- 경험치
- 드랍

이 데이터를 확보하면 이후 전투 밸런스 조정의 근거로 사용할 수 있다.

---

# 6. 분석 방법

앞으로는 다음 4단계를 반복한다.

```text
① Record 후보 발견
       ↓
② Field/Reference 구조 확인
       ↓
③ 연결 Record 추적
       ↓
④ 반복 패턴으로 의미 확정
```

단순히 Record 이름만 보고 의미를 확정하지 않는다.

예를 들어:

```text
m_rewardId
```

가 있다고 해서 무조건 보상 데이터라고 단정하지 않는다.

다음 항목을 함께 확인한다.

- 어떤 Record에서 참조하는가
- 어떤 필드에서 반복되는가
- 대상 Record의 필드 구조
- 동일 Record가 다른 시스템에서 어떻게 사용되는가
- CODE*VALUE와 연결되는가
- ID|ID 목록과 연결되는가

---

# 7. 앞으로 만들 결과물

분석이 진행되면서 다음 결과 파일을 추가한다.

```text
01_record_inventory.json
02_record_type_inventory.json
03_system_candidates.json
04_duplicate_ids.json
05_reference_summary.json
06_data_graph.md

system/
├─ gacha_analysis.md
├─ reward_analysis.md
├─ shop_analysis.md
├─ daily_login_analysis.md
├─ achievement_analysis.md
├─ event_analysis.md
├─ character_analysis.md
├─ equipment_analysis.md
├─ skill_analysis.md
├─ stage_analysis.md
└─ monster_analysis.md
```

그리고 가능한 경우 기계 분석 결과도 별도 NDJSON으로 저장한다.

---

# 8. 가챠 분석의 최종 목표

가챠 분석은 단순히 DrawRecord 목록을 만드는 것이 아니다.

최종적으로 가능한 범위에서:

```text
[가챠 이름]
    |
    +-- 비용
    |     +-- 재화 종류
    |     +-- 필요 수량
    |
    +-- 횟수
    |     +-- 1회
    |     +-- 10회
    |
    +-- Pool
    |     |
    |     +-- 일반 등급
    |     |     +-- Item A
    |     |     +-- Item B
    |     |
    |     +-- 희귀 등급
    |           +-- Character A
    |           +-- Equipment B
    |
    +-- 확률 / Weight
    |
    +-- 보장 / 천장
    |
    +-- 기간
    |
    +-- 제한
```

형태까지 복원하는 것을 목표로 한다.

단, 원본에 없는 값은 만들어내지 않는다.

---

# 9. 오프라인 후속작업과의 연결

이 데이터 분석의 최종 목적은 분석 자체가 아니다.

향후 오프라인 버전에서:

```text
JSON 원본
   ↓
정규화된 게임 데이터
   ↓
GameData
   ├─ Characters
   ├─ Equipment
   ├─ Skills
   ├─ Items
   ├─ Gacha
   ├─ Shops
   ├─ Rewards
   ├─ Events
   ├─ Stages
   └─ Monsters
   ↓
Offline Game Logic
```

으로 연결할 수 있는 형태를 만드는 것이 최종 목표다.

온라인 서버/API에 의존하던 데이터를 가능한 범위에서 로컬 정적 데이터로 변환하고, 실제 게임 로직은 별도 단계에서 구현한다.

---

# 10. 현재 작업 원칙

### 원칙 1 — 원본 보존

원본 JSON을 직접 수정하지 않는다.

### 원칙 2 — 사실과 해석 분리

Python 분석 결과와 사람이 판단한 게임 의미를 분리한다.

### 원칙 3 — 미해결 데이터를 억지로 채우지 않는다

현재 데이터에 없는 Record는 빈 값으로 유지한다.

### 원칙 4 — 복합 문자열을 버리지 않는다

`CODE*VALUE`, `ID|ID` 같은 구조는 원본 문자열과 분해 결과를 모두 보존한다.

### 원칙 5 — 연결이 확인된 것부터 사용한다

미해결 Reference가 많더라도 검증된 연결을 기반으로 시스템을 복원한다.

### 원칙 6 — 반복 패턴을 중요하게 본다

한 개의 Record보다 같은 구조가 수십/수백/수천 번 반복되는 패턴을 우선 신뢰한다.

### 원칙 7 — 오프라인 구현을 염두에 둔다

최종적으로 실제 게임에서 필요한 데이터 구조로 변환할 수 있도록 분석한다.

---

# 11. 현재 진행 상태

```text
[완료]
JSON 파싱
    ↓
Record ID 추출
    ↓
Reference 그래프
    ↓
CODE*VALUE 분석
    ↓
ID|ID 다중 목록 분석
    ↓
데이터 구조 검증
    ↓
[현재]
게임 시스템별 의미 분석
    ↓
가챠 / 보상 / 상점
    ↓
출석 / 업적 / 이벤트
    ↓
캐릭터 / 장비 / 스킬
    ↓
스테이지 / 몬스터 / 전투
    ↓
정규화된 Offline GameData
    ↓
오프라인 게임 로직 연결
```

현재는 **가챠 → 보상/ItemPackage → 상점** 순서로 후속 분석을 시작한다.


---

# 12. 2026-09-18 3차 매핑 실행 결과 및 인계

3차 매퍼 map_game_systems.py 실제 실행 결과: JSON 74 / 정상 파싱 74 / 고유 Record ID 118,015 / Localization 118,015 / Localization 충돌 0 / 전체 시스템 매핑 11,847.

시스템 후보: Item 952 / ItemPackage 2,028 / Reward 1,503 / Draw 3,034 / Shop 154 / Daily/Login 3,393 / Achievement 682 / Event 101.

주의: Draw 3,034는 실제 가챠 종류 수가 아니라 현재 분류 규칙으로 잡힌 Draw 계열 후보 Record 수다.

초기 3차 실행에서 JSON 74 / ID 0 문제가 발생했다. 원인은 hiddenValue와 currentCryptoKey 형태의 Record ID를 처리하지 않았기 때문이다. 수정 후 118,015개 고유 ID가 정상 복원되었다.

한국어 명칭은 Word__krRecord.json의 m_cn을 사용하며 현재 Localization conflict는 0이다.

# 13. 현재 작업 — 4차 Gacha 구조 복원

현재는 Draw 후보 3,034개를 실제 가챠 단위로 정제한다.

우선 확인할 연결:

DrawRecord → DrawPreviewRecord → ItemPackage → Item → Word__krRecord.m_cn

추가 조사:
- 가챠 이름과 타입
- 1회/10회
- 사용 재화와 비용
- 실제 ItemPackage와 Item
- 수량
- 확률 / rate / weight / probability
- 등급 / rarity
- 기간 시작/종료
- 천장/보장
- 한정/상시

확률/수량/가격은 숫자만 보고 추정하지 않는다. 필드명, 반복 구조, Reference, 대상 Record를 함께 확인한다.

권장 다음 스크립트: analyze_draw_structure.py
권장 결과: output/system_mapping/gacha/draw_structure.ndjson, draw_candidates.ndjson, draw_unresolved.ndjson, probability_fields.ndjson, cost_fields.ndjson, period_fields.ndjson, gacha_tables.md

# 14. 후속 작업 인계 규칙

다른 GPT가 이어서 작업할 경우 이 문서를 먼저 읽고 현재 기준 수치와 1~3차 분석을 유지한다. 처음부터 118,015 Record를 다시 분류하지 말고 output/_work 및 output/system_mapping을 기준으로 4차 Gacha 분석을 진행한다.

4차 완료 후 이 문서에 실제 DrawRecord 수, DrawPreviewRecord 수, ItemPackage 연결 수, Item 연결 수, 한국어 이름 연결 수, 비용/확률/기간/천장 필드 발견 결과, 미해결 연결 수, 다음 우선 작업을 기록한다.

의미가 확정되지 않은 값은 candidate 또는 unresolved로 남긴다.


## 15. 2026-09-18 4차 분석기 추가

`analyze_draw_structure.py`를 추가했다.

역할:
- 원본 JSON의 hiddenValue XOR currentCryptoKey ID 복원
- DrawRecord / DrawPreviewRecord 후보 추출
- ID-like Reference의 실제 대상 Record 확인
- ItemPackage / Item / Reward / Currency / Event 연결 후보 집계
- 확률 관련 필드 후보 추출
- 비용/재화 관련 필드 후보 추출
- 기간 관련 필드 후보 추출
- 미해결 Draw Record 별도 저장
- source_file / Record path / field / raw_value를 evidence로 보존

출력: `output/system_mapping/gacha/` 아래 summary, structure, candidates, unresolved, probability, cost, period, semantics, tables, README 파일.

아직 실제 데이터 실행 결과는 확보하지 않았다. 사용자가 로컬 원본 74개 JSON에서 실행한 뒤 `00_draw_analysis_summary.json`을 기준으로 실제 Gacha 체인을 정제한다.

## 16. 2026-09-18 4차 Gacha 실행 결과

사용자가 로컬 원본 74개 JSON에 4차 분석기를 실행했다.

실행 결과:

- JSON: 74
- 정상 파싱: 74
- 고유 Record ID: 118,015
- DrawRecord 후보: 2,922
- DrawPreviewRecord 후보: 112
- Draw 계열 전체: 3,034
- Reference 해결 Draw 계열: 3,034
- 미해결 Draw 계열: 0
- 직접 연결 대상: DrawPreviewRecord 112 / Item 316 / DrawRecord 2,922
- 확률 필드 후보 발생: 3,034
- 비용 필드 후보 발생: 0
- 기간 필드 후보 발생: 3,034
- JSON 오류: 0

### 4차 결과 해석

이번 결과는 4차 분석기의 ID 복원 문제가 해결되었음을 보여준다. 특히 이전에는 2,922개 DrawRecord가 미해결이었지만, hiddenValue XOR currentCryptoKey를 중첩 구조에서도 복원하도록 수정한 뒤 3,034개 전체가 최소 하나의 ID-like Reference를 해석할 수 있게 되었다.

다만 target_type_counts에 ItemPackage / Reward / Currency / Event가 나타나지 않았으므로, 이것을 실제로 해당 시스템이 없다고 해석하면 안 된다. 현재 파일명 기반 타입 분류 또는 Reference 필드 탐색 규칙이 실제 데이터 구조와 맞지 않을 가능성이 있다.

또한 probability_field_occurrences: 3,034, period_field_occurrences: 3,034는 해당 필드가 존재한다는 뜻이지 확률/기간의 실제 의미가 확정되었다는 뜻이 아니다. cost_field_occurrences: 0 역시 비용 데이터가 없다는 증거가 아니라 필드명 규칙으로 발견하지 못했을 가능성을 먼저 조사한다.

## 17. 2026-09-18 5차 Gacha 체인 분석으로 전환

4차 결과에 따라 다음 단계는 Draw 후보 개수 자체를 세는 것이 아니라 실제 Reference 체인과 필드 구조를 확인하는 것으로 변경한다.

추가 스크립트: analyze_gacha_chains.py

목표:
- DrawRecord → DrawPreviewRecord → ItemPackage/Package → Reward/Item 등의 실제 연결 확인
- 파일명에 의존한 타입 분류의 누락 여부 조사
- Draw 계열의 실제 필드명 inventory 생성
- 직접 연결 대상 파일 inventory 생성
- probability/cost/period/pity/quantity 후보를 Record 타입별로 집계
- 최대 5단계 BFS 체인 evidence 보존
- 실제 가챠 배너 단위 정제에 필요한 반복 구조 확인

출력:
- output/system_mapping/gacha/01_gacha_chain_summary.json
- gacha_chain_candidates.ndjson
- gacha_draw_inventory.ndjson
- gacha_field_inventory.ndjson
- gacha_target_file_inventory.ndjson
- gacha_semantic_candidates.ndjson
- gacha_tables.md

### 다음 실행

로컬에서:

python 참고용-unity-behavior-data\\데이터_분석\\analyze_gacha_chains.py

실행 후 01_gacha_chain_summary.json의 전체 결과와 가능하면 gacha_target_file_inventory.ndjson, gacha_field_inventory.ndjson의 상위 결과를 확보한다.

다음 판단 기준:
1. Draw → Preview 연결 패턴
2. Preview → Package/Reward 연결 여부
3. ItemPackage가 다른 파일명으로 존재하는지
4. 확률 후보 필드의 실제 이름/값 형태
5. 기간 필드의 실제 이름/값 형태
6. 비용이 CODE*VALUE 또는 다른 구조에 저장되는지
7. 동일 구조가 반복되는 단위가 실제 가챠 배너/Pool인지

이 단계가 끝나면 gacha_tables.md를 실제 가챠 목록 형태로 정제하고, 이후 Reward/ItemPackage 분석을 별도 단계로 확장.

## 18. 2026-09-18 5차 결과 검토 및 6차 방향 확정

Git에 올라온 5차 Gacha 결과물을 재검토했다. 현재 확인된 핵심 수치는 JSON 74 / 고유 Record ID 118,015 / DrawRecord 2,922 / DrawPreviewRecord 112 / Draw 전체 3,034 / 체인 edge 23,077 / 미해결 Draw 0이다.

5차 결과에서 특히 중요한 구조적 단서는 DrawRecord에 `m_itemPackageId`, `m_group`, `m_probability`, `m_period`, `m_limit` 등이 반복적으로 존재한다는 점이다. `DrawRecord.m_itemPackageId`를 기준으로 실제 대상 Record를 ID로 역검색해야 하며, ItemPackage라는 파일명이 존재하지 않는 경우에도 실제 Record를 찾아낼 수 있도록 파일명 분류보다 ID 연결을 우선한다.

또한 DrawPreviewRecord에는 `m_group`, `m_probability`, `m_period`, `m_articleID`가 존재하고 실제 `m_probability` 값이 0.0075, 0.005, 0.015, 0.03, 0.2, 0.245, 0.45 등의 형태로 확인되었다. 이는 확률 후보를 실제 값으로 검증할 수 있는 단계에 들어섰다는 의미지만, 필드명만으로 의미를 확정하지 않는다.

### 6차 분석 방향

5차 분석을 종료하고 `analyze_gacha_resolution.py`를 추가하여 다음 작업으로 전환한다.

1. 모든 DrawRecord의 `m_itemPackageId`를 정확한 Record ID로 역검색한다.
2. ItemPackage가 어떤 실제 파일/Record 타입으로 저장되어 있는지 확인한다. 파일명은 보조 정보로만 사용한다.
3. DrawRecord의 `m_group`별로 Draw를 묶고 각 그룹의 Draw 수, Package 수, 기간, 제한값을 집계한다.
4. 112개 DrawPreviewRecord 각각에 대해 전체 74개 JSON에서 역참조를 검색한다. 이를 통해 Preview보다 상위에 있는 실제 Gacha/Banner 설정 후보를 찾는다.
5. 그룹별 `m_probability` 합계를 계산하여 1.0 또는 그 주변 패턴을 검증한다. 합계가 1이라고 해서 자동으로 실제 확률이라고 확정하지 않는다.
6. ItemPackage ID → 실제 Record → Item/Equipment/Weapon/Stigmata 등의 하위 보상 연결을 다음 단계에서 확장한다.
7. 최종적으로 실제 Gacha 단위, 이름, 기간, 비용, Pool, 보상, 확률, 제한/보장 정보를 원본 증거와 함께 정리한다.

### 6차 출력

`output/system_mapping/gacha/`에 다음 결과를 생성한다.

- `02_gacha_resolution_summary.json`
- `gacha_resolution.ndjson`
- `gacha_groups.ndjson`
- `gacha_packages.ndjson`
- `gacha_preview_reverse.ndjson`
- `gacha_probability_validation.ndjson`
- `gacha_resolution_tables.md`

추가된 분석기 Git commit: `9dc2b572aa16a89c4ebc8010d9395aa043136fd2`.

### 6차 이후 우선순위

```
5차 결과 검토
  ↓
[6차] DrawRecord.m_itemPackageId / m_group / Preview 역참조 해석
  ↓
[7차] ItemPackage → Item/Equipment/Weapon/Stigmata 실제 보상 해석
  ↓
[8차] Gacha 비용/1회·10회/무료/한정/천장 구조 검증
  ↓
[9차] Daily Login / Attendance
  ↓
[10차] Achievement
  ↓
[11차] Event / Limited
  ↓
[12차] Shop / Currency
  ↓
[13차] Reward 통합
  ↓
[14차] Character / Equipment / Skill
  ↓
[15차] Stage / Monster / Battle
  ↓
정규화된 Offline GameData
  ↓
오프라인 게임 로직 연결
```

다음 실행은 로컬 원본 74개 JSON을 대상으로 `analyze_gacha_resolution.py`를 실행하고 `02_gacha_resolution_summary.json`을 기준으로 실제 연결 수치를 확인한다. 실행 결과가 나오기 전에는 Gacha 배너 수나 ItemPackage 존재 여부를 확정하지 않는다.


## 19. 2026-09-18 6차 결과 검토 및 6.5차 방향 변경

사용자가 실제 게임의 Gacha 동작과 ItemPackage의 의미를 추가로 설명했다. 이 설명을 반영하여 기존 Package 모델을 수정한다.

### 6차 실제 결과

- JSON: 74
- 정상 파싱: 74
- 고유 Record ID: 118,015
- DrawRecord: 2,922
- DrawPreviewRecord: 112
- 고유 Draw Group: 74
- 고유 m_itemPackageId: 214
- 정확한 Record ID로 해석된 Package ID: 0/214
- 미해결 Package ID: 214/214
- Preview incoming reference: 112/112
- 확률값이 있는 Group: 74
- Group 확률합 exact 1: 0
- Group 확률합 near 1: 0
- JSON 오류: 0

### Package 모델 수정

ItemPackage를 Character Package, Weapon Package처럼 고정된 타입으로 분류하지 않는다.

현재 작업 가설은 다음과 같다.

> Package는 특정 가챠 결과에 사용되는 관련 데이터 목록/묶음을 나타내는 내부 구조이며, 그 종류는 사전에 정해진 Character/Weapon/Item 타입값으로 결정되는 것이 아니라 실제 연결된 데이터 구성에 따라 달라질 수 있다.

따라서 한 Package 안에 Character, Weapon, Fragment, Item, Reward 등이 함께 존재하는 경우도 허용한다. Package의 실제 성격은 내부 참조 목록을 확인한 뒤 결과로 파생한다.

또한 Package 위에 존재하는 별도의 Gacha/CharacterPackage/WeaponPackage 같은 상위 계층은 원본 데이터나 코드에서 확인되기 전까지 생성하지 않는다.

10회 뽑기도 별도의 Package라고 가정하지 않는다. 실제 코드 호출/Draw 실행 구조를 확인하기 전까지는 Draw를 반복 실행하는 로직일 가능성을 열어 둔다.

### 확률 해석 수정

m_probability를 Package 내부 특정 Item의 확률이라고 자동 확정하지 않는다.

현재 가능한 구조는 다음처럼 열어 둔다.

DrawRecord
  ├─ m_probability
  └─ m_itemPackageId
          ↓
       Package
          ├─ 관련 Record A
          ├─ 관련 Record B
          ├─ 관련 Record C
          └─ ...

따라서 0.075 같은 값은 해당 Draw/Package 선택 단위의 확률, 등급/종류 선택 확률, 특정 결과의 확률 또는 가중치일 수 있다. 실제 의미는 Package 구성과 코드 사용 구조를 확인한 뒤 결정한다.

m_group별 확률합이 1이 되지 않는다는 사실만으로 데이터가 잘못되었다고 판단하지 않는다. m_group이 확률 정규화 단위인지 먼저 검증한다.

### 6.5차 분석 추가

새 분석기: analyze_gacha_packages.py

목표:

1. 214개 m_itemPackageId를 전체 74개 JSON의 모든 필드에서 전수 역검색한다.
2. 단순히 파일명이 ItemPackage인지 확인하지 않고 정확한 Logical Record ID가 Package ID와 일치하는지 확인한다.
3. Package ID와 일치하는 Record가 있으면 그 Record 내부의 모든 ID/복합 ID 참조를 추출한다.
4. 내부 참조 대상 Record를 Character/Weapon/Equipment/Item/Fragment/Reward 등의 파일/Record evidence와 함께 기록한다.
5. Package가 여러 DrawRecord에서 재사용되는지 확인한다.
6. 하나의 Package가 여러 Group에서 재사용되는지 확인한다.
7. Package별 실제 구성 Record 수와 타입 evidence를 집계한다.
8. 일반/한정 Gacha의 차이는 Package 이름이 아니라 실제 후보 목록 차이로 검증할 수 있도록 구조를 보존한다.

### 6.5차 출력

output/system_mapping/gacha/:

- 03_gacha_package_analysis_summary.json
- gacha_package_reverse_refs.ndjson
- gacha_package_definitions.ndjson
- gacha_package_members.ndjson
- gacha_package_usage.ndjson
- gacha_package_summary.ndjson
- gacha_package_analysis.md

### 다음 순서

[완료] 6차 DrawRecord / Preview / Group 구조
       ↓
[현재] 6.5차 Package 전수 역검색 및 구성 복원
       ↓
[7차] Package 내부 후보 Record의 실제 Item / Character / Weapon / Fragment / Reward 연결
       ↓
[8차] 실제 Gacha 단위와 m_probability 의미 검증
       ↓
[9차] 1회/10회/무료/비용/한정/기간/천장 등 코드 및 데이터 구조 연결
       ↓
Daily Login / Achievement / Event / Shop / Reward ...

6.5차에서는 Package 타입을 임의 생성하지 않으며, 원본에 없는 상위 Gacha 객체나 확률 단위를 만들어내지 않는다.


## 20. 2026-09-18 6.5차 실행 결과 및 6.6차 방향 — m_itemPackageId 호출/Lookup 가설

6.5차를 실행한 결과:

- JSON 재파싱 수치: 0/0
- 기존 분석에서 유지된 고유 Record ID: 118,015
- DrawRecord: 2,922
- 고유 m_itemPackageId: 214
- 정확한 Record ID 정의: 0/214
- Package 내부 member reference: 0
- 여러 Group에서 재사용되는 Package ID: 6
- Package ID 전역 incoming reference rows: 1,463
- parse error: 0

6.5차의 json_file_count: 0은 Package 분석기가 원본 JSON을 이번 실행에서 다시 읽지 못하고 기존 분석 산출물만 사용한 실행이라는 의미이므로, 이 수치를 원본 JSON 부재로 해석하지 않는다.

### 중요한 구조적 관찰

214개 m_itemPackageId가 모두 정확한 Logical Record ID와 일치하지 않았다. 따라서 m_itemPackageId를 단순한 DrawRecord → ItemPackageRecord FK로 확정하지 않는다.

현재 새 가설:

> m_itemPackageId는 실제 Package Record의 ID라기보다 Draw 실행 시 사용되는 호출값, lookup key, table/index key 또는 서버/클라이언트 매핑용 opaque identifier일 가능성이 있다.

이 가설은 아직 확정되지 않았다.

게임 동작 관점에서 가능한 구조:

Draw 화면
  ↓
A-1 버튼
  ↓
Draw 실행
  ↓
m_itemPackageId = K
  ↓
Package/Pool Resolver
  ├─ 서버 요청 parameter
  ├─ 클라이언트 Dictionary/Table lookup
  └─ 별도 매핑 데이터
  ↓
실제 결과 후보
  ├─ Item
  ├─ Weapon
  ├─ Fragment
  ├─ Character
  └─ Reward

한정 가챠나 화면별 데이터를 서버 측 매핑으로 교체하는 구조도 가능한 설계이지만, 현재 JSON만으로 실제 네트워크 API 호출이라고 확정하지 않는다.

### 6.6차 분석 추가

새 분석기: analyze_gacha_package_calls.py

목표:

1. 214개 m_itemPackageId를 원본 JSON의 모든 scalar field에서 전수 검색한다.
2. 값이 단순 Record ID인지, key/id 문맥인지, package 명칭 문맥인지, 배열/복합 문자열 문맥인지 분류한다.
3. 동일 값이 여러 파일/Record에서 어떤 경로로 반복되는지 기록한다.
4. Package ID가 들어 있는 부모 object의 전체 key 구조를 보존한다.
5. Draw Group/기간/확률과 Package ID의 재사용 관계를 별도 inventory로 만든다.
6. JSON에서 확인 가능한 구조적 evidence와 실제 네트워크 호출 여부를 분리한다.
7. 코드/디컴파일 산출물에서 caller → parameter → resolver 흐름을 찾을 수 있도록 후속 검색 기준을 만든다.

### 6.6차 출력

output/system_mapping/gacha/:

- 04_gacha_package_call_analysis_summary.json
- gacha_package_call_occurrences.ndjson
- gacha_package_parent_context.ndjson
- gacha_package_call_usage.ndjson
- gacha_package_call_evidence.ndjson
- gacha_package_call_analysis.md

### 6.6차 이후 판단 기준

m_itemPackageId
   ↓
[1] 서버 request parameter로 확인
   ↓
Network/API mapping 복원
   ↓
Offline LocalPackageResolver로 대체

또는

m_itemPackageId
   ↓
[2] Client Dictionary/Table key로 확인
   ↓
Local Package/Pool table 복원
   ↓
Offline resolver 구현

또는

m_itemPackageId
   ↓
[3] 다른 데이터 구조의 index/key로 확인
   ↓
해당 구조를 Package 후보 풀로 복원

어느 경우든 원본에 없는 Package 타입이나 상위 Gacha 객체를 임의 생성하지 않는다.

### 확률 모델도 수정 유지

m_probability은 현재 원본 표시 확률/상위 선택 확률 후보로 취급한다.

예를 들어 상위 등급 확률이 10%이고 후보가 10개라면 개별 후보가 1%가 될 수 있지만, 실제로 동일 확률인지 또는 내부 weight가 있는지는 Package/Pool 구조를 확인한 후 결정한다.

따라서 원본 m_probability와 검증된 내부 weight 및 후보군에서 계산한 derived_individual_probability를 별도 필드로 유지한다.

m_group별 확률합이 1이 되지 않는 것은 현재 오류로 취급하지 않는다.


# 21. 2026-09-18 7차 방향 — Package를 Gacha 전용으로 고정하지 않고 Random Reward Pool로 확장

6.6차 결과를 바탕으로 Package 분석 범위를 Gacha 외 시스템까지 확장한다.

현재 작업 가설:

> Package는 Gacha 전용 객체가 아니라, 여러 시스템에서 랜덤 후보군/보상 후보군을 조회하거나 조합하기 위한 공통적인 Pool/Package/Lookup 메커니즘일 가능성이 있다.

이 가설은 아직 확정하지 않는다. 특히 `m_itemPackageId`가 서버 요청 parameter인지, 클라이언트 Dictionary/Table key인지, 다른 인덱스인지 코드/디컴파일 사용처를 통해 검증해야 한다.

## 21.1 확인 대상

다음 시스템에서 Package/Pool/Reward 계열 필드와 구조를 함께 검색한다.

- Gacha / Draw
- Dungeon / Stage / Wave
- Reward / Drop / Loot
- Quest / Mission / Achievement
- Daily / Login / Attendance
- Event / Season / Limited
- Shop / Box / Chest / Bonus

검색 후보:

```text
m_itemPackageId
itemPackageId
packageId
m_packageId
m_poolId
poolId
m_dropPoolId
dropPoolId
m_dropGroup
dropGroup
m_randomGroup
randomGroup
m_rewardGroup
rewardGroup
m_rewardId
rewardId
m_dropTable
dropTable
m_boxId
boxId
m_contentId
contentId
```

## 21.2 7차 분석기

추가 파일:

`analyze_random_reward_pools.py`

역할:

1. 원본 JSON 전체에서 Package/Pool/Reward 관련 필드를 전수 탐색
2. Package ID가 다른 시스템 문맥에서도 사용되는지 확인
3. 정확한 Record FK인지 여부와 별개로 opaque identifier 사용 패턴 보존
4. Dungeon/Stage/Quest/Daily/Achievement/Event/Shop 문맥의 랜덤 보상 후보 탐색
5. 동일 Package/Pool 값이 여러 시스템에서 재사용되는지 확인
6. 이후 코드/IL2CPP resolver 추적에 필요한 evidence 생성

출력:

```text
output/system_mapping/reward_pool/
├─ 05_random_reward_pool_summary.json
├─ random_reward_pool_hits.ndjson
├─ random_reward_pool_candidates.ndjson
├─ package_value_contexts.ndjson
├─ parse_errors.ndjson
└─ random_reward_pool_analysis.md
```

## 21.3 보상 조합 모델 가설

현재부터 다음 구조도 검증 대상으로 둔다.

```text
Dungeon/Stage
    ↓
Reward Slot A → Package/Pool A → 일반 보상 후보
Reward Slot B → Package/Pool B → 특정 무기 파편 후보
Reward Slot C → Package/Pool C → 추가 보상 후보
    ↓
각 Pool의 선택 결과 조합
    ↓
최종 Reward Result
```

이 구조가 실제 데이터/코드에서 확인되면 Gacha와 Dungeon Reward가 같은 RandomRewardEngine을 공유할 가능성이 높아진다.

반대로 Gacha에서만 사용되는 구조라면 Package를 Gacha 전용으로 제한한다.

## 21.4 서버 보상과 로컬 표시 데이터 구분

다음 두 구조를 모두 열어 둔다.

```text
[클라이언트 RNG]
UI → Package/Pool Resolver → Local Candidate List → RNG → Reward
```

또는

```text
[서버 RNG]
UI → Package/Pool ID → Network Request → Server Reward Resolver/RNG → Result
```

현재 JSON만으로 서버 전용 후보군이라고 확정하지 않는다.

로컬 데이터에 표시용 후보만 있고 실제 서버 후보군이 별도로 존재하는 경우도 후속 코드/네트워크 호출 추적에서 검증한다.

## 21.5 Gacha 확률 모델

기존 원칙 유지:

- `m_probability`는 원본 확률/상위 선택 확률 후보
- Package 내부 후보의 개별 확률로 자동 변환하지 않음
- 후보 수만으로 균등 분배하지 않음
- 내부 weight가 확인될 경우에만 derived probability 계산
- `m_group`별 확률합이 1이 아니어도 오류로 처리하지 않음

## 21.6 다음 작업

```text
[완료] 6.6 m_itemPackageId 전수 호출/lookup 문맥 확인
        ↓
[현재] 7차 Cross-System Random Reward Pool 분석
        ↓
[다음] Package/Pool의 다중 시스템 재사용 여부 검증
        ↓
[다음] 코드/IL2CPP에서 Package resolver / caller / network request 추적
        ↓
Reward 통합
        ↓
Gacha + Dungeon + Quest + Daily + Event 보상 공통 모델
        ↓
Offline RandomRewardEngine 설계
```

7차 실행 결과가 나오기 전까지 Package가 Gacha 전용인지, 공통 보상 시스템인지 확정하지 않는다.

# 22. 2026-09-18 7차 결과 반영 및 7.1 Package Record 분석

7차 Cross-System Random Reward Pool 분석을 실제 74개 JSON에 실행한 결과:

- JSON: 74
- 정상 파싱: 74
- 고유 Record ID: 118,015
- Package 계열 필드 발생: 437
- 고유 Package 값: 422
- 정확한 Record 정의가 있는 Package 값: 416
- 정확한 Record 정의가 없는 Package 값: 6
- Pool/Reward 계열 후보 필드 발생: 6,939
- Reward/Pool 후보 Record: 118,015
- JSON 오류: 0

m_itemPackageId는 437회 발견되었고, 이 중 Quest 문맥 32회가 확인되었다. 나머지 문맥은 현재 파일명/경로 분류상 other로 잡혔으므로 이를 Gacha 이외 시스템이라고 단정하지 않는다.

## 22.1 현재 데이터의 한계에 대한 기준

이번 분석부터 다음을 명시적으로 전제로 둔다.

> 현재 확보된 JSON은 로컬 클라이언트에 포함된 데이터이므로 게임 서버가 런타임에 보내는 전체 데이터의 완전한 복사본이라고 볼 수 없다.

따라서 로컬 JSON에 어떤 Record/Pool/Reward가 없다고 해서 실제 게임에 존재하지 않는다고 판단하지 않는다.

특히 다음 경우를 모두 열어 둔다.

1. 클라이언트에는 UI 표시/검증에 필요한 최소 후보만 존재
2. 실제 확률/가중치/보상 결과는 서버가 계산
3. 클라이언트가 Package/Pool ID만 보내고 서버가 결과를 반환
4. 서버 응답에서만 최종 Reward/Item/Quantity가 결정
5. 일부 기간 한정/이벤트 데이터가 별도 서버 데이터로 존재
6. 런타임에 생성되거나 다운로드되는 데이터가 별도로 존재

따라서 이 프로젝트의 목표를 “JSON만으로 원게임 100% 복제”로 정의하지 않는다.

대신:

로컬 JSON + 코드/IL2CPP + 네트워크 호출 구조 + 실제 관찰 가능한 동작

을 결합하여 확인 가능한 범위의 Offline GameData와 Offline Game Logic을 최대한 복원한다.

확인되지 않은 서버 전용 데이터는 unknown/server_candidate로 보존하고 임의의 값으로 채우지 않는다.

## 22.2 7.1 Package Record 구조 분석

추가 스크립트:

analyze_package_records.py

목적:

- 7차에서 발견한 422개 Package 값을 실제 Record ID와 대조
- 정확한 정의가 존재하는 416개 Package Record 구조 분석
- Package Record의 field inventory 생성
- 내부 Record 참조(member) 추출
- 누가 Package Record를 역참조하는지 추적
- Gacha/Reward/Dungeon/Quest/Daily/Event/Shop 등 시스템 문맥별 재사용 여부 확인
- CODE*VALUE / ID|ID 구조가 Package 내부에 존재하는지 보존
- 의미가 불명확한 Package는 그대로 candidate로 유지

출력:

output/system_mapping/reward_pool/

- 06_package_record_analysis_summary.json
- package_records.ndjson
- package_members.ndjson
- package_incoming_refs.ndjson
- package_cross_system_usage.ndjson
- package_missing_definitions.ndjson
- package_record_parse_errors.ndjson
- package_record_analysis.md

## 22.3 7.1 결과 해석 규칙

416개의 정확한 Package Record가 발견되더라도 이것만으로 “실제 보상 풀 전체”라고 확정하지 않는다.

특히:

- Package 내부 값이 Item이라고 해서 최종 지급 Item이라고 확정하지 않는다.
- m_probability가 있다고 해서 개별 당첨 확률이라고 확정하지 않는다.
- 수치가 있다고 해서 quantity/weight/price를 자동 분류하지 않는다.
- 역참조가 없다고 해서 사용하지 않는 데이터라고 확정하지 않는다.
- JSON에 없는 Package를 새로 만들어 채우지 않는다.

## 22.4 다음 분석 우선순위

7.1 Package Record 구조
↓
Package 내부 member 타입 분류
↓
다중 시스템 재사용 Package 확인
↓
Gacha/Dungeon/Quest/Reward 호출 구조 비교
↓
IL2CPP/decompile에서 caller → resolver → network/local lookup 추적
↓
서버 계산 데이터와 로컬 정적 데이터 경계 확인
↓
공통 RandomRewardEngine 모델 설계
↓
Offline GameData + Offline Game Logic

이후에는 JSON만 계속 파고들기보다 코드 사용처 추적을 병행한다.

## 22.5 핵심 목표 수정

최종 산출물은 다음 세 계층으로 나눈다.

1. Confirmed Local Data
   - JSON에서 직접 확인된 Record/Reference/Field

2. Confirmed Runtime Logic
   - IL2CPP/decompile 및 관찰을 통해 확인된 resolver, 계산, 호출 흐름

3. Unknown / Server Candidate
   - 클라이언트 JSON에 없거나 코드만으로 확정할 수 없는 서버 측 데이터

Offline 구현에서는 1과 2를 최대한 재현하고, 3은 명시적으로 대체 규칙을 설계할 때만 별도로 기록한다.

이 기준을 이후 모든 Gacha/Reward/Dungeon/Quest/Daily/Event 분석에 공통 적용한다.


# 23. 2026-09-18 분석 방향 전환 — 추론 중심 분석 종료, 데이터 정규화 단계로 전환

7.1 Package Record 결과와 이후 IL2CPP 검색을 검토한 결과, 현재 단계에서 코드 호출 그래프를 계속 확장하는 방식은 중단한다.

핵심 판단:

> 현재 확보된 로컬 JSON에서 직접 확인할 수 있는 데이터를 최대한 보존하고, 나중에 실제 구현에 재사용하기 좋은 정규화 데이터셋을 먼저 완성한다.

이유:

- 로컬 JSON만으로 서버 데이터 전체를 복원할 수 없다.
- 코드에서 getter/caller를 찾아도 실제 서버 요청 또는 런타임 매핑까지 다시 확인해야 할 수 있다.
- 확인되지 않은 연결을 추측으로 채우면 분석이 반복되는 도돌이표가 된다.
- 현재 데이터 자체가 충분히 크고, 먼저 정리해 두는 것이 이후 구현과 추가 분석 모두에 재사용성이 높다.

따라서 지금부터는 “무엇인지 추론”보다 “무엇이 실제로 존재하는지 구조적으로 보존”하는 것을 우선한다.

## 23.1 데이터 정규화의 기본 원칙

### 원칙 A — 원본 Record 보존

모든 Record는 가능한 한 원본 object를 그대로 보존한다.

정규화 Record의 기본 구조:

- record_id
- source_file
- source_path
- system_candidates
- record
- name_candidate

system_candidates는 파일명 기반 후보일 뿐이며 최종 의미 확정값이 아니다.

### 원칙 B — ID 정규화

다음 ID 키를 동일한 logical record_id 체계로 취급한다.

- id
- m_id
- _id
- recordid
- record_id

hiddenValue/currentCryptoKey 형태는 기존 규칙대로 XOR 복원한다.

### 원칙 C — Localization 보존

Word__krRecord.json은 기존 규칙을 유지한다.

- 한국어 표시값: m_cn
- language: ko
- name_source: m_cn

Localization을 원본 Record와 분리된 NDJSON으로도 저장하여 이후 UI/GameData에서 직접 사용할 수 있게 한다.

### 원칙 D — Reference는 사실과 미해결을 분리

로컬 데이터에서 exact logical ID로 확인되는 참조만 references.ndjson에 기록한다.

대상을 찾지 못한 값은 unresolved.ndjson에 기록한다.

미해결은 오류나 존재하지 않는 데이터라는 의미가 아니다.

### 원칙 E — 복합 값 원본 보존

다음 구조는 분해 결과와 원본 문자열을 모두 유지한다.

- CODE*VALUE
- CODE*VALUE|CODE*VALUE
- ID|ID

value의 의미를 quantity/probability/weight/price 등으로 자동 변환하지 않는다.

### 원칙 F — 시스템 분류는 candidate

Gacha, Reward, Shop, Daily, Achievement, Event, Quest, Stage, Monster, Character, Equipment, Skill 등의 분류는 우선 파일명/구조 기반 candidate로 저장한다.

이 분류를 곧바로 실제 게임 의미로 확정하지 않는다.

### 원칙 G — 서버 데이터 생성 금지

로컬 JSON에서 확인되지 않은 다음 값은 생성하지 않는다.

- 서버 보상 결과
- 서버 확률
- 서버 Weight
- 서버 Quantity
- 서버 전용 Event 데이터
- 서버 전용 Package/Pool
- 네트워크 API 응답 구조

필요할 경우 나중에 별도의 Unknown / Server Candidate 데이터셋으로 기록한다.

## 23.2 새 정규화 분석기

추가 파일:

normalize_game_data.py

목적:

1. 74개 로컬 JSON을 전수 읽는다.
2. 118,015개 Record를 logical ID 기준으로 정규화한다.
3. 원본 Record object를 보존한다.
4. 시스템별 candidate Record를 별도 NDJSON으로 만든다.
5. Localization을 별도 NDJSON으로 만든다.
6. exact local ID 기준 Reference와 unresolved를 분리한다.
7. CODE*VALUE 및 ID|ID 구조를 별도 구조화 데이터로 보존한다.
8. 중복 ID를 별도 목록으로 만든다.
9. 전체 field inventory와 data inventory를 생성한다.

출력:

output/normalized/

- all_records.ndjson
- system_records.ndjson
- localization.ndjson
- references.ndjson
- unresolved.ndjson
- structured_values.ndjson
- data_inventory.json
- field_inventory.json
- duplicate_ids.json
- parse_errors.ndjson
- unknown_data.md

대용량 파일은 NDJSON 스트리밍 방식으로 기록한다. 분석 결과를 메모리에 전부 누적하여 거대한 단일 JSON으로 만들지 않는다.

## 23.3 정규화 데이터의 역할

정규화 데이터는 최종 GameData 자체가 아니라 “원본 사실을 재사용하기 위한 중간 표준층”이다.

구조:

원본 JSON
  ↓
Normalized Local Data
  ├─ Records
  ├─ Localization
  ├─ Confirmed local references
  ├─ Unresolved references
  └─ Structured raw values
  ↓
필요한 시스템별 GameData schema
  ↓
Offline GameData
  ↓
Offline Game Logic

이렇게 분리하면 나중에 Gacha를 구현할 때 필요한 데이터만 선택하고, Shop/Quest/Daily 등을 구현할 때도 같은 원본 정규화층을 재사용할 수 있다.

## 23.4 기존 Gacha/Package 분석기의 처리

기존 분석기는 삭제하지 않는다.

- analyze_draw_structure.py
- analyze_gacha_chains.py
- analyze_gacha_resolution.py
- analyze_gacha_packages.py
- analyze_gacha_package_calls.py
- analyze_random_reward_pools.py
- analyze_package_records.py

이 결과들은 “확정된 GameData”가 아니라 탐색/증거 자료로 유지한다.

특히 m_itemPackageId의 의미를 더 이상 추측하여 ItemPackage Record와 강제로 연결하지 않는다.

현재 확보된 사실은 그대로 보존한다.

- Gacha DrawRecord에 m_itemPackageId가 존재
- Gacha 214개 고유 m_itemPackageId는 exact local Record ID로 확인되지 않음
- Cross-System 분석에서는 422개 고유 Package 값 중 416개가 exact local Record definition을 가짐
- 두 집합은 서로 다른 데이터 범주일 수 있으므로 하나로 합치지 않는다.

## 23.5 앞으로의 작업 순서 수정

기존의 “코드/IL2CPP resolver 추적 → 공통 RandomRewardEngine 추론”을 즉시 진행하지 않는다.

새 순서:

1. [현재] 74개 JSON 전체 정규화
2. 전체 Record/Field/Localization inventory 완성
3. 시스템별 candidate dataset 정리
4. Confirmed Local Data와 Unknown/Server Candidate 분리
5. Gacha/Reward/Shop/Daily/Achievement/Event/Quest/Stage 데이터를 필요한 범위에서 읽기 좋은 schema로 변환
6. 실제 Offline GameData 생성
7. 오프라인 구현 중 부족한 데이터가 발견될 때만 해당 항목을 원본/코드/네트워크에서 추가 조사
8. 필요한 경우에 한해 Runtime Logic을 별도 복원

즉, **분석을 위해 구현하는 것이 아니라 구현에 필요한 데이터가 부족할 때 분석을 다시 수행한다.**

## 23.6 최종 데이터 계층

앞으로 모든 결과는 다음 세 계층을 구분한다.

### Confirmed Local Data

로컬 JSON에서 직접 확인된 값.

### Confirmed Runtime Logic

나중에 코드/관찰로 실제 동작이 확인된 로직.

### Unknown / Server Candidate

현재 데이터만으로 확정할 수 없는 값.

세 계층을 같은 필드에 섞지 않는다.

## 23.7 현재 인계 기준

다음 GPT가 이어서 작업할 때:

- 이 문서의 23장을 현재 작업 기준으로 사용한다.
- Package 의미를 추가로 추측하지 않는다.
- ItempackageData getter/caller 전체 추적을 우선 작업으로 만들지 않는다.
- 먼저 normalize_game_data.py를 로컬 74개 JSON에 실행한다.
- 실행 결과의 data_inventory.json / field_inventory.json / unknown_data.md를 기준으로 다음 작업을 결정한다.
- 기존 분석 결과는 삭제하지 않고 증거 자료로 유지한다.
- 원본에 없는 값은 생성하지 않는다.

다음 실행 명령:

python 참고용-unity-behavior-data\\데이터_분석\\normalize_game_data.py

필요한 경우:

python 참고용-unity-behavior-data\\데이터_분석\\normalize_game_data.py --data-root "C:\\원본\\MonoBehaviour" --output "참고용-unity-behavior-data\\데이터_분석\\output\\normalized"

실행 후 가장 먼저 확인할 파일:

output/normalized/data_inventory.json

그 다음:

output/normalized/field_inventory.json
output/normalized/unknown_data.md

이 결과를 기반으로 다음 시스템 분석 범위를 결정한다.


# 24. 2026-09-18 정규화 실행 완료 및 전체 데이터 카탈로그 단계

사용자가 로컬 원본 74개 JSON에 normalize_game_data.py를 실행했다.

실행 결과:

- JSON: 74
- Record: 118,015
- 고유 ID: 118,015
- 검증 참조: 92,484
- 미해결 참조: 998,811
- 중복 ID: 0
- 오류: 0

## 24.1 결과 해석

정규화 1단계는 정상 완료로 판단한다.

118,015개 Record가 모두 고유 ID를 가지며 중복 ID와 파싱 오류가 없다. 따라서 이 데이터셋을 이후 Offline GameData의 원본 정규화층으로 사용할 수 있다.

92,484개의 검증 참조는 현재 로컬 데이터에서 exact logical ID로 확인된 연결이다.

998,811개의 미해결 참조는 오류로 간주하지 않는다. 서버 데이터, 다른 ID 체계, 코드/enum 값, 문자열 복합값, 누락된 원본, 런타임 데이터 등의 가능성이 있으므로 별도 데이터로 보존한다.

## 24.2 분석 방향 재확인

이 시점부터 ItempackageData getter/caller 또는 전체 IL2CPP 호출 그래프를 선행 분석하지 않는다.

목표는 먼저 현재 존재하는 데이터를 정리하여 재사용 가능한 중간 데이터층을 만드는 것이다.

코드/네트워크 분석은 나중에 실제 Offline 구현에서 특정 데이터가 부족할 때 해당 항목만 추가 조사하는 방식으로 수행한다.

## 24.3 다음 도구

추가 파일:

build_data_catalog.py

역할:

- normalized/all_records.ndjson 전체 Record inventory
- system candidate inventory
- field inventory
- confirmed reference field inventory
- unresolved reference field inventory
- structured value format inventory
- 전체 데이터 규모 요약

출력:

output/data_catalog/

- 00_catalog_summary.json
- 01_system_candidates.json
- 02_field_inventory.json
- 03_reference_fields.json
- 04_unresolved_fields.json
- 05_structured_formats.json
- data_catalog.md

로컬 실행:

python 참고용-unity-behavior-data\\데이터_분석\\build_data_catalog.py

## 24.4 카탈로그 이후 작업

카탈로그 결과를 기준으로 실제 데이터가 충분한 영역부터 GameData schema를 만든다.

우선 확인할 순서:

1. Record/Field 전체 inventory
2. Item / Character / Equipment / Skill
3. Stage / Monster / Boss
4. Reward / ItemPackage
5. Gacha / Draw
6. Shop
7. Quest / Achievement
8. Daily / Login
9. Event / Limited

이 순서는 기능적 중요도보다 데이터 구조를 안정적으로 만들기 위한 작업 순서다. 특정 시스템을 우선 구현해야 한다는 의미는 아니다.

각 시스템 결과는 다음 세 층으로 구분한다.

- Confirmed Local Data
- Confirmed Runtime Logic
- Unknown / Server Candidate

정규화 단계에서는 첫 번째 층의 원본 사실을 최대한 보존하고, 나머지는 별도 증거로 관리한다.

## 24.5 다음 GPT 인계 기준

다음 작업자는 먼저 output/normalized/data_inventory.json과 field_inventory.json, unknown_data.md를 확인한다.

그 다음 build_data_catalog.py를 실행하여 전체 Field 분포를 확보한다.

카탈로그가 확보되면 Field 빈도와 실제 Record 구조를 기준으로 첫 번째 GameData schema를 선정한다.

미해결 참조 998,811건을 전수 해결하는 작업은 하지 않는다.

Gacha/Package 의미를 추가로 추측하지 않는다.

원본에 없는 값은 생성하지 않는다.


# 25. 2026-09-18 전체 데이터 카탈로그 검토 및 구조 Signature 단계

사용자가 로컬에서 생성한 output/data_catalog 결과를 Git에 반영했다.

## 25.1 현재 규모

카탈로그 기준:

- Record: 118,015
- 고유 Record ID: 118,015
- 카탈로그에 반영된 원본 파일: 69

System candidate:

- other: 77,977
- skill: 23,470
- item: 6,222
- gacha: 3,034
- shop: 2,868
- item_package: 2,028
- equipment: 1,523
- reward: 1,503
- achievement: 682
- daily: 393
- monster: 242
- event: 101

other가 큰 것은 데이터가 의미 없다는 뜻이 아니라 현재 분류 규칙에서 특정 candidate로 분류되지 않았다는 뜻이다.

## 25.2 카탈로그에서 확인된 주요 구조

전체 Record에서 m_id, baseDataType, m_icon, m_quality, m_frame, m_surface, m_period, m_star, m_type, m_nameId, m_describeId, m_probability, m_priority, m_power, m_effectLevel, m_attribute, m_target, m_trigger, m_group, m_reward, m_level, m_itemPackageId, m_skillId, m_itemId, m_limit, m_weight, m_parentId, m_nextId 등이 반복된다.

특히 m_probability와 m_itemPackageId는 여러 시스템에 걸쳐 존재할 수 있으므로 필드명만으로 Gacha 의미를 확정하지 않는다.

## 25.3 Reference Field 확인

현재 exact local Record 대상으로 확인된 주요 ID-like field에는 m_nameId, m_describeId, m_describe1Id, m_skillShowId, m_itemId, m_costId, m_tollgateId, m_suitId, m_bossIds, m_skillId, m_weaponId, m_ornamentId, m_clothesId, m_badgeId, m_itemPackageId 등이 있다.

이 통계는 해당 필드의 모든 값이 FK라는 의미가 아니라 현재 탐색 규칙에서 exact logical ID가 발견된 건수다.

## 25.4 다음 도구 — 실제 Record 구조 Signature 분석

추가 파일:

inspect_data_catalog.py

목적:

1. 동일 Field 집합을 가진 Record를 schema signature로 묶는다.
2. system candidate별 Field 빈도를 계산한다.
3. Field의 primitive type을 확인한다.
4. system/schema별 제한된 샘플을 저장한다.
5. 이후 GameData schema를 만들 때 사용할 구조 후보를 찾는다.

출력:

output/data_catalog/

- 06_schema_signatures.json
- 07_field_by_system.json
- 08_field_types.json
- 09_record_samples.json
- catalog_overview.md

실행:

python 참고용-unity-behavior-data\\데이터_분석\\inspect_data_catalog.py

## 25.5 다음 판단 순서

구조 Signature 결과를 확보한 뒤 다음 시스템의 실제 Record 구조를 우선 추출한다.

1. Item / Equipment / Skill
2. Stage / Monster / Boss
3. Reward / ItemPackage
4. Gacha / Draw
5. Shop
6. Quest / Achievement
7. Daily / Login
8. Event / Limited

이 순서는 중요도 순위가 아니라 데이터 구조를 안정적으로 만드는 순서다.

## 25.6 공통 schema 원칙

각 GameData schema에는 가능한 한 다음을 보존한다.

- record_id
- source_file
- source_path
- system_candidates
- 원본 Record
- 확인된 local reference
- unresolved evidence
- localization 연결

확률/수량/가격/보장/서버 결과처럼 의미가 확정되지 않은 값은 원본 필드와 candidate 상태를 유지한다.

## 25.7 현재 단계의 금지사항

- other Record를 버리지 않는다.
- 미해결 참조 998,811건을 전수 해결하지 않는다.
- m_probability를 자동으로 Gacha 확률로 변환하지 않는다.
- m_itemPackageId를 자동으로 Gacha Package FK로 확정하지 않는다.
- 로컬 JSON에 없는 서버 데이터를 생성하지 않는다.
- 실제 Offline 구현에 필요한 데이터가 특정될 때까지 전체 IL2CPP resolver 추적을 재개하지 않는다.


## 25.8 2026-09-18 구조 Signature 결과 검토

카탈로그 업로드 결과를 검토했다.

핵심 결과:
- Record 118,015
- 고유 schema signature 69개
- 가장 큰 signature 34,331건
- 두 번째 11,548건
- 전투/스킬 계열로 보이는 55-field signature 11,371건
- 25-field signature 5,274건
- 27-field signature 4,577건
- DrawRecord와 동일한 22-field signature 2,922건
- 32-field Shop 계열 후보 signature 2,714건
- 18-field ItemPackage 계열 후보 signature 2,028건
- 35-field Stage/Tollgate 계열 후보 signature 1,507건
- 43-field Event UI 계열 후보 signature 1,491건
- 76-field 전투 Actor/Monster 후보 signature 1,100건

69개의 schema signature가 확인되면서 현재 데이터는 개별 Record를 무작정 해석하기보다 source_file + schema signature 단위로 데이터 타입을 고정해 정리하는 것이 효율적이라는 판단을 내렸다.

모든 118,015 Record에 반복되는 공통 메타 필드는 m_id, baseDataType, m_icon, m_quality, m_frame, m_surface, m_period, m_star, m_type, m_specialShow, m_nameId, m_describeId, m_describe1Id, m_obtainSound, m_PumpingCard1, m_PumpingCard2, m_iconshow다.

따라서 이후 GameData schema에서는 공통 메타 필드와 시스템별 payload를 분리하는 방식을 검토한다.

## 25.9 source_file 기반 Record Type Inventory

추가 도구: build_record_type_inventory.py

목적:
- normalized/all_records.ndjson의 source_file별 Record 수 집계
- source_file별 system candidate 분포
- source_file별 schema signature
- source_file별 주요 Field
- 샘플 Record ID 보존

출력:
- output/data_catalog/10_record_type_inventory.json
- output/data_catalog/10_record_type_inventory.md

실행:
python 참고용-unity-behavior-data\\데이터_분석\\build_record_type_inventory.py

이 결과를 확보하면 69개 구조를 실제 원본 파일 타입과 1:1로 대응시킬 수 있다.

## 25.10 다음 단계

Record Type Inventory 확보 후 실제 시스템 데이터셋을 만든다.

첫 번째 대상: Item → Equipment → Skill
이후: Stage/Tollgate → Monster/Actor → Reward/Package → Gacha/Draw → Shop → Quest/Achievement → Daily → Event

각 데이터셋은 의미를 새로 만드는 것이 아니라 실제 원본 Record와 확정된 local reference를 그대로 재사용하는 방향으로 만든다.

## 25.11 2026-09-18 GameData 1차 추출 단계 진입

Record Type Inventory 업로드 결과를 검토했다.

69개 원본 파일별 Record 구조가 확인되었으며, 다음과 같이 실제 데이터셋 추출 단계로 전환한다.

1. Item
2. Equipment
3. Weapon
4. Character/Actor
5. Skill/SkillEffect

추가 도구:
- build_gamedata_datasets.py

목적:
- normalized/all_records.ndjson을 기준으로 시스템별 1차 GameData dataset 생성
- source_file / source_path / record_id / raw Record 보존
- name_candidate 보존
- ID-like 필드에서 exact local logical ID가 확인되는 참조만 confirmed_local로 기록
- 로컬에서 대상을 찾지 못한 ID는 unresolved_local로 기록
- 서버 데이터, 확률, 수량, 가격 등의 의미를 새로 생성하지 않음

출력:
output/gamedata/
- item.ndjson
- equipment.ndjson
- weapon.ndjson
- character.ndjson
- skill.ndjson
- gamedata_summary.json
- README.md

현재 출력은 최종 GameData schema가 아니라 **1차 사실 보존층**이다. 이후 각 시스템의 실제 연결 구조를 검토한 뒤 필요한 필드만 별도 schema로 정리한다.

로컬 실행:
python 참고용-unity-behavior-data\\데이터_분석\\build_gamedata_datasets.py

다음 단계:
- 위 5개 dataset 실행 결과 검토
- Item/Equipment/Weapon의 ID 연결 및 한국어 명칭 검증
- Actor ↔ Weapon ↔ Skill 연결 확인
- 이후 Stage/Tollgate → Monster/Boss → Reward/ItemPackage로 확장
- 구현 중 부족한 데이터가 발견될 때만 추가 원본/코드 분석 수행

중요: 이 단계에서도 998,811건의 unresolved reference를 전수 해결하지 않는다.

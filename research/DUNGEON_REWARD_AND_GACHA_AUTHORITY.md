# Dungeon Reward / Gacha Authority — Local Server 기준

## 1. 목적

이 문서는 던전과 가챠의 서버 권한 구조를 **Local Private Server로 이전할 때의 기준**으로 사용한다.

핵심은 Client 내부에서 모든 서버 응답을 하나씩 재구현하는 것이 아니라, 원본 Client가 기대하는 Request/Response를 Local Server가 제공하고 서버 authoritative state를 Local Server에서 유지하는 것이다.

---

## 2. Dungeon

### 2.1 후보 보상과 실제 보상은 다르다

던전 화면의 전체 보상 목록은 후보 목록이다.

예:

```text
Candidate Rewards
A B C D E F G H I J
```

실제 획득 보상은 이 중 일부이며 보통 2~3개의 기본 + 랜덤 조합이다.

### 2.2 실제 보상 결정 시점

현재 사용자 확인 기준으로 **실제 보상은 Battle Victory가 아니라 Dungeon Enter 시점에 서버가 결정한다.**

```text
Dungeon Screen
 ↓
Candidate Reward List
 ↓
Dungeon Enter Request
 ↓
Server
 ├─ Eligibility
 ├─ Base Reward
 ├─ Random Reward
 └─ Actual Reward 확정
 ↓
Enter Response
 ↓
Battle
 ↓
Success
 ↓
이미 확정된 Reward 표시/적용
```

Local Server에서도 이 시점을 변경하지 않는다.

### 2.3 Local Server 구현 모델

```text
POST/Command: DungeonEnter
 ↓
Validate Player State
 ↓
Generate Actual Reward
 ↓
Store Dungeon Session
 ├─ dungeon_id
 ├─ reward_result
 └─ session/battle identifier
 ↓
Response
```

Battle Clear에서는 새 랜덤을 실행하지 않고 저장된 `reward_result`를 사용한다.

### 2.4 Clear Transaction

던전 클리어는 보상 하나의 문제가 아니다.

```text
DUNGEON_CLEAR
 ├─ reward
 ├─ star
 ├─ clear_count
 ├─ stage/dungeon progress
 ├─ achievement progress
 ├─ mission progress
 ├─ event progress
 ├─ currency
 ├─ exp
 ├─ inventory
 └─ history/flags
```

실제 존재하는 항목만 Client/Response 분석으로 확정한다.

Local Server에서는 가능한 한 하나의 논리적 Transaction으로 처리한다.

```text
Validate
 → Mutate
 → Record History/Event
 → SQLite Commit
 → Response
```

### 2.5 Failure

```text
Battle Fail
 ↓
Dungeon Session 처리
 ↓
실패 Response
```

실패 시 실제로 변경되는 State가 무엇인지 증명한 후 구현한다.

---

## 3. Gacha

### 3.1 Banner/Data

상시/기간한정/특수 등 가챠 목록은 서버에서 공급될 수 있다.

Local Server는 Client가 기대하는 banner/data Response를 제공한다.

```text
Gacha Open
 ↓
Banner Request
 ↓
Local Server
 ↓
Banner Response
 ↓
Existing Client UI
```

### 3.2 Execute

현재 확인 기준:

```text
Gacha Select
 ↓
1 / 10 Pull
 ↓
Gacha Request
 ↓
Server
 ├─ Count
 ├─ Cost
 ├─ RNG
 ├─ Result
 └─ Player State
 ↓
Gacha Response
 ↓
Client Result UI
```

Local Server에서도 결과 결정과 상태 변경을 서버 계층에서 처리한다.

### 3.3 State Transaction

```text
GACHA_EXECUTE
 ├─ currency -= cost
 ├─ gacha_count += pull_count
 ├─ pity/guarantee state
 ├─ character/item result
 ├─ duplicate conversion
 ├─ inventory/character state
 └─ history
```

실제 필드와 규칙은 분석 전까지 확정하지 않는다.

### 3.4 Immediate Exit

가챠 결과 UI와 authoritative state의 관계를 확인한다.

```text
Gacha Execute
 ↓
Local Server Transaction
 ↓
SQLite Commit
 ↓
Response
 ↓
Client Result UI
 ↓
즉시 종료
 ↓
재실행
 ↓
Player State 확인
```

목표는 결과가 UI에만 존재하지 않고 Local Server state에 정상 저장되는 것이다.

---

## 4. Dungeon / Gacha 공통 구조

원본:

```text
Client Action
 ↓
Server Authority
 ↓
State / RNG / Result
 ↓
Response
 ↓
Client
```

목표:

```text
Client Action
 ↓
Local Private Server
 ↓
Local Authority
 ├─ State
 ├─ RNG
 ├─ Result
 └─ Transaction
 ↓
Response
 ↓
Original Client Parser / Manager / UI
```

이 구조를 사용하면 Client의 결과 표시/상태 반영 코드를 최대한 재사용할 수 있다.

---

## 5. 반드시 조사할 Client 경계

### Dungeon

```text
Candidate List
 → Enter Request
 → Enter Response
 → Actual Reward Object
 → 어디에 저장되는가?
 → Battle Start
 → Battle Result
 → Clear Handler
 → Reward/Star/Progress/Achievement/Mission
```

### Gacha

```text
Banner Response
 → Gacha Request
 → Result Response
 → Decode/Decrypt
 → Deserialize
 → Gacha Result Object
 → Client Handler
 → Inventory/Character State
```

두 기능 모두 **Response가 State로 연결되는 지점**을 반드시 확인한다.

---

## 6. 랜덤 규칙

Random 호출 하나를 찾는 것보다 다음을 증명한다.

```text
Candidate Table
 ↓
Selection Rule
 ↓
Random Timing
 ↓
Result Object
 ↓
State Mutation
```

Dungeon은 `Dungeon Enter`에서 실제 보상을 확정한다.

Gacha는 `Gacha Execute`에서 결과를 확정한다.

확률, 가중치, 천장, 중복 처리 등은 실제 코드/데이터로 확인하기 전까지 임의 구현하지 않는다.

---

## 7. 구현 우선순위

1. Dungeon Enter Request/Response 규격
2. Actual Reward Object 확인
3. Dungeon Session State 확인
4. Battle Result 연결
5. Clear Transaction 확인
6. Gacha Request/Response 규격
7. Gacha Result Object 확인
8. Currency/Inventory/Character State 연결
9. SQLite persistence
10. Runtime 검증

**Local Server 구현은 API contract가 확인된 기능부터 점진적으로 진행한다.**

## 8. 추가 Gacha/Data 분석 포인트 — 2026-09-18

현재 구조에서 다음 연결을 우선 추적한다.

```text
DrawRecord
   ↓
DrawpreviewRecord
   ↓
ItemPackage
   ↓
ShopRecord / Banner
   ↓
Gacha Request
   ↓
Result / Currency / Inventory
```

확인 항목:
- 동일 ID가 어느 단계에서 유지/변환되는지
- 상시/한정/특수 Banner 구분 필드
- Package 내부 실제 Item/Character 목록
- cost, pull count, pity/guarantee, duplicate 처리 후보 필드
- 판매기간/시작·종료 시간 및 구매 제한
- 결과가 저장되는 Player State와 History

추가로 Gacha와 동일한 방식으로 `Daily Reward → Attendance → Mission/Achievement → Event Reward`의 **조건/보상/수령 상태** 연결을 조사한다.

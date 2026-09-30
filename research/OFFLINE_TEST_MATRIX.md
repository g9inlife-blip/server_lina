# Local Server API / State Test Matrix

## 1. 목적

현재 프로젝트는 **Local Private Server / API Emulation**을 1차 방향으로 사용한다.

테스트의 핵심은 모든 Response를 APK 안에서 수동 처리하는 것이 아니라,

```text
Client Request
 → Local Server
 → State Transaction
 → Response
 → Existing Client Parser / Handler
 → UI / Gameplay
```

가 실제 게임 진행 순서대로 성립하는지 확인하는 것이다.

## 2. 공통 API 분석 단계

모든 핵심 기능은 가능하면 다음 8단계를 사용한다.

### Stage 0 — 진입 조건
- 화면/버튼/이벤트
- 필요한 선행 State
- ID/초기값
- 선행 API

### Stage 1 — Request
- Request type
- creator
- field
- serialize
- endpoint/command

### Stage 2 — Transport
- HTTP/RPC/socket
- TLS
- retry/timeout
- 성공/실패 callback

### Stage 3 — Response
- response type
- result code
- 필수 field
- server-generated values
- lists/nested objects

### Stage 4 — Decode / Deserialize
- decode/decrypt
- parser
- object 생성

### Stage 5 — Client Handler
- 어떤 Manager/Singleton이 받는가
- UI용 데이터와 State 데이터 구분

### Stage 6 — State Effect
- 어떤 Player State가 변하는가
- 어떤 Transaction인가

### Stage 7 — Persistence
- Local Server SQLite에 무엇이 저장되는가
- 다음 요청에서 어떻게 재사용되는가

### Stage 8 — Runtime
- Client 화면
- 다음 행동
- 앱 재실행 후 State

## 3. 핵심 성공 기준

단순히 Response가 정상 수신되거나 화면이 뜨면 PASS가 아니다.

```text
Request
 → Response
 → Client 처리
 → State 변경
 → 다음 행동에서 변경 상태 사용
 → Persistence
 → 재실행 후 복원
```

전체 흐름이 맞아야 기능 PASS다.

## 4. Login / Bootstrap

```text
Login Request
 → Local Server
 → Login Response
 → Client Login Complete
 → Initial Player State
 → Main Menu
```

확인:
- 계정/플레이어 ID
- session/token
- currency
- character
- inventory
- progress
- 초기 메뉴 데이터

첫 목표는 **최소 Login Response로 Main Menu까지 진입**하는 것이다.

## 5. Main Menu

메인 진입 시 필요한 API를 기능별로 분리한다.

```text
Login
 ├─ Player Data
 ├─ Currency
 ├─ Character
 ├─ Inventory
 ├─ Mail
 ├─ Mission
 ├─ Event
 ├─ Shop
 └─ Gacha/Banner
```

각 API를 하나씩 활성화하면서 어느 Response가 필수인지 기록한다.

## 6. Dungeon

### Entry

```text
Dungeon Open
 → Candidate Reward Data
 → Dungeon Enter Request
 → Local Server
 → Eligibility Check
 → Actual Reward Generation
 → Actual Reward 저장
 → Enter Response
```

**실제 보상은 Dungeon Enter 시점에 확정한다.**

화면의 약 10개 후보 목록과 실제 2~3개 획득 예정 보상을 혼동하지 않는다.

### Battle / Clear

```text
Battle Start
 → Local/Client Battle
 → Battle Result
 → Dungeon Clear
 → Stored Actual Reward Apply
 → Star
 → Clear Count
 → Achievement
 → Mission/Event
 → Currency/EXP
 → Inventory
 → History
 → Response
```

확인해야 할 것은 단순 reward field가 아니라 **하나의 Clear Action이 발생시키는 전체 State transaction**이다.

### Failure

```text
Battle Fail
 → Failure Result
 → Dungeon Session Reset
 → 관련 State 보존/변경 확인
```

## 7. Battle

전투 시작과 종료를 분리한다.

### Start
- stage ID
- character IDs
- entry cost
- session/battle ID
- initial values

### Middle
가능하면 Client 기존 전투 로직을 그대로 사용한다.

### Complete
- result
- clear/fail
- reward reference
- battle statistics
- progress
- State mutation

서버가 전투 계산을 실제로 담당하는지 증명되기 전에는 서버 전투 로직을 새로 만들지 않는다.

## 8. Gacha

```text
Gacha Menu
 → Banner Data
 → Gacha Request
 → Local Server
 → Count/Cost Validation
 → RNG / Result
 → State Transaction
 → Gacha Response
 → Existing Client Result UI
```

확인:
- banner ID
- type
- count
- cost
- currency
- result IDs
- rarity
- duplicate
- pity/guarantee
- gacha count
- character/inventory update

### Immediate Exit Test

```text
Gacha Execute
 → Server Transaction
 → Response
 → 즉시 앱 종료
 → 재실행
 → Player State 확인
```

목표는 **결과 UI보다 State Transaction이 먼저 또는 동일 Action에서 완료되는지** 확인하는 것이다.

## 9. Shop

```text
Shop Open
 → Shop Request
 → Shop Response
 → Shop UI

Purchase
 → Purchase Request
 → Validation
 → Currency/Inventory Transaction
 → Purchase Response
 → Client UI
```

구매 성공 후:
- 재화 차감
- 아이템 지급
- 구매 횟수/제한
- 상점 상태
- 관련 mission/achievement

을 확인한다.

## 10. Mission / Achievement / Event

다른 Action의 부산물로 발생하는 State를 별도 API로만 보지 않는다.

예:

```text
DUNGEON_CLEAR
 ├─ achievement_progress += 1
 ├─ mission_progress += 1
 ├─ event_progress += 1
 └─ star_count += ...
```

실제 구조가 별도 Response인지 동일 Response의 nested data인지 확인한다.

## 11. Player State / SQLite

Local Server에서 최소한 다음 계층을 고려한다.

```text
player
currency
characters
inventory
equipment
stage_progress
dungeon_state
achievement
mission
quest
gacha_state
shop_state
event_state
mail
flags
history
```

단, 실제 테이블은 Client/Response 분석 후 확정한다.

### Transaction 원칙

```text
Action
 → Validate
 → Mutate State
 → Record History/Event
 → Commit SQLite
 → Build Response
```

부분 성공 상태를 만들지 않도록 관련 State 변경은 하나의 논리적 Transaction으로 처리한다.

## 12. Response Contract 테스트

Local Server Response는 가능하면 원본 Client가 기대하는 구조를 유지한다.

테스트:

- 정상 Response
- 실패 Response
- 빈 list
- 여러 list item
- optional field 누락
- enum/result code
- nested object
- 중복 요청
- 동일 요청 재실행

중요:

**Response를 만들었다는 것과 Client가 정상적으로 State를 변경했다는 것은 별개의 검증이다.**

## 13. 네트워크/암호화

현재 패킷은 Base64-like 표현을 포함하지만 사용자가 확인한 바와 같이 암호화된 payload로 취급한다.

분석 목표는 암호를 수동으로 푸는 것이 아니라:

```text
Receive
 → Decode
 → Decrypt
 → Deserialize
 → Response Object
```

의 실제 Client path를 찾는 것이다.

Local Server가 원본과 동일한 wire format을 요구하는 경우에만 해당 암호화/직렬화 계층을 구현한다.

## 14. Runtime 테스트 순서

```text
1. Login
2. Main Menu
3. Shop Open
4. Map / Stage
5. Dungeon Open
6. Dungeon Enter
7. Battle
8. Battle Clear
9. Reward/State 확인
10. Gacha
11. Inventory/Character 재조회
12. 앱 재실행
13. State 복원 확인
```

Codex가 자동으로 build/install/logcat/network/server 상태를 확인하고, 사용자는 화면과 실제 게임 동작만 확인한다.

## 15. 기능 완료 기준

기능은 다음을 모두 만족해야 한다.

- Request contract 확인
- Response contract 확인
- Local Server handler 구현
- State mutation 확인
- SQLite persistence 확인
- Existing Client handler 정상 동작
- UI/Gameplay 정상
- 다음 행동에서 State 재사용
- 재실행 후 State 복원
- 자동 로그 이상 없음
- 필요한 사용자 화면 확인 완료

## 16. 테스트 기록

각 TASK 결과에 다음을 기록한다.

```text
TASK:
API:
Request:
Response:
Client Handler:
State Before:
Action:
State After:
SQLite:
Runtime:
User Verification:
Result: PASS / FAIL / NEED_MORE_INVESTIGATION
```

## 17. 추가 분석 체크리스트 — Data/Event 계층

기능별 API 분석과 별도로 **정적 Data와 Player State의 연결**을 확인한다.

```text
Static Data
 → ID/Package/Reward Table
 → Request/Response
 → Player State Mutation
 → UI
```

추가 대상:
- Daily Reward / Attendance
- Mission / Achievement
- 기간한정 Event / Limited Gacha
- Shop 상품/구매 제한
- Gacha Banner / Draw / Package / Result
- 서버 시간/시즌/기간 조건

각 항목은 `Data ID → Response field → State field → 저장 위치`까지 연결되면 분석 완료로 본다.

# Current State

## 1. Project
- Package: `com.thumbage.heroes.google`
- Engine: Unity / IL2CPP
- Architecture investigated: ARM64
- Primary development direction: **Local Private Server / API Emulation**
- Reference architecture: `research/ARCHITECTURE_DIRECTION.md`

## 2. Current runtime status

### Update Gate
- 기존 온라인 업데이트 진입/실패 경로에 대한 우회 패치가 적용되어 있다.
- **업데이트 우회 자체는 성공 상태**로 기록한다.
- 이것은 로그인/게임 서비스 전체의 네트워크 의존성을 제거한 것이 아니다.

### Network connected
- 업데이트 우회 후에도 원래의 서버 로그인/인증 및 데이터 처리 경로가 실행된다.
- 메인 메뉴까지 진입 가능한 상태가 확인되었다.

### Network disconnected
- 로그인 화면에서 무한 로딩이 발생한다.
- 따라서 현재 빌드는 완전 오프라인 실행 상태가 아니다.
- 최초 확실한 오프라인 실패 지점은 메인 메뉴가 아니라 **로그인 완료를 기다리는 네트워크 경계**다.

## 3. 관찰된 온라인 구조

```text
Login
 → Network Loading
 → Main
 → Network Loading
 → Shop
 → Network Loading
 → Map
 → Network Loading
 → Map Detail
 → Network Loading
 → Battle
 → Network Loading
 → Battle Result
 → Network Loading
 → Special Shop
 → Network Loading
 → Gacha
 → ...
```

메뉴 표시 자체와 별개로 기능 진입, 행동 실행, 결과 반영, 다음 화면의 상태 조회 경계에서 네트워크가 반복되는 구조다.

## 4. 아키텍처 판단 변경

기존에는 서버 권한을 Client Local Logic으로 직접 이전하는 완전 로컬화를 우선 검토했다.

현재는 게임이 Full Network Game에 가깝고 사용자 단말에 전통적인 세이브 파일이 존재하지 않는 것으로 관찰되므로, **서버가 관리하던 Player State를 Local Server + SQLite로 유지하는 방향을 1순위로 변경한다.**

```text
Original / Patched Client
       ↓ Request
Local Private Server
       ↓
Player State + Game State + Required Logic
       ↓
SQLite
       ↓ Response
Original Client Parser / Manager / UI
```

Client의 기존 Response parser, Result Object, Manager, UI, 전투 등은 최대한 재사용한다.

## 5. 왜 Local Server인가

서버 authoritative state가 단순 보상 하나가 아니라 여러 상태의 연쇄 변경을 포함할 가능성이 높다.

예: Dungeon Clear

```text
Dungeon Enter
 → Actual Reward 결정
 → Battle
 → Clear
 → Reward
 → Star
 → Clear Count
 → Achievement
 → Mission/Event Progress
 → Currency / EXP
 → Inventory
 → Flags / History
```

이를 APK 내부에서 모두 새 State/Persistence 구조로 재구현하는 것보다 Local Server에서 Transaction 단위로 관리하고 기존 Client에 필요한 Response를 반환하는 것이 현재 구조와 더 잘 맞는지 검증한다.

## 6. State 관리 방향

Local Server의 핵심은 API 개수가 아니라 **Player State**다.

후보 상태:

```text
Account / Login
Currency
Characters
Inventory
Equipment
Stage / Dungeon Progress
Achievement
Mission
Quest
Gacha State
Shop State
Event State
Mail / Attendance
Flags / History
```

실제 필드와 존재 여부는 역분석으로 확정한다.

권장 처리 모델:

```text
Request
 ↓
Command / Action
 ↓
Validation
 ↓
Transaction
 ├─ State Mutation
 ├─ Result
 └─ History/Event
 ↓
SQLite Persistence
 ↓
Response
```

## 7. Dungeon authority

현재 사용자 확인 기준:

- 화면에 보이는 약 10개의 보상은 후보 목록이다.
- 실제 보상은 보통 2~3개의 기본 + 랜덤 조합이다.
- **실제 보상은 Battle Victory가 아니라 Dungeon Enter 시점에 서버가 결정한다.**
- 이후 전투 성공 시 이미 결정된 보상을 표시/적용한다.

따라서 Local Server도:

```text
Dungeon Enter
 → Eligibility
 → Reward Generation
 → Actual Reward 저장
 → Enter Response
 → Battle
 → Clear
 → Reward/Star/Progress/Achievement/Mission Transaction
 → Response
```

순서를 보존한다.

## 8. Gacha authority

현재 확인된 구조:

```text
Gacha/Banner
 → Gacha Request
 → Server가 count/RNG/result 처리
 → Response
 → Client Result UI
 → Inventory / Character State 재조회
```

Local Server에서는 가챠 실행 시 결과와 관련 Player State를 함께 관리한다.

배너/확률/천장/중복 처리 규칙은 코드와 데이터로 증명하기 전까지 임의로 구현하지 않는다.

## 9. Response 분석 방향

암호화된 패킷을 단순히 해독하는 것 자체를 목표로 하지 않는다.

핵심 추적 경로:

```text
Network Receive
 → Decode / Decrypt
 → Deserialize
 → Response Object
 → Client Handler
 → State Effect
```

특히 Response가 어떤 Player State를 변경하는지 기록한다.

## 10. 현재 조사 우선순위

### Priority 1 — Login Protocol
- Login Request 생성
- endpoint/command
- serialization/encryption
- Response decode/decrypt
- Response model
- Login Complete callback
- 초기 Player State
- Main Menu bootstrap

### Priority 2 — State Model
- Player/User/Account 관련 중심 객체
- Currency
- Inventory
- Character
- Progress
- 공통 State mutation 함수

### Priority 3 — Local Server Bootstrap
- 최소 API 서버
- SQLite schema 초안
- 요청/응답 로깅
- 첫 Login Response mock
- 실제 Client 연결 검증

### Priority 4 — Dungeon / Battle
- Dungeon Enter Request/Response
- 실제 보상 객체
- Battle Start/Result
- Clear transaction
- Star/Achievement/Mission 등 연쇄 State

### Priority 5 — Gacha / Shop
- Request/Response
- Result model
- Currency/Inventory mutation
- banner/state

## 11. 아직 확정하지 않은 것

- 전체 API 개수
- 전체 Response model 개수
- 실제 persistence 데이터 구조
- 암호화 알고리즘의 전체 범위
- TLS/certificate pinning 여부와 패치 범위
- anti-cheat 의존성
- 서버에서만 존재하는 게임 로직의 전체 범위
- Client에 존재하는 RNG/Reward table의 전체 범위

## 12. 방향 전환 원칙

현재부터는 **Local Server를 먼저 검증**한다.

단, 모든 기능을 서버에서 새로 구현하지 않는다.

```text
Client가 이미 하는 것
 → Client 유지

Server가 반드시 해야 하는 것
 → Local Server 구현

Client와 Server의 경계가 불명확한 것
 → Request/Response/State tracing 후 결정
```

Local Server 방식으로 진행했을 때 특정 기능이 오히려 복잡해지는 경우에는 해당 기능만 Client Local Logic을 재사용하는 Hybrid 구조를 허용한다.

## 13. 문서 우선순위

1. `research/ARCHITECTURE_DIRECTION.md` — 현재 아키텍처 기준
2. `research/CODEX_PROTOCOL.md` — GPT/Codex 개발 역할과 작업 규칙
3. `research/RUNTIME_PROTOCOL.md` — 런타임 검증 규칙
4. `research/OFFLINE_TEST_MATRIX.md` — 기능별 API/State 테스트 기준
5. `research/DUNGEON_REWARD_AND_GACHA_AUTHORITY.md` — 던전/가챠 authority 사실
6. `research/reports/` — 개별 조사 결과
7. `research/runtime/` — 실제 실행 기록

오래된 '완전 Client Local' 설계 문구가 위 문서와 충돌하면 현재 문서의 Local Server 중심 방향을 우선한다.

## 14. 추가 분석 포인트 — 2026-09-18

기존 MD를 기준으로 다음 영역은 추가 증거 확보 가치가 높다.

1. **정적 Data ↔ Response 매핑**
   - Item/Package/Shop/Draw 계열 ID 연결
   - 보상 후보 → 실제 보상 → 인벤토리 ID 변환 경로
2. **시간/이벤트 State**
   - Daily Reward, Attendance, Mission, Achievement, 기간한정 Event의 시작/종료/수령 조건
   - 서버 시간과 Client 표시 시간의 경계
3. **가챠 확장**
   - DrawRecord / DrawpreviewRecord / ItemPackage / ShopRecord 연결
   - 상시/한정/특수 Banner 식별
   - cost/count/pity/duplicate/history 필드 추적
4. **Bootstrap State**
   - Login 직후 내려오는 초기 Player/Inventory/Currency/Event/Gacha 데이터와 Main 진입 필수 Response 분리
5. **공통 State Mutation**
   - 여러 API에서 반복 호출되는 Currency/Inventory/Progress 갱신 함수 식별 → Local Server Transaction 모델의 기준으로 사용

우선순위는 **Bootstrap → 공통 State Mutation → Reward/Event → Gacha/Shop** 순으로 잡는다.

# Architecture Direction — Local Private Server Emulation

## 1. 결정 사항

현재 프로젝트의 1차 개발 방향을 **완전 클라이언트 로컬화(Local-only)**에서 **Local Private Server / API Emulation** 중심으로 전환한다.

목표는 원본 게임의 서버를 완벽하게 재현하는 것이 아니라, **원본 Unity/IL2CPP 클라이언트가 기대하는 Request/Response 계약을 유지하면서 실제 서비스 서버가 담당하던 계정 상태와 필요한 게임 서비스를 로컬 서버에서 제공하는 것**이다.

```text
Original / Patched Client
        │
        │ Request
        ▼
Local Private Server
        │
        ├─ API / Protocol
        ├─ Player State
        ├─ Game State
        ├─ Required Game Logic
        ├─ RNG / Reward Authority
        └─ SQLite Persistence
        │
        │ Response
        ▼
Original Client
        │
        └─ Existing Parser / Manager / UI / Gameplay
```

## 2. 왜 방향을 변경하는가

이 게임은 사용자 단말에 전통적인 세이브 파일이 존재하는 구조가 아니라 **서버 authoritative state에 강하게 의존하는 Full Network Game에 가깝다.**

한 번의 행동도 단순 결과 하나가 아니라 여러 상태를 변경할 수 있다.

예: 던전 클리어

```text
Dungeon Enter
 → 실제 보상 확정
 → Battle
 → Clear
 → Reward
 → Star
 → Clear Count
 → Achievement
 → Mission / Event Progress
 → Currency / EXP
 → Inventory
 → 기타 Flags / History
```

이 모든 상태를 APK 내부에서 새 LocalPlayerState와 Persistence 계층으로 하나씩 재구현하면 작업량과 누락 위험이 커진다.

반면 Local Server 방식에서는 서버가 원래 담당하던 **Player State와 Transaction을 서버 쪽에서 유지**하고, 클라이언트는 기존 Response 처리 경로를 최대한 재사용할 수 있다.

## 3. KingBugCastle은 참고 모델이지 복제 대상이 아니다

KingBugCastle의 Private Server 사례는 다음 개념의 참고 모델로 사용한다.

- 원본 클라이언트 유지
- 로컬 API 서버 제공
- 서버 상태를 SQLite 등으로 유지
- Request/Response 기반 기능별 구현
- 필요할 때만 클라이언트 패치
- 기능을 실제 게임 진행 순서대로 점진 구현

단, 해당 프로젝트의 endpoint/model/코드를 우리 게임에 그대로 적용한다고 가정하지 않는다.

우리 게임의 실제 Request, Response, 암호화, 인증, 데이터 모델, State 구조를 역분석으로 증명한다.

## 4. 핵심 설계 원칙

### 4.1 Client를 최대한 보존한다

가능하면 다음을 그대로 사용한다.

- Response parser / Deserialize
- Result/Data Object
- Manager / Singleton
- 기존 UI
- 기존 전투 로직
- 기존 결과 표시 로직
- 기존 데이터 모델

클라이언트 패치는 **서버 주소/통신 계층/필수 인증·무결성·업데이트 경로 등 Local Server 연결에 필요한 최소 범위**부터 시작한다.

### 4.2 서버가 권한을 가진 상태는 Local Server가 관리한다

```text
Account
Currency
Characters
Inventory
Equipment
Stage/Dungeon Progress
Achievement
Mission
Gacha State
Shop State
Event State
Mail/Attendance
Flags/History
```

실제 존재 여부와 필드는 반드시 Response/State 분석으로 확정한다.

### 4.3 Response를 하나씩 수동 패치하지 않는다

핵심은 수백 개의 Response를 각각 APK 내부에서 처리하는 것이 아니다.

```text
Request
 ↓
Local API Handler
 ↓
Game/State Transaction
 ↓
Response
```

라는 공통 서버 계층을 만들고, 클라이언트가 기대하는 Response contract를 맞춘다.

### 4.4 게임 로직은 필요한 만큼만 구현한다

처음부터 서버의 모든 내부 알고리즘을 완벽하게 복제하지 않는다.

우선:

```text
Request가 무엇을 요구하는가?
Response의 필수 필드는 무엇인가?
Response 이후 Client가 무엇을 하는가?
State에는 무엇이 저장되어야 하는가?
```

를 확인한다.

그 뒤 클라이언트가 직접 처리하는 로직은 그대로 두고, **서버에서 반드시 생성해야 하는 값만 Local Server에서 구현**한다.

## 5. State와 Transaction

Local Server의 핵심은 API 숫자가 아니라 Player State다.

권장 개념 구조:

```text
API Request
   ↓
Command / Action
   ↓
Validation
   ↓
Transaction
   ├─ State 변경
   ├─ Result 생성
   └─ History/Event 기록
   ↓
Persistence
   ↓
Response
```

예: 던전 클리어

```text
DUNGEON_CLEAR
 ├─ reward
 ├─ star
 ├─ clear_count
 ├─ achievement_progress
 ├─ mission_progress
 ├─ currency
 ├─ exp
 ├─ inventory
 └─ history
```

가능하면 하나의 논리적 Action에서 관련 상태 변경이 함께 반영되도록 한다.

## 6. 던전 기준

현재 확정된 사용자 관찰을 유지한다.

- 화면의 10개 안팎 보상 목록은 후보 목록이다.
- 실제 획득 보상은 보통 2~3개 수준의 기본 + 랜덤 조합이다.
- **실제 보상은 전투 승리 시점이 아니라 던전 입장 시 서버가 결정한다.**
- 이후 전투 성공 시 이미 결정된 보상을 표시/적용한다.

Local Server에서는:

```text
Dungeon Enter Request
 → Eligibility Check
 → Reward Generation
 → Actual Reward 확정/저장
 → Enter Response

Battle
 → Battle Result
 → Existing Client Result Flow

Dungeon Clear
 → 확정 Reward Apply
 → Star/Progress/Achievement/Mission 등 State Transaction
 → Response
```

## 7. 가챠 기준

현재 확정된 구조:

```text
Gacha/Banner
 → Gacha Request
 → Server RNG / Count / Result
 → Response
 → Client Result UI
 → Inventory/Character State
```

Local Server에서는 가챠 실행 시 결과를 결정하고, 재화/보유 캐릭터/아이템/카운트 등의 상태를 함께 관리한다.

배너, 확률, 천장, 중복 처리 등의 구체 규칙은 실제 데이터와 코드로 증명하기 전까지 임의로 만들지 않는다.

## 8. API 분석 순서

모든 핵심 API는 다음 순서로 기록한다.

```text
Endpoint / Command
 ↓
Request 생성 함수
 ↓
Serialize / Encrypt
 ↓
Network Send
 ↓
Response Receive
 ↓
Decode / Decrypt
 ↓
Deserialize
 ↓
Response Model
 ↓
Client Handler
 ↓
State Effect
```

기록 필드:

- API/Command 식별자
- Request type
- Response type
- endpoint/route
- serialization format
- encryption/decryption path
- 성공/실패 code
- 필수 Request field
- 필수 Response field
- State effect
- 관련 Manager
- 관련 XREF
- 런타임 확인 결과

## 9. 개발 단계

### Phase 0 — Update Gate
업데이트/에셋 체크로 인해 게임 진입이 막히는 경로를 분리한다.

### Phase 1 — Protocol Discovery
로그인부터 실제 Request/Response 계약을 추출한다.

### Phase 2 — Local Server Bootstrap
최소 서버 + SQLite + health check를 만든다.

### Phase 3 — Login / Main Bootstrap
로그인 → 초기 Player State → Main Menu를 성립시킨다.

### Phase 4 — Core State
Currency / Character / Inventory / Progress 등 핵심 State를 구축한다.

### Phase 5 — Dungeon / Battle
Dungeon Enter 보상 확정 → Battle → Clear Transaction을 구현한다.

### Phase 6 — Gacha / Shop
가챠/상점 Request/Response와 State Transaction을 구현한다.

### Phase 7 — Mission / Achievement / Event / Mail
액션 결과로 파생되는 상태를 확장한다.

### Phase 8 — Asset / CDN
서버 API와 별개인 AssetBundle/CDN 의존성을 로컬 데이터 공급으로 처리한다.

### Phase 9 — APK Minimal Adaptation
필요한 통신 주소, TLS, 인증/무결성, 업데이트 경로만 패치한다.

### Phase 10 — Full Runtime Validation
인터넷 차단 상태에서 로그인부터 주요 콘텐츠까지 실제 플레이를 검증한다.

## 10. 분기 조건

다음 경우 Local Server 방식을 계속 확장한다.

- Client가 Response를 중심으로 동작한다.
- Server authoritative state가 명확하다.
- 기존 Client parser/result/UI를 재사용할 수 있다.
- API를 기능 단위로 에뮬레이션할 수 있다.

다음 경우에만 Client Local Logic 비중을 늘린다.

- 특정 결과 생성에 필요한 로직이 Client에 이미 존재한다.
- Local Server가 불필요하게 복잡해지는 기능이 있다.
- Client가 이미 가진 데이터/계산을 재사용하는 편이 명백히 단순하다.

**따라서 최종 구조는 순수 Local Server만을 강제하지 않는다. Local Server를 중심으로 하되 Client의 기존 로직을 최대한 재사용하는 Hybrid 구조를 허용한다.**

## 11. 작업 분담

```text
GPT
 ├─ 분석
 ├─ 증거 해석
 ├─ 다음 TASK 결정
 ├─ 아키텍처 판단
 └─ 패치 방향 결정

Codex
 ├─ Ghidra
 ├─ APK / native 파일
 ├─ API tracing
 ├─ Local Server 구현
 ├─ APK build/sign/install
 ├─ ADB/logcat
 └─ 결과 MD 기록

사용자
 └─ 실제 화면/게임 동작 확인
```

이 역할 분리는 기존 프로젝트 원칙을 유지한다.

## 12. 성공 기준

단순히 메인 화면이 뜨는 것으로 성공 처리하지 않는다.

최종 성공은 다음을 의미한다.

```text
인터넷 없음
 ↓
Local Server
 ↓
Login
 ↓
Main
 ↓
Dungeon / Battle / Gacha / Shop 등
 ↓
State Transaction
 ↓
SQLite Persistence
 ↓
앱 재실행
 ↓
State 복원
 ↓
기존 Client UI/Gameplay 정상 동작
```

그리고 각 기능에서 **화면 표시와 실제 State 변경이 모두 일치**해야 한다.

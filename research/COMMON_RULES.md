# COMMON_RULES — 프로젝트 공통 작업 규칙

> 아르메블랑쉐의 Reverse Engineering / Protocol / Local Server / APK 작업에 공통 적용한다.

## 1. 최상위 방향

**Local Private Server / API Emulation + Original Client Reuse + 필요한 경우 Hybrid**를 기본 방향으로 한다.

완전 Client Local화는 기본 방향이 아니다. 목표는 원본 서버 전체 복제가 아니라, 원본 Client가 기대하는 통신/Response 계약을 유지하면서 필요한 서버 authoritative state와 서비스를 Local Server에서 제공하는 것이다.

```text
Original/Patched Client
        ↕
Original Client가 기대하는 Protocol/Response
        ↕
Local Private Server
        ↕
SQLite / State / 필요한 Game Logic
```

## 2. 통신 방향: TLS/원본 통신을 먼저 보존

현재 단계에서는 **TLS 완전 복제** 또는 **통신 구조 전면 변경**을 선결정하지 않는다. 대신 **원본 통신/TLS/Application Crypto 경로를 최대한 보존하는 것을 1순위 가설**로 두고 실제 분석으로 필요한 최소 변경점을 찾는다.

KBC가 참고 모델로 보여주는 다음 구조는 방향성 참고만 한다.

```text
Bypassed TLS via ARM64 Patch
Fetch XML Patch Bundles
Faked Seed Handshake
Android Client / Emulator
Local / Public FastAPI Server
Local XML CDN
Xigncode Stub + il2cpp hooks
JSON rules + SQLite saves
```

KBC의 방식·키·인증서·seed·주소·offset·anti-cheat 처리를 현재 게임에 그대로 적용하지 않는다.

### 통신 호환성 단계

**Level 1 — Original Wire/TLS Compatibility**
- 원본 TLS transport
- certificate/hostname 검증 경로
- application protocol/framing
- serialize/deserialize
- application encrypt/decrypt
- authentication/session

을 가능한 한 유지하고 Local Server가 종단을 제공한다.

**Level 2 — Minimum Client Communication Adapter**

Level 1이 폐쇄된 원격 서버, 인증서/pinning, hostname 등 때문에 불가능할 때 통신 계층의 필요한 최소 부분만 Client에서 수정한다.

**Level 3 — Feature-level Hybrid**

특정 기능은 Client 기존 로직을 재사용하는 편이 명백히 단순할 경우 해당 기능만 Hybrid/local 처리한다.

### 증거 없이 하지 않는 것

- TLS를 HTTP/plaintext로 전면 교체
- application encrypt/decrypt 삭제 또는 전면 재작성
- decrypt/serialize 경로 전체 교체
- anti-cheat/Xigncode 무차별 제거
- native hook 대량 적용
- 모든 network function을 Client-local로 치환

## 3. TLS와 Application Crypto를 분리

긴 암호문/Base64-like payload나 decrypt 함수의 존재만으로 그것이 TLS라고 단정하지 않는다.

다음을 XREF/caller/callee와 런타임 흐름으로 분리한다.

```text
TLS/Transport
Application Crypto
Packet Integrity/Signature
Authentication/Session
Anti-cheat / Integrity Check
Asset/Bundle Crypto
Save/Data Crypto
```

```text
Decrypt 코드 존재
≠ 통신 암호화가 TLS
≠ Decrypt 코드가 Anti-cheat
≠ Anti-cheat 수정이 통신에 필요
```

## 4. Client 보존 원칙

가능하면 Request/Response model, Serializer/Deserializer, Encrypt/Decrypt, Network client, Response handler, Manager, Data object, UI, 기존 전투/결과 로직을 그대로 재사용한다.

Client 패치는 Local Server 연결에 필요한 최소 범위부터 시작한다.

## 5. Local Server는 Response만 흉내 내지 않는다

```text
Request
 ↓
Validate
 ↓
Action / Transaction
 ↓
State Mutation
 ↓
History/Event
 ↓
SQLite Commit
 ↓
Response
```

`success=true` 같은 최소 응답만으로 기능 완료를 확정하지 않는다.

## 6. Protocol Contract와 Game State Schema를 분리

초기부터 거대한 DB schema를 만들지 않는다.

```text
API Request/Response Contract
 ↓
Client Object
 ↓
State Mutation
 ↓
Next API Dependency
```

실제로 확인된 필드만 State/SQLite에 반영한다.

## 7. State Graph를 누적

핵심 기능은 다음을 기록한다.

```text
API
 ↓
Response Object
 ↓
Manager / Handler
 ↓
State Mutation
 ↓
Persistence
 ↓
다음 API에서 사용하는 State
```

필드와 해석은 `CONFIRMED / PROBABLE / UNKNOWN`으로 관리한다.

## 8. Login 최소 성공 경로

첫 목표는:

```text
Login Request
 ↓
Local Server
 ↓
Minimum Valid Response
 ↓
Existing Decode/Deserialize
 ↓
Login Complete
 ↓
Initial State
 ↓
Main Menu
```

Main 진입 후 실제 필요한 bootstrap API를 순차적으로 추가한다.

## 9. Dungeon / Gacha

Dungeon은 현재 분석 기준으로 **Enter에서 실제 보상을 확정하고 session에 저장한 뒤 Clear에서 적용**한다. Battle Victory에서 새 RNG로 다시 생성하지 않는다.

Gacha는 기본적으로 `Request → Server Result/State Transaction → Response → Existing Client Result UI` 구조를 사용한다. 확률/천장/중복 규칙은 실제 증거 전까지 임의로 만들지 않는다.

## 10. Asset/CDN과 통신/보안 트랙 분리

```text
Track A: API / Protocol / Player State
Track B: AssetBundle / CDN / Update Assets
Track C: Client TLS / Certificate / Pinning
Track D: Anti-cheat / Integrity
```

한 트랙의 문제를 다른 트랙의 원인으로 추정하지 않는다.

## 11. Anti-cheat는 최소 변경

Anti-cheat/Xigncode/무결성 코드는 실제 실행 경로와 차단 기능을 확인하고 Local Server 연결에 직접 필요한지 확인한 뒤 필요한 최소 범위만 변경한다.

`decrypt 쪽에 anti-cheat 코드가 많다`는 관찰만으로 전체 수정 대상으로 확정하지 않는다.

## 12. Investigation과 Implementation 분리

### Investigation
- 수정하지 않는다.
- XREF / decompile / assembly / runtime을 수집한다.
- `research/reports/TASK-xxx-result.md`에 기록한다.

### Implementation
- GPT가 결정한 범위만 수정한다.
- 한 번에 하나의 관찰 가능한 효과를 만든다.
- build/install/runtime 검증 후 기록한다.

## 13. 증거 우선순위

```text
Runtime behavior
 > Concrete caller/callee + XREF
 > Decompile + Assembly
 > Metadata / dump.cs 이름
 > KBC reference
 > 추측
```

KBC는 현재 게임의 사실을 대신 증명하지 않는다.

## 14. KBC 사용 규칙

### 참고 가능
- Private Server/API 구조
- FastAPI route/service 분리
- SQLite persistence 패턴
- Action → Validate → State Mutation → Commit → Response
- JSON 정적 데이터와 DB 상태 분리
- Local CDN 구조
- build/automation workflow
- 일반적인 ARM64 client adaptation 아이디어

### 현재 게임에 그대로 복사 금지
- endpoint / URL / domain / IP / port
- request/response schema
- token/auth/session 규칙
- TLS certificate/pinning
- key/seed/crypto value
- item/character/stage ID
- reward/probability/balance
- server state schema
- binary offset/hook
- anti-cheat patch target
- protocol header/version/magic

**KBC는 "어떻게 만들었는가"의 참고서이고, 현재 게임은 "무엇을 구현해야 하는가"의 증거다.**

## 15. 작업 분담

```text
GPT     → 분석 / 증거 해석 / TASK / 아키텍처 / patch 결정
Codex   → Ghidra / tracing / runtime / Local Server / APK / Git 기록
사용자  → 실제 화면 및 게임 동작 확인
```

사용자에게 ADB, logcat, terminal, APK 설치/삭제 등의 기술 작업을 요구하지 않는다.

## 16. 현재 결론

**현재는 TLS를 버리고 구조를 새로 만드는 방향보다, 원본 통신 스택을 최대한 보존하면서 Local Server 종단을 맞추는 방향으로 조사한다.**

단, 이것은 "TLS 완전 복제를 지금 확정한다"는 뜻이 아니다. 먼저 현재 게임의 TLS transport, application-level crypto, 인증/세션, 무결성/anti-cheat의 실제 관계를 증명한다.

따라서 순서는:

```text
원본 TLS/Protocol 분석
 ↓
Application Crypto/Session 분석
 ↓
Local Server 종단 가능성 확인
 ↓
가능하면 Original Wire/TLS Compatibility
 ↓ 불가능한 부분만
Minimum Client Communication Adapter
 ↓
필요한 기능만 Hybrid
```

**TASK-006 Login API Contract는 이 결정을 증명하기 위한 핵심 조사 단계이며, Login → Main이 확인되기 전에는 서버 전체 구현이나 대규모 anti-cheat/decrypt 패치를 시작하지 않는다.**

## 17. 완료 기준

```text
Request
 → Transport
 → Response
 → Decode/Deserialize
 → Client Handler
 → State Mutation
 → Persistence
 → Next Action에서 재사용
 → 앱 재실행 후 복원
```

확인되지 않은 부분은 UNKNOWN으로 남긴다.

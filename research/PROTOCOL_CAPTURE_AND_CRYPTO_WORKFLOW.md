# Protocol Capture / Crypto 분석 작업 절차

> 정상 서버에서 수집한 PCAP/패킷과 현재 게임 Client의 IL2CPP/Ghidra 분석을 연결하여 Local Private Server가 처리해야 할 실제 Protocol Contract를 확립하기 위한 작업 문서다.
>
> **목표는 암호화를 무조건 제거하거나 깨는 것이 아니라, 원본 Client가 사용하는 Transport/TLS/Application Crypto/Serialize/Deserialize 경로를 증명하고 가능한 한 그대로 재사용하는 것이다.**

## 1. 핵심 원칙

현재 프로젝트의 기본 방향은 `Local Private Server / API Emulation + Original Client Reuse + 필요한 경우 Hybrid`다.

PCAP은 서버의 정답 데이터 자체가 아니라 **통신의 관찰 증거**다. PCAP만 보고 Protocol이나 암호화 방식을 확정하지 않는다.

증거 우선순위:

```text
Runtime behavior
 > Concrete caller/callee + XREF
 > Decompile + Assembly
 > PCAP / packet structure
 > Metadata / dump.cs 이름
 > KBC reference
 > 추측
```

PCAP과 Client 분석 결과가 일치할 때 Contract의 신뢰도를 올린다.

## 2. 반드시 분리해서 분석할 계층

패킷 하나를 발견했다고 해서 그것이 곧 "암호화된 API"라는 의미는 아니다.

다음 계층을 별도로 확인한다.

```text
Application Object
 ↓
Serialize
 ↓
Compression / Encoding (있는 경우)
 ↓
Application Encryption (있는 경우)
 ↓
Packet Framing / Integrity / Signature
 ↓
TLS / Transport
 ↓
Network
```

Response는 반대 방향이다.

```text
Network / TLS
 ↓
Packet Framing
 ↓
Application Decrypt
 ↓
Decode / Decompress (있는 경우)
 ↓
Deserialize
 ↓
Response Object
 ↓
Manager / Handler
```

**TLS와 Application Crypto를 혼동하지 않는다.** 긴 Base64-like 문자열, 높은 엔트로피, decrypt 함수의 존재만으로 TLS 또는 특정 암호 알고리즘이라고 단정하지 않는다.

## 3. PCAP 수집 시 작업 방식

가능한 정상 서버 접근 기능을 실제 게임에서 순서대로 수행하고 PCAP을 수집한다.

처음부터 전체 게임을 한 번에 수집하지 않는다.

권장 순서:

```text
1. 앱 시작
2. 로그인
3. Main 진입
4. Main bootstrap
5. Player/Inventory 조회
6. Shop 진입
7. Dungeon 진입
8. Battle/Result
9. Gacha
10. Mission/Event/Mail 등
```

각 행동은 가능한 한 **한 행동 = 한 분석 단위**로 구분한다.

예:

```text
LOGIN
MAIN_BOOTSTRAP
PLAYER_REFRESH
SHOP_OPEN
DUNGEON_ENTER
BATTLE_RESULT
GACHA_EXECUTE
```

정상 게임에서 접근할 수 없는 기능은 억지로 접근하려 하지 않는다. Client static analysis로 Request/Response 경로를 추적하고 나중에 Local Runtime에서 검증한다.

## 4. PCAP 1차 분석

각 PCAP에 대해 다음만 먼저 추출한다.

- 통신 flow
- 목적지 host/IP
- port
- protocol/TCP/UDP
- TLS handshake 존재 여부
- packet 방향(C→S / S→C)
- packet length
- 반복되는 framing/header 후보
- 동일 행동에서 반복되는 packet sequence
- payload가 평문인지 encoded/encrypted처럼 보이는지

이 단계에서는 암호를 풀려고 하지 않는다.

### 결과 예시

```text
Action: SHOP_OPEN
Flow: C→S / S→C
Transport: TCP
TLS: confirmed / probable / unknown
Application payload: encrypted-looking
Framing: candidate header 12 bytes
Request count: 1
Response count: 2
```

## 5. Client에서 동일 Packet을 만드는 코드 찾기

PCAP의 목적지/경로/패킷 크기/행동 시점을 단서로 Client를 역추적한다.

반드시 다음 체인을 찾는다.

```text
Request Creator
 → Request Object
 → Serialize
 → Encrypt/Encode
 → Network Send
```

그리고 Response는:

```text
Network Receive
 → Framing
 → Decrypt/Decode
 → Deserialize
 → Response Object
 → Handler
 → State Mutation
```

Ghidra에서는 함수 이름만 믿지 않고 XREF/caller/callee와 실제 assembly/decompile 흐름을 확인한다.

## 6. 암호화 분석의 목표

목표는 "암호를 깨는 것" 자체가 아니다.

다음 질문에 답하는 것이 목표다.

### Request
- 평문 Request Object는 무엇인가?
- 어떤 serializer를 사용하는가?
- 압축/encoding이 있는가?
- application encryption이 있는가?
- key/IV/nonce/session 값은 어디에서 오는가?
- packet framing은 어떻게 만들어지는가?
- integrity/signature가 있는가?

### Response
- 서버가 어떤 payload를 반환하는가?
- Client가 어느 함수에서 복호화하는가?
- 복호화 직후 어떤 byte/string/object가 되는가?
- 어떤 serializer/deserializer로 객체가 되는가?
- Response Object가 어느 Manager로 전달되는가?

## 7. 키/암호 파라미터 조사

키나 IV 등의 값이 발견되더라도 즉시 문서에 실제 비밀값을 복사하는 것을 목표로 하지 않는다.

먼저 다음을 분류한다.

```text
STATIC
- 바이너리에 고정

DERIVED
- 다른 값에서 계산

SESSION
- 로그인/세션 과정에서 생성 또는 수신

PER_REQUEST
- 요청마다 변경

SERVER_PROVIDED
- 서버 응답에서 획득

UNKNOWN
```

목표는 Local Server가 Client와 호환되는 데 필요한 **생성 규칙과 교환 흐름**을 증명하는 것이다.

## 8. 암호화된 Response를 Contract로 바꾸는 방법

Raw PCAP의 긴 ciphertext/Base64-like 문자열을 GPT에게 계속 전달하지 않는다.

Codex가 가능한 범위에서 다음 형태로 정규화한다.

```text
Action: PLAYER_REFRESH
Request:
  endpoint/operation: CONFIRMED
  fields:
    playerId: CONFIRMED

Response:
  encrypted: yes
  decrypt function: <function/RVA>
  deserialize function: <function/RVA>
  object/class: <type>
  fields:
    currency: CONFIRMED
    inventory: PROBABLE
    itemId: CONFIRMED

State Effect:
  PlayerState.currency ← response.currency

Next Dependency:
  SHOP_OPEN uses PlayerState.currency

Evidence:
  PCAP + XREF + runtime

Confidence: A/B/C
```

GPT에는 이 요약 Contract와 핵심 증거만 전달한다. Raw PCAP은 로컬에 보존한다.

## 9. Response Contract와 Master Data를 함께 구축

Response에서 발견되는 ID는 별도의 Master Data 후보로 추출한다.

```text
Response
 ├─ itemId ─────→ Item Master
 ├─ monsterId ──→ Monster Master
 ├─ stageId ────→ Stage Master
 ├─ characterId → Character Master
 └─ rewardId ───→ Reward Master
```

예:

```text
Item 10001
- type: CONFIRMED
- attack: CONFIRMED
- rarity: PROBABLE
- maxLevel: UNKNOWN
- evidence: Response / Client data
```

각 Master Data 항목은 다음 상태를 유지한다.

```text
CONFIRMED  실제 응답/런타임/명확한 코드 근거
PROBABLE   강한 정황이나 직접 검증 부족
UNKNOWN    의미 또는 값 미확정
```

Client asset/static data만으로 발견한 값은 실제 서버 authoritative state와 동일하다고 단정하지 않는다.

## 10. Contract Registry

기능별로 누적한다.

```text
research/contracts/
├─ AUTH.md
├─ PLAYER.md
├─ SHOP.md
├─ DUNGEON.md
├─ BATTLE.md
├─ GACHA.md
├─ MISSION.md
└─ EVENT.md
```

각 Contract는 최소 다음을 포함한다.

- Action
- Request fields
- Response fields
- Transport/Protocol evidence
- Encode/Encrypt evidence
- Decode/Decrypt evidence
- Response Object
- Client Handler
- State Effect
- Persistence Effect
- Next API dependency
- Evidence source
- Confidence
- Runtime verified 여부

## 11. Local Server 구현으로 넘어가는 조건

패킷 하나를 봤다고 바로 Server endpoint를 구현하지 않는다.

최소한 다음 체인이 확보된 기능부터 구현한다.

```text
PCAP / Static evidence
 ↓
Request Contract
 ↓
Response Contract
 ↓
Client Decode/Deserialize 확인
 ↓
Client Handler 확인
 ↓
필요 State 확인
 ↓
Local Server transaction 설계
 ↓
Local Runtime 검증
```

서버는 단순히 `success=true`를 반환하는 방식이 아니다.

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

## 12. Login 우선

현재 첫 목표는 Login → Main이다.

따라서 PCAP 분석도 우선 로그인 관련 flow를 완성한다.

```text
Login Request
 → Serialize
 → Encrypt/Encode
 → Transport
 → Local Server
 → Response
 → Client Decrypt/Decode
 → Deserialize
 → Login Complete
 → Bootstrap
 → Main Menu
```

Login이 확인되면 Main bootstrap에서 필요한 Response Contract를 하나씩 추가한다.

## 13. 실패 시 분기

### Level 1 — Original Wire/TLS Compatibility

원본 Client의 transport/TLS/application protocol을 최대한 유지하고 Local Server가 종단을 제공한다.

### Level 2 — Minimum Client Communication Adapter

원격 인증서/hostname/pinning 등으로 Level 1이 막히는 경우 필요한 최소 통신 부분만 수정한다.

### Level 3 — Feature-level Hybrid

특정 기능만 Client 기존 로직 또는 local 처리로 전환한다.

증거 없이 TLS 전면 제거, application crypto 전면 삭제, network stack 전체 교체를 하지 않는다.

## 14. PCAP → Contract 자동화 방향

장기적으로 Codex가 다음 파이프라인을 자동화하는 것을 목표로 한다.

```text
PCAP
 ↓
Flow grouping
 ↓
Packet sequence grouping
 ↓
Duplicate/variable field detection
 ↓
Candidate Request/Response pairing
 ↓
Client function correlation
 ↓
Decrypt/Deserialize correlation
 ↓
Contract summary
 ↓
Master ID extraction
 ↓
research/contracts + research/master_data
```

자동화가 확실하지 않은 부분은 `UNKNOWN`으로 남기고 사람이 확인한다.

## 15. GPT Token 절약 규칙

- Raw PCAP 전체를 GPT에 반복 전달하지 않는다.
- 동일 payload/flow는 deduplicate한다.
- packet length/hex dump 전체보다 구조 요약을 우선한다.
- 암호문 자체보다 `decrypt 함수 → 평문 object → deserialize class` 연결을 우선한다.
- GPT에는 새로운 사실/충돌/핵심 증거만 전달한다.
- 원본 PCAP과 상세 분석 결과는 로컬에 보존한다.

## 16. 현재 업로드된 PCAP 작업

사용자가 정상 게임에서 여러 기능을 수행하며 수집한 `PCAPdroid_11_9월_18_22_06.pcap`은 **Protocol Capture 분석 자료**로 취급한다.

첫 작업은 이 파일에서 flow/packet structure를 정리하고, 기존 Ghidra에서 확인된 Network/Encrypt/Decrypt 함수와 대응 관계를 찾는 것이다.

파일 자체만으로 암호화 알고리즘을 확정하지 않는다. PCAP과 Client static/runtime evidence가 연결된 경우에만 다음 단계로 진행한다.

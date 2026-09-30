# TASK-006 — Login API Contract / Local Server Bootstrap 조사

## 목적

아키텍처 방향을 **Local Private Server / API Emulation**으로 전환한 후 첫 구현 단위다.

목표는 로그인 기능을 패치로 강제 성공시키는 것이 아니라, **원본 Client가 로그인 시 보내는 Request와 기대하는 Response를 증거로 규격화하고 최소 Local Server Response로 Main Menu까지 연결할 수 있는지 확인하는 것**이다.

## 범위

```text
Login UI
 ↓
Login Request 생성
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
Login Response Object
 ↓
Login Complete / Callback
 ↓
Initial Player State
 ↓
Main Menu Bootstrap
```

## 반드시 조사할 것

### 1. Request
- 로그인 버튼/자동 로그인 진입점
- Request 생성 함수
- Request type / DTO
- 주요 field
- Account ID / user identifier
- device/app/version 정보
- session/token 관련 값
- serializer
- encryptor
- 실제 endpoint/command

### 2. Response
- Response type
- raw response 구조
- decode/decrypt 함수
- deserialize 함수
- result/status code
- 성공 callback
- 실패 callback
- token/session 생성값

### 3. Initial State
Login Response 또는 후속 bootstrap Response가 생성/갱신하는 객체를 추적한다.

후보:
- Account
- Player
- Currency
- Character
- Inventory
- Stage/Progress
- Mail
- Mission
- Event
- Shop
- Gacha/Banner

각 항목은 실제 코드/XREF로 확인하고 추측하지 않는다.

### 4. Main Menu
- Login Complete 이후 호출되는 함수
- 추가 bootstrap API
- Main Menu 진입 조건
- 특정 Response가 없으면 어디에서 대기/실패하는지

## Local Server 설계에 필요한 결과

보고서에 다음 표를 작성한다.

| 항목 | 결과 |
|---|---|
| API/Command | |
| Endpoint | |
| Request Type | |
| Required Request Fields | |
| Response Type | |
| Required Response Fields | |
| Result Code | |
| Client Handler | |
| State Effect | |
| Persistence Effect | |
| Next API | |

## 최소 Response 실험

조사 단계에서 임의 패치를 하지 않는다.

분석이 끝난 뒤 별도 구현 TASK에서 다음을 목표로 한다.

```text
Client Login Request
       ↓
Local Server
       ↓
Minimum Valid Login Response
       ↓
Existing Client Parser
       ↓
Login Complete
       ↓
Main Menu
```

Main Menu까지 가지 못하면 **어느 Response/State/bootstrap 단계에서 멈추는지** 다음 조사 대상으로 기록한다.

## 중요 원칙

1. 서버의 전체 로그인 시스템을 복제하지 않는다.
2. Client가 실제로 요구하는 필드부터 확정한다.
3. Response가 State를 변경하는지 별도로 추적한다.
4. Client에 이미 존재하는 Player/Data Object는 Local Server에서 중복 구현하지 않는다.
5. 암호화 패킷을 수동 해독하는 것이 목적이 아니다. Client의 Decode → Decrypt → Deserialize path를 찾는다.
6. 조사 중에는 APK/서버 코드를 수정하지 않는다.
7. 결과는 `research/reports/TASK-006-result.md`에 기록한다.

## 완료 조건

다음 중 하나로 종료한다.

- Login Request/Response contract와 Main Menu bootstrap이 증거로 확인됨
- 특정 Response/State 의존성이 확인되어 다음 TASK가 명확함
- 추가 분석 없이는 확인할 수 없는 이유가 명확함

Codex는 결과를 기록하고 GPT의 다음 구현/조사 판단을 기다린다.


---

# 2026-09-28 추가 지시 — Game Server Login Contract 확정

현재 TASK-006 결과와 최신 runtime/PCAP/Ghidra 분석을 기준으로, 다음 작업은 **DH64 복호화를 먼저 완료하는 것이 아니라 Game Server Login Request/Response Contract를 최대한 확정하는 것**으로 한다.

## 1. ProtocolGame_SendRequest.Login 분석

대상:

- `ProtocolGame_SendRequest.Login()`
- RVA: `0xCDE818`

확인:

- 생성하는 `OpInfo`
- `OpCode` 및 Login opcode 값
- `SerialNumber`
- `User` 관련 필드
- Token 관련 필드
- 기타 설정 필드
- serializer
- encrypt/decode 관련 함수
- `CSBehaviour.RequestOp()` 연결
- 실제 Network Send까지 caller/callee

각 필드는 가능하면 decompile/assembly의 실제 assignment 근거를 기록한다.

## 2. CSBehaviour.Response 분석

대상:

- `CSBehaviour.Response(Commands, OpInfo)`
- RVA: `0x15DCD50`

다음 체인을 추적한다.

```
Network Receive
 → framing
 → decrypt/decode
 → deserialize
 → OpInfo
 → CSBehaviour.Response
```

확인:

- `Commands.CmdRequest`
- `Commands.CmdEncrypt`
- `Commands.CmdCompress`
- ReturnCode 처리
- OpCode 분기
- Login Response 분기
- `Request.SetResponse()`
- callback 연결

## 3. DataCenter.ProccessRequestRes 분석

Login Response가 Client State를 어떻게 변경하는지 추적한다.

특히 다음 객체가 실제 Login 처리에서 사용되는지 확인한다.

- User
- Heros
- Items
- Weapons
- Equiments
- Mails
- Chapters
- Sections
- Teams
- Shops
- Activities

각 항목을 `CONFIRMED / PROBABLE / UNKNOWN`으로 분류한다.

## 4. HTTP Login 연결 확인

다음 함수도 계속 추적한다.

- `ProtocolGame_HttpRequest.V4_POST_Login`
- `ProtocolGame_HttpRequest.V3_POST_Anon`
- `ProtocolGame_HttpRequest.Sign`

확인:

- 실제 URL/path
- parameter dictionary
- uid
- pwd
- type
- device
- version
- retail
- token
- sign 대상 및 호출 순서

Sign 알고리즘은 함수명만으로 확정하지 말고 실제 decompile/assembly 근거를 기록한다.

## 5. Runtime 증거 연결

2026-09-28 runtime에서 확인된:

```
Ali.DoHttpCallBack
 → NetworkCenter
 → CSBehaviour.Connect
 → 182.92.62.79:8000 TCP connection attempt
```

을 기존 PCAP의 Game Server endpoint와 연결하여, HTTP callback 이후 Game Server Login 단계가 실제 실행되는지 확인한다.

## 6. DH64 분석은 병행하되 Login Contract 분석을 막지 않는다

다음은 별도 경로로 계속 조사한다.

```
KCPTube.Handshake1
 → DH64.KeyPair #1/#2
 → private/public
```

PCAP에서 확인된:

```
clientPublic1 = 0x1f594d0100000169
clientPublic2 = 0xe8986e3637f5aba4
```

와 runtime KeyPair 결과를 연결한다.

단, private key를 PCAP만으로 역산하지 않는다.

## 7. 조사 단계 제한

이번 작업에서는 다음을 하지 않는다.

- APK 수정
- libil2cpp 수정
- 임의 Hook 적용
- 임의 Login Response 생성
- Local Server 구현
- DH private 추측
- Packet byte만 보고 protobuf/field 의미 확정

이번 단계는 조사와 증거 수집만 수행한다.

## 8. 보고서에 반드시 채울 Contract 표

| 항목 | 결과 | Confidence |
|---|---|---|
| HTTP Login endpoint | | |
| HTTP Request Type | | |
| HTTP Request fields | | |
| HTTP Sign | | |
| HTTP Response Type | | |
| Game Server endpoint | | |
| Game Login OpCode | | |
| Game Login Request fields | | |
| Game Login Response type | | |
| Decode/Decrypt | | |
| Deserialize | | |
| Response Handler | | |
| DataCenter State Effect | | |
| Main Bootstrap dependency | | |

최종적으로 다음 체인 중 어디까지 증명됐는지 명확하게 기록한다.

```
Login Request
 ↓
Game Server Login
 ↓
Response
 ↓
DataCenter
 ↓
Main Bootstrap
```

## 9. 종료 조건

다음 중 하나면 종료한다.

1. Game Server Login Request/Response Contract가 충분히 확정됨
2. 특정 Response/State에서 추가 조사가 필요한 지점이 명확해짐
3. 현재 증거로 더 이상 진행할 수 없는 구체적인 이유가 확인됨

완료 후 `research/reports/TASK-006-result.md`를 업데이트하고 GPT의 다음 판단을 기다린다.

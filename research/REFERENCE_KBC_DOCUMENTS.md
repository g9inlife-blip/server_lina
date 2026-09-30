# Reference: King Bug Castle(KBC) 관련 문서 정리

## 1. 목적

이 문서는 `참고용-another_app/`에 포함된 **King Bug Castle(KBC) Private Server / Reverse Engineering 프로젝트의 문서군**을 현재 프로젝트(아르메블랑쉐)에서 참고하기 위한 문서 인덱스다.

KBC는 현재 게임과 다른 게임이므로, 여기서는 **문서가 설명하는 방법·구조·workflow를 참고**한다. 현재 게임의 API, protocol, auth, crypto, state, reward, asset 데이터는 반드시 현재 게임 분석 결과로 확정한다.

---

## 2. KBC 문서군

### A. Login / Auth / Server Bootstrap

관련 문서 예:

- `SETUP.md`
- `HANDOVER.md`
- `server/README.md`
- `docs/README.md`
- `KNOWLEDGE.md`

참고할 핵심 흐름:

```text
Client 시작
  ↓
Login / Auth Request
  ↓
Local Server
  ↓
Session / Player State 초기화
  ↓
Minimum Valid Response
  ↓
Client Decode / Deserialize
  ↓
Initial State
  ↓
Main Menu
```

현재 프로젝트 적용 시에는 KBC의 endpoint나 auth 값을 복사하지 않고, 현재 게임에서 실제로 확인되는 Login Request → Response → Deserialize → Main 진입 흐름에 맞춘다.

**참고 가치: 매우 높음**

---

### B. CDN / Asset / XML

관련 문서 예:

- `docs/mftl-extraction.md`
- `SETUP.md`
- `server/README.md`
- KBC의 `server/xml_live/`, CDN 관련 script/history 문서

참고할 핵심 흐름:

```text
Client
  ↓
Version Check
  ↓
Manifest / Asset Index
  ↓
XML / Static Data
  ↓
AssetBundle
  ↓
Local CDN / Asset Server
```

현재 게임도 `GameUpdateService`, `AssetVersionManager`, `AssetDownloader`, `AssetBundleManager` 계열의 별도 Asset/CDN update 경로가 확인되어 있으므로, KBC의 **Local CDN 분리 구조**를 참고 가치가 높은 별도 track으로 둔다.

현재 분석에서 `GameUpdateService`는 Build/Server Version 확인, remote asset version/base URL 처리, manifest 다운로드, asset need-update 확인, AssetBundle 다운로드로 이어지는 구조가 확인되었다. 따라서 API 서버와 Asset/CDN 서버를 처음부터 하나의 개념으로 섞지 않는다.

**참고 가치: 매우 높음**

---

### C. Runtime / Build / Client Adaptation

관련 문서 예:

- `SETUP.md`
- `HANDOVER.md`
- `docs/README.md`
- KBC의 ARM64 build/rebuild 관련 문서 및 script 설명

참고할 핵심:

- APK rebuild / sign / install workflow
- ARM64 client adaptation의 단계 분리
- patch → build → runtime test의 반복 구조
- 서버와 client patch를 독립적으로 검증하는 방식
- 자동화 script를 통한 반복 작업 축소

현재 프로젝트에서는 Codex가 build/install/runtime 검증을 담당하고 사용자는 화면 결과만 확인하는 workflow와 연결한다.

**참고 가치: 높음**

---

### D. Handover / Knowledge / Investigation Workflow

관련 문서 예:

- `HANDOVER.md`
- `KNOWLEDGE.md`
- `docs/README.md`

참고할 핵심:

```text
분석
 ↓
증거 기록
 ↓
API / Model / State contract 정리
 ↓
Server route 추가
 ↓
Runtime 검증
 ↓
문서화
 ↓
다음 미매핑 영역으로 진행
```

현재 프로젝트에서도 `research/reports/TASK-xxx-result.md`를 통해 조사 결과를 남기고, 검증된 contract만 Local Server 구현으로 넘기는 방식으로 적용한다.

**참고 가치: 높음**

---

## 3. KBC에서 참고할 기술 패턴

### 3.1 FastAPI + Domain Route 분리

```text
server/
 ├─ routes/
 │   ├─ auth
 │   ├─ player
 │   ├─ game
 │   └─ ...
 ├─ data/
 ├─ state/
 └─ webui/
```

현재 프로젝트에서도 API를 기능/도메인별로 분리하는 구조를 참고한다.

### 3.2 Static Data와 Player State 분리

```text
Static Rules / Master Data
        +
Player State / Runtime State
        ↓
Local Server
```

초기에는 실제 state schema를 과도하게 설계하지 않고, 현재 게임 Request/Response와 State Effect를 확인하면서 확장한다.

### 3.3 Transaction 중심 처리

```text
Request
 → Validate
 → Action
 → State Mutation
 → History/Event
 → SQLite Commit
 → Response
```

재화, 보상, 인벤토리, clear count 등 여러 상태가 함께 변하는 기능에서 특히 참고한다.

### 3.4 Local CDN 분리

API 서버와 Asset/CDN 제공 서버를 별도 track으로 관리한다.

```text
Local API Server
        │
        └── gameplay / player / auth state

Local Asset/CDN Server
        │
        └── manifest / XML / bundle / static asset
```

---

## 4. 현재 프로젝트와의 연결

### Login

현재 1차 목표는 **Login → Main Menu**다.

KBC 문서는 다음을 설계하는 참고자료로 사용한다.

```text
Login Request
 → Transport
 → Local Server
 → Auth/Session
 → Minimum Response
 → Existing Decode/Deserialize
 → Login Complete
 → Initial State
 → Main
```

현재 게임의 실제 contract가 확인되기 전에는 KBC Login endpoint/schema를 구현하지 않는다.

### CDN

현재 게임의 Asset update path는 별도 track으로 유지한다.

이미 확인된 `GameUpdateService` 흐름은 대략 다음과 같다.

```text
Build/Server Version
 → Version Check
 → Best CDN / Remote Asset Base
 → AssetBundle Manifest
 → Asset Need Update
 → AssetBundle Download
 → Asset Update Complete
```

KBC의 Local CDN/asset mirroring 구조를 이 흐름을 로컬에서 재현할 때 참고한다.

---

## 5. 절대 복사하지 않는 것

KBC 문서에서 다음은 현재 게임의 증거가 없으면 사용하지 않는다.

- KBC endpoint / route 이름
- KBC domain / IP / port
- KBC request/response schema
- KBC account / token / auth 규칙
- KBC TLS certificate / pinning 대상
- KBC crypto key / seed / protocol magic
- KBC API header / version 값
- KBC item / character / stage / currency ID
- KBC reward / RNG / pity / duplicate 규칙
- KBC player DB schema를 현재 게임 schema로 간주하는 것
- KBC CDN URL / asset path
- KBC ARM64 binary offset / hook target
- KBC anti-cheat patch target
- KBC 게임 고유 balance/data

---

## 6. 참고 우선순위

현재 프로젝트에서의 증거 우선순위는 다음과 같이 유지한다.

1. 현재 게임 Runtime 결과
2. 현재 게임의 구체적인 XREF / caller / callee
3. 현재 게임 Ghidra decompile / assembly
4. 현재 게임 IL2CPP metadata / dump
5. 현재 게임 Request/Response 및 Decode/Decrypt/Deserialize 결과
6. KBC 문서의 구현 방식
7. 일반적인 추론

즉 **KBC는 구현 방법을 알려주는 참고 프로젝트이고, 현재 게임의 실제 contract를 결정하는 출처가 아니다.**

---

## 7. Codex 적용 규칙

Codex가 현재 게임의 Login/Server/CDN을 구현할 때 다음 문장을 기준으로 한다.

> KBC는 구조·기술·workflow 참고용으로만 사용한다. 현재 게임의 API/Protocol/Auth/Crypto/State/Data/Asset contract는 현재 게임 Reverse Engineering 증거로 확정한다. Client ↔ Local Server 연결은 원본 wire/TLS 호환 → 최소 client communication adapter → feature-level Hybrid 순으로 필요한 최소 변경을 선택한다.

또한 KBC 참고가 실제 구현에 사용된 경우 작업 결과에 **참고한 KBC 문서 경로와 현재 게임에서 별도로 검증한 근거**를 기록한다.

---

## 8. 한 줄 요약

> **KBC Login/CDN 문서는 현재 프로젝트의 Local Private Server를 만드는 방법을 배우는 참고자료로 적극 활용하되, KBC의 게임 고유 정보는 현재 게임에 이식하지 않는다.**

# TASK-005 — Request → Local Response → Player State / Static Data 구조 증명

## 상태
PLANNED / TASK-003 이후 단계

> 이 TASK는 현재 즉시 실행하지 않는다.
> 오프라인 로그인/최소 bootstrap 및 메인 메뉴 접근이 어느 정도 성립한 이후, 실제 기능 하나를 선택하여 실행한다.
>
> Unity Asset/AssetBundle 전체 분석보다 우선순위가 낮으며, 실제 Response를 구성하는 데 필요한 Static Data가 확인되는 경우에만 필요한 Asset 분석 TASK를 별도로 만든다.

## 목적

온라인 게임의 각 기능이 단순히 `Request → Server → Response`로 끝나는 것이 아니라,

`Request + Player State + Static Game Data → Response → Parser → Manager → UI`

구조로 동작하는지 증명한다.

최종 목표는 서버가 하던 Response 생성을 로컬에서 재현할 수 있는 최소 단위를 찾아내는 것이다.

## 핵심 가설

예를 들어 메뉴 1을 누르면 다음과 같은 구조일 수 있다.

```text
Menu 1 클릭
    ↓
MenuRequest
{
    menuId,
    userId,
    기타 필드...
}
    ↓
Server
    ↓
Player State 조회
    +
Static Game Data 조회
    ↓
MenuResponse
    ↓
Response Parser / Deserialize
    ↓
Manager / Data Object
    ↓
UI
```

오프라인 목표 구조:

```text
Menu 1 클릭
    ↓
기존 MenuRequest
    ↓
Local Response Provider / Builder
    ↓
Local Player State
    +
Static Game Data
    ↓
기존 Response Object
    ↓
기존 Parser / Data Path
    ↓
기존 Manager
    ↓
기존 UI
```

단, 위 구조는 가설이며 실제 코드 증거로 확인해야 한다.

## 중요 가설: 서버 권한형 가변 Response

가챠/상점/전투 결과처럼 유저 상태를 변경하는 기능은 다음과 같은 서버 권한형 구조일 가능성이 있다.

```text
GachaRequest
    ↓
Server Player State / DB 조회
    ↓
가챠 가능 여부 확인
    ↓
Server RNG
    ↓
등급 결정
    ↓
캐릭터/아이템 결정
    ↓
중복 여부 및 중복 보상 계산
    ↓
재화 차감
    ↓
Inventory 갱신
    ↓
DB 저장
    ↓
GachaResponse
```

이 구조는 실제 게임 코드로 증명해야 한다.

이 경우 오프라인화의 목표는 단순히 `Request 성공` 또는 고정된 `Response`를 반환하는 것이 아니다.

```text
GachaRequest
    ↓
Local Gacha Logic
    ↓
Local Player State
    +
Gacha Static Data
    ↓
RNG / 결과 결정
    ↓
중복 및 보상 계산
    ↓
재화 차감
    ↓
Inventory 갱신
    ↓
기존 GachaResponse Object
    ↓
기존 Parser / Manager / UI
```

따라서 가변 Response의 경우 다음을 구분해서 조사한다.

1. 서버에서만 수행되는 계산인가?
2. 클라이언트에 동일하거나 유사한 계산 로직이 이미 존재하는가?
3. 클라이언트에 필요한 Static Data가 이미 존재하는가?
4. 기존 Response Object/Manager가 결과 적용을 담당하는가?
5. 새로 추가해야 하는 최소 Local Logic은 무엇인가?

새 로직이 필요한 경우에도 우선순위는 다음과 같다.

```text
기존 로직 재사용
    ↓
기존 Data Object / Manager 재사용
    ↓
기존 Response Object 재사용
    ↓
최소 Local Response Builder 추가
    ↓
정말 필요한 경우에만 새로운 계산 로직 추가
```

복잡한 서버 로직 전체를 처음부터 native/ARM64 assembly로 재작성하는 것은 최후의 수단으로 한다.

## 네트워크 패킷과 암호화된 Response 분석

실제 패킷에서 평문 JSON이 아니라 바이너리 헤더/필드 뒤에 긴 ASCII 데이터가 관찰되었다.
관찰된 긴 영역은 `A-Z`, `a-z`, `0-9`, `+`, `/`, `=` 문자로 구성되고 `==`로 끝나는 형태였으며, 추가 확인 결과 **평문 Base64 데이터가 아니라 암호화된 데이터를 Base64 계열 표현으로 전달하는 형태로 판단한다.**

따라서 이 TASK에서는 해당 문자열을 단순한 Response 본문으로 취급하지 않는다.

핵심 경로는 다음과 같이 잡는다.

```text
Network Packet
    ↓
Header / Length / Type / Sequence 등
    ↓
Base64 Decode 또는 대응 Decode
    ↓
Decrypt / Decompress ?
    ↓
평문 Response Payload
    ↓
Deserialize / Parse
    ↓
Response Object
    ↓
Manager / Data Object
    ↓
UI
```

**중요:** 암호 알고리즘 자체를 먼저 복원하는 것이 목적이 아니다. 기존 클라이언트가 실제로 사용하는 `Decode → Decrypt → Deserialize → Response Object` 경계를 찾는 것이 우선이다.

오프라인화에서는 가능하면 네트워크 패킷/암호화 프로토콜을 재현하지 않고, 암호화 이전 또는 Response Object 생성 직전의 기존 데이터 경로를 재사용한다.

## Response 분석을 반드시 수행하는 단계

Response는 패킷 분석과 별도로 하나의 독립적인 조사 단계로 기록한다.

### 단계 A — Network Receive

- 어떤 함수가 패킷을 받는가?
- 수신 버퍼의 타입과 길이는 무엇인가?
- 공통 네트워크 수신 함수인가, 기능별 함수인가?
- 어떤 Request/기능에 대응하는 Response인가?

### 단계 B — Decode / Decrypt / Decompress

다음 계열 API/함수의 사용 여부를 확인한다.

- Base64 Decode / Encode
- byte[] ↔ string 변환
- AES / RSA / DES / XOR 등 암복호화
- 압축 해제
- custom decode/decrypt

알고리즘 이름만으로 확정하지 말고 실제 호출/XREF와 데이터 흐름으로 확인한다.

### 단계 C — 평문 Response Payload 확인

복호화 이후의 데이터를 확보하고 다음을 기록한다.

- payload 타입(byte[]/string 등)
- 길이
- JSON/XML인지
- protobuf/MessagePack인지
- custom binary인지
- 사람이 읽을 수 있는 문자열이 존재하는지
- 반복되는 필드/구조가 있는지

가능하면 **암호화된 패킷과 복호화 직후 payload를 대응시켜** 어느 함수가 경계를 만드는지 특정한다.

### 단계 D — Deserialize / Parser

복호화된 payload가 어떤 Parser/Deserializer를 거치는지 추적한다.

확인 대상:
- JSON parser
- protobuf
- MessagePack
- custom binary serializer
- 기타 게임 전용 serialization

그리고 반드시 다음을 특정한다.

```text
평문 payload
    ↓
Parser / Deserialize 함수
    ↓
실제 Response 타입
```

### 단계 E — 실제 Response Object 분석

Decode/Decrypt/Deserialize 직후 만들어지거나 전달되는 실제 Response 타입을 특정한다.

기록 항목:
- class/struct 이름
- 필드 목록
- 필드 타입
- constructor/factory
- 생성 위치
- callback
- caller/callee
- 성공/실패 상태값
- 하위 Response/Data Object

특히 **Response 필드가 이후 어떤 Player State 또는 Static Data와 연결되는지** 추적한다.

### 단계 F — Response → Manager / Data Object → UI

Response Object가 어느 Manager/Data Object로 전달되는지 추적한다.

```text
Response Object
    ↓
Manager / Data Object
    ↓
Player State 갱신
    ↓
UI
```

UI가 실제로 읽는 Response/Data Object 필드까지 연결한다.

이 단계가 끝나야 해당 Response가 오프라인에서 어떤 형태로 공급되어야 하는지 판단한다.

## Response 값 분석 기준

실제 Response를 확보하면 단순히 타입 이름만 기록하지 않는다.
각 Response 필드에 대해 다음을 조사한다.

| Response 필드 | 생성/파싱 위치 | 값의 출처 | Player State 영향 | Static Data 의존 | UI 사용처 | 서버 권한 여부 |
|---|---|---|---|---|---|---|
| 미확인 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |

값의 출처는 가능한 한 다음 중 하나로 분류한다.

```text
Request 직접 반영
Player State 반영
Static Data 반영
Server 계산 결과
Random/RNG 결과
Event/Time 상태
Session 상태
기타
```

가변 Response의 경우 특히 다음 흐름을 추적한다.

```text
Request
  ↓
Response 결정 요소
  ↓
Response 필드
  ↓
Client Data Object
  ↓
UI / 다음 Request
```

이를 통해 단순한 고정 Response인지, Player State와 계산을 필요로 하는 동적 Response인지 구분한다.

## 패킷 비교 조사

가능하면 동일 기능의 서로 다른 Response를 비교한다.

예:

```text
Gacha 1회 A
Gacha 1회 B
Gacha 1회 C
```

또는:

```text
메뉴 진입
샵 진입
가챠 진입
스테이지 진입
배틀 시작
배틀 종료
```

비교 시 다음을 기록한다.

- 공통 바이트 영역
- 반복되는 ASCII/Base64-like 영역
- 길이 변화
- 특정 위치의 변경값
- sequence/request ID 후보
- timestamp 후보
- 결과/재화/인벤토리와 상관되는 변경 영역
- 복호화 후 동일하게 유지되는 필드
- 복호화 후 변경되는 필드

패킷 바이트만으로 특정 필드의 의미를 최종 확정하지 않는다. **복호화/Deserialize 이후 Response Object의 실제 필드와 교차 검증한다.**

## 가장 중요한 조사 질문

### 1. Request가 무엇인가?

기능별로 실제 Request 객체/구조를 특정한다.

확인 대상 예:
- menuId
- stageId
- userId/account identifier
- selected world/map
- character ID
- inventory/currency 관련 값
- battle result
- 기타 요청 필드

각 필드에 대해:
- 생성 위치
- setter/constructor
- caller
- 직렬화 지점
- 네트워크 전송 지점
을 기록한다.

### 2. Response가 무엇인가?

실제 Response 타입/구조를 특정한다.

확인 대상:
- Response class/struct
- 암호화/복호화 전후 payload
- JSON/protobuf/custom binary 등 직렬화 형식
- deserialize/parser
- callback
- 성공/실패 경로
- Response → Data Object 변환
- 주요 Response 필드의 실제 값 출처

### 3. Response를 결정하는 상태는 무엇인가?

단순히 `menuId`만으로 Response가 결정되는지 확인하지 않는다.

다음과 같은 후보를 모두 조사한다.

```text
Request
+
Player State
+
Static Game Data
+
Event/Time State
+
기타 Session State
→ Response
```

특히 `Request의 필드 → Response 필드` 사이의 실제 데이터 의존성을 추적한다.

## 예시: 메뉴 → 스테이지 목록

가상의 예시는 다음과 같다.

```text
StageListRequest
{
    menuId = 1,
    userId = 123
}
    ↓
PlayerState.clearedStage = 3
    +
StageStaticData
    ↓
StageListResponse
{
    stage1 = unlocked,
    stage2 = unlocked,
    stage3 = unlocked,
    stage4 = locked,
    ...
}
```

중요:
- 위 값은 예시이며 실제 게임 구조로 확정하지 않는다.
- 실제 코드에서 어떤 Player State/Static Data가 사용되는지 증명한다.

## 예시: 스테이지 상세

```text
StageDetailRequest
{
    menuId = 1,
    stageId = 3,
    userId = 123
}
    ↓
StageStaticData[3]
    +
PlayerStageState[3]
    ↓
StageDetailResponse
    ↓
Stage Manager
    ↓
상세 UI
```

확인할 PlayerStageState 후보:
- clear 여부
- clear count
- best score/time
- stars
- achievement 상태
- 최초 클리어 여부
- 보상 수령 여부
- 기타 stage-specific state

## Static Data와 Player State 분리

조사 결과를 다음 두 범주로 분리한다.

### Static Game Data

게임 자체에 공통으로 존재할 가능성이 있는 데이터.

예:
- StageData
- CharacterData
- SkillData
- ItemData
- GachaTable
- RewardTable
- MenuData
- EnemyData

이 데이터가 실제로 AssetBundle/ScriptableObject/TextAsset/Resources/기타 Unity 데이터에 존재한다고 확인되는 경우에만 별도 Unity Asset 분석 TASK를 만든다.

### Player State

유저별로 달라지는 상태.

예:
- Account/LoginState
- Level/EXP
- Currency
- ClearedStage
- PlayerStageState
- Characters
- Inventory
- Achievements
- GachaState
- Daily/Login Reward State

기존 게임에 동일하거나 유사한 Data Object/Manager가 있으면 새 구조를 만들기 전에 재사용 가능성을 우선 조사한다.

## Local Response Provider 개념

최종적으로 다음과 같은 기능별 로컬 공급 구조가 가능한지 조사한다.

```text
LocalResponseProvider
├── GetMenu(request)
├── GetStageList(request)
├── GetStageDetail(request)
├── GetShop(request)
├── GetGacha(request)
├── StartBattle(request)
├── CompleteBattle(request)
└── GetPlayerState(request)
```

이는 구현을 즉시 요구하는 것이 아니라, 각 기능의 서버 응답 생성 역할을 로컬로 치환할 수 있는지 판단하기 위한 개념 모델이다.

## 기존 Response Object 재사용 원칙

가능하면 새 Response 타입을 만들지 않는다.

우선순위:

```text
기존 Request
↓
Local Response 생성
↓
기존 Response Object
↓
기존 Parser / Callback / Manager
↓
기존 UI
```

이 구조가 확인되면 UI 전체를 새로 만드는 대신 기존 클라이언트 데이터 경로를 유지할 수 있다.

## 기능별 API/데이터 매핑표

조사 결과를 다음 형태로 기록한다.

| 기능 | Request | Response | Response 결정 요소 | Static Data | Player State |
|---|---|---|---|---|---|
| 메뉴 1 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 스테이지 목록 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 스테이지 상세 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 상점 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 가챠 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 전투 시작 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| 전투 결과 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |

실제 조사 후 확인된 값만 채운다.

## Unity Asset 분석과의 관계

이 TASK에서는 Unity Asset을 무조건 전체 언팩하지 않는다.

다음 조건을 만족할 때만 Asset 상세 분석으로 연결한다.

```text
Request/Response 흐름 확인
        ↓
Response 결정 요소 확인
        ↓
Static Data가 필요한 것으로 증명
        ↓
해당 Static Data의 위치가 미확인
        ↓
필요한 AssetBundle/Unity 파일만 분석
```

즉,

**오프라인 동작이 아직 성립하지 않은 상태에서 전체 Asset을 상세 분석하는 것은 우선하지 않는다.**

## 조사 순서

1. 실제 동작 가능한 기능 중 하나를 선택한다.
2. 해당 기능의 Request 생성 위치를 찾는다.
3. 네트워크 전송 지점을 찾는다.
4. Response 수신 지점을 찾는다.
5. Decode/Decrypt/Decompress 여부를 확인한다.
6. **복호화 직후의 평문 Response Payload를 확인한다.**
7. Deserialize/Parser와 실제 Response 타입을 찾는다.
8. **Response 필드별 값의 출처와 의미를 역추적한다.**
9. Response가 어떤 Data Object/Manager에 저장되는지 추적한다.
10. UI가 어떤 필드를 읽는지 추적한다.
11. Response 필드별 입력/의존 데이터를 역추적한다.
12. Player State와 Static Data를 구분한다.
13. 서버 권한형 계산인지, 클라이언트에 기존 계산 로직이 있는지 구분한다.
14. 기존 Response Object/Manager 재사용 가능성을 판단한다.
15. 필요한 경우 Local Response Builder/Local Logic의 최소 범위를 정의한다.
16. Static Data가 필요하지만 위치가 불명확한 경우에만 Unity Asset 분석을 후속 TASK로 만든다.

## 수정 금지

이 TASK는 구조 증명이 목적이다.

- 코드/바이너리 수정 금지
- 임의 Response 생성 금지
- 더미 성공값 적용 금지
- Request/Response 이름만으로 역할 확정 금지
- Static Data가 AssetBundle에 있다고 추정만 하고 확정하지 않기
- 암호화된 패킷의 Base64-like 표현만 보고 평문 구조나 필드 의미를 확정하지 않기
- 복호화/Deserialize 이후 실제 Response Object를 확인하기 전에는 Response 필드 의미를 최종 확정하지 않기

## 결과 파일

`research/reports/TASK-005-result.md`

결과 보고서에는 가능하면 다음 항목을 별도로 기록한다.

```text
Network Receive
→ Decode/Decrypt/Decompress
→ 평문 Response Payload
→ Deserialize
→ Response Object
→ Response Field Analysis
→ Manager/Data Object
→ UI
```

그리고 기능별로:

```text
Request
Encrypted Response / Packet
Decode / Decrypt
Plain Response Payload
Response Type
Response Fields
Player State
Static Data
Server-only Logic 후보
Client-existing Logic
Local Logic 필요 범위
```

를 구분한다.

## 종료 기준

### 성공
최소 하나의 기능에 대해 다음을 증명한다.

`Request → Encrypted Response → Decode/Decrypt → Deserialize → Response → Data Object/Manager → UI`

그리고 가능한 범위에서:

`Request + Player State + Static Data → Response`

의 실제 의존성을 특정한다.

또한 주요 Response 필드에 대해 값의 출처와 UI/상태 갱신 경로를 특정한다.

### 부분 성공
Request/Response 또는 일부 데이터 의존성만 특정했지만 후속 분석에 필요한 함수/XREF/타입이 확보된다.

### 실패
추적이 막힌 경우 마지막으로 확인된 함수/객체/주소와 필요한 추가 조사 내용을 기록한다.

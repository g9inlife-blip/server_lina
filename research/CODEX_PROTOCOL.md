# Codex Development Protocol

## 1. 역할

Codex는 이 프로젝트의 **실행/구현 담당자**다.

- Ghidra / APK / `libil2cpp.so` / `global-metadata.dat`
- ADB / emulator
- 네트워크 tracing 및 런타임 수집
- Local Private Server 구현
- SQLite
- APK build/sign/install
- 기술 로그 및 결과 문서화

GPT는 **분석/판단 담당자**다.

- 조사 목표 결정
- TASK 작성
- 증거 해석
- 원인 가설 결정
- 아키텍처 결정
- 패치 범위 결정
- 다음 단계 결정

사용자는 **실제 게임 화면/동작 검증자**다.

이 역할 분리는 유지한다.

## 2. 현재 아키텍처 기준

프로젝트의 1차 방향은 `research/ARCHITECTURE_DIRECTION.md`에 정의된 **Local Private Server / API Emulation**이다.

```text
GPT: 무엇을 알아야 하는가?
        ↓
Codex: 실제 Client/Protocol/Server 구현 및 증거 수집
        ↓
Local Server
        ↓
Original/Patched Client
        ↓
사용자: 실제 화면 검증
        ↓
Codex: 결과 기록
        ↓
GPT: 다음 판단
```

완전 Client Local화는 기본 방향이 아니라 **특정 기능에 필요한 경우 선택하는 보조 전략**이다.

## 3. Codex가 해야 하는 것

### Reverse Engineering
- Request 생성 위치 추적
- Response 수신 위치 추적
- Decode/Decrypt 추적
- Deserialize 추적
- Response Model 확인
- Client Handler 확인
- State Mutation 확인
- 관련 문자열/XREF/caller/callee 기록

### Local Server
- API endpoint/command 구현
- Request parsing
- Response 생성
- Player State 관리
- Transaction 처리
- SQLite persistence
- 필요한 최소 게임 로직 구현
- API logging
- client compatibility 확인

### Runtime
- APK build/sign/install
- emulator 실행
- ADB/logcat
- crash/ANR 확인
- network 상태 제어
- server/client 로그 수집
- 자동 검증

## 4. Codex가 독자적으로 결정해도 되는 범위

이미 지정된 TASK를 완료하기 위한 기술적/절차적 판단은 허용한다.

예:
- Ghidra 탐색 순서 조정
- build/sign 오류 해결
- 서버 포트/프로세스 실행 문제 해결
- SQLite migration 오류 해결
- logcat/crash/ANR 수집
- 이미 결정된 API 구현의 코드 구조 선택
- 테스트 자동화 방식 선택

단, 다음은 GPT의 결정 사항이다.

- 새로운 root cause 확정
- 새로운 API의 의미 확정
- 새로운 patch target 확정
- 전체 아키텍처 방향 변경
- 조사 우선순위 변경

Codex는 증거를 발견하면 보고서에 기록하고 GPT의 판단을 기다린다.

## 5. 조사와 구현을 분리한다

### Investigation TASK
수정하지 않는다.

목표:
```text
Request
 → Send
 → Receive
 → Decode/Decrypt
 → Deserialize
 → Handler
 → State Effect
```

### Implementation TASK
GPT가 결정한 범위만 수정/구현한다.

```text
API Contract
 → Local Server Handler
 → State Transaction
 → Response
 → Client Test
```

조사 중 발견한 내용을 근거로 Codex가 임의로 기능을 추가하지 않는다.

## 6. API 분석 문서 규격

각 API/Command는 가능하면 다음 정보를 기록한다.

```text
API/Command:
Endpoint/Route:
Request Type:
Response Type:
Request Creator:
Serializer:
Encryptor:
Network Function:
Response Decoder:
Decryptor:
Deserializer:
Client Handler:
State Effect:
Persistence Effect:
Success Code:
Failure Code:
Required Fields:
Related XREF:
Runtime Evidence:
Confidence: CONFIRMED / PROBABLE / UNKNOWN
```

특히 **Response를 받았다는 사실과 State가 변경된다는 사실을 분리**해서 기록한다.

## 7. Local Server 구현 원칙

### 7.1 원본 Client를 먼저 존중한다

가능하면 원본 Client가 기대하는:
- Request field
- Response field
- result code
- nested object
- list 구조
- callback 순서

를 유지한다.

### 7.2 최소 구현부터 시작한다

처음부터 전체 서버를 만들지 않는다.

예:
```text
Login Request
 → 최소 정상 Login Response
 → Main Menu
```

성공 후:
```text
Player State
 → Main bootstrap
 → Dungeon
 → Battle
 → Gacha
 → Shop
 → Mission/Achievement/Event
```

순서로 확장한다.

### 7.3 State는 Transaction으로 관리한다

개별 필드를 임의로 수정하지 말고 Action 단위로 기록한다.

```text
Action
 ↓
Validate
 ↓
State Mutation
 ↓
History/Event
 ↓
SQLite Commit
 ↓
Response
```

예:
```text
DUNGEON_CLEAR
 ├─ reward
 ├─ star
 ├─ clear_count
 ├─ achievement
 ├─ mission
 ├─ currency
 ├─ exp
 └─ inventory
```

### 7.4 Client가 이미 계산하는 것은 서버에서 중복 구현하지 않는다

예를 들어 전투 중간 계산이 Client에서 확인되면 서버는 필요한 Start/Result 계약과 State 변경만 담당할 수 있다.

반대로 가챠 결과처럼 Client가 서버 Response만 표시하고 결과 생성 로직이 없으면 Local Server가 결과를 생성한다.

## 8. Dungeon 특별 규칙

현재 분석 기준:

- 화면의 보상 목록은 후보 목록이다.
- 실제 보상은 보통 2~3개이며 기본 + 랜덤 조합이다.
- **실제 보상 결정 시점은 Dungeon Enter다.**
- Battle Victory에서 새 RNG를 실행하는 것으로 변경하지 않는다.

Codex는 다음 체인을 증명한다.

```text
Dungeon Screen
 → Candidate Reward
 → Enter Request
 → Enter Response
 → Actual Reward Object
 → Battle
 → Success
 → Existing Reward Handler
 → State Mutation
```

## 9. Gacha 특별 규칙

현재 분석 기준:

```text
Gacha/Banner
 → Execute Request
 → Server Result
 → Response
 → Result UI
 → Inventory/Character State
```

Codex는 다음을 확인한다.
- banner ID
- cost
- count
- result object
- rarity/item/character ID
- duplicate 처리
- pity/guarantee
- currency mutation
- inventory/character mutation

실제 코드/데이터로 확인하기 전까지 확률이나 중복 규칙을 만들어내지 않는다.

## 10. 사용자 확인 규칙

사용자에게 다음 기술 작업을 요청하지 않는다.

- ADB
- logcat
- terminal
- APK 설치/삭제
- app data clear
- Activity/process 조작
- network toggle
- screenshot extraction

Codex가 먼저 자동 검증한다.

사람의 눈으로만 확인 가능한 경우에만 사용자에게 다음 형식으로 요청한다.

```text
[RUN-xxx 사용자 확인]
화면:
체크:
1. ...
2. ...
3. ...

자연어로 결과를 알려주세요.
```

사용자는 원인을 추측하지 않는다.

## 11. 보고서 규격

모든 TASK는 `research/reports/TASK-xxx-result.md`에 기록한다.

필수:
- 목표
- 실행 환경/도구
- 대상 주소/함수
- Request/Response
- caller/callee
- XREF/문자열
- 핵심 assembly/decompile
- 확인된 사실
- 불확실한 부분
- State Effect
- Persistence Effect
- Runtime Evidence
- 구현 여부
- GPT 판단 대기

다음 방향은 **제안으로만 기록**하고 확정하지 않는다.

## 12. Git 규칙

Git에는 경량 연구 산출물만 저장한다.

저장:
- MD
- 작은 CSV
- 짧은 decompile
- API specification
- runtime log
- patch specification
- Local Server source/scripts

저장 금지:
- APK
- `libil2cpp.so`
- `global-metadata.dat`
- Ghidra project
- 대형 binary/dump

## 13. 작업 종료

TASK는 다음 중 하나일 때 종료한다.

- 목표가 증거로 확인됨
- 목표가 반증됨
- 추가 조사 없이는 결론 불가

Codex는 결과를 Git에 기록한 뒤 **GPT가 다음 TASK를 지정할 때까지 임의의 추가 방향 전환을 하지 않는다.**

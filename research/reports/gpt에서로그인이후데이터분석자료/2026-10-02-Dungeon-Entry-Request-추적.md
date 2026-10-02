# 2026-10-02 던전 입장 요청 경로 추적

## 목적
Energy 수치/회복 경로 분석은 중단한다. Energy는 서버 권한 데이터이며 클라이언트의 값 변경은 UI 표시 및 사전 조건에만 영향을 줄 수 있다. 이 작업은 실제 던전 입장 요청과 서버 응답 계약을 확인하는 데 집중한다.

추적 순서:
```
던전/Section 선택
 → Ready 화면
 → 입장 버튼 사전 조건
 → 실제 Request 생성
 → KCP 송신
 → 서버 응답
 → Client response 처리
 → 전투 화면 전환 또는 거절 안내
```

## 1. Git 자료 확인
기준 저장소: `g9inlife-blip/arme`
확인한 기존 문서:
- `research/reports/2026-09-29-인게임-네트워크-경로-분석.md`
- `research/reports/2026-10-02-Bootstrap-OpCode2-Response-계약-초안.md`
- `research/reports/2026-10-02-로컬서버-중심-분석범위-작업원칙.md`
- `research/Ghidra_Listing_txt/RE.txt`
- `research/Ghidra_Listing_txt/DA.txt`
- `research/Ghidra_Listing_txt/CS.txt`
- `research/Ghidra_Listing_txt/CH.txt`
- `research/PCAP`의 기존 PCAP 및 변환 JSON 목록

## 2. 입장 버튼 사전 조건 — 정적 확인

### 2.1 ReadyMono.RefreshBtnState
- RVA: `00e5e86c`
- 목적: Ready 화면 입장 버튼 상태 갱신
- Calls OUT:
  - `ReadyMono.get_sectiondata @ 00e5cdb0`
  - `DataCenter.IsTaskMission @ 016de974`
  - `UserInfo.get_Energy @ 00dd2ce4`
  - ReadyPanel의 `lbl_cost` 접근 및 Text 갱신
- Assembly에서 현재 Energy와 Section 데이터의 `+0xA0` 값을 비교하는 분기가 확인된다.
- 이 경로는 클라이언트의 버튼/비용 표시 및 사전 조건 판단으로 분류한다. 서버의 최종 입장 승인 근거로 해석하지 않는다.

### 2.2 ReadyMono.InitReady
- RVA: `00e5dec0`
- Ready 화면 초기화 함수
- Calls OUT에 다음이 확인된다.
  - `DataCenter.IsSectionOpening @ 016e7f08`
  - `BaseExtensions.IsOpenChapter @ 00e1bf8c`
  - `ReadyMono.RefreshBtnState @ 00e5e86c`
  - `ReadypanelNode.get_btn_startbattle`
  - `ReadypanelNode.get_btn_startbattle_gray`
  - 버튼/이벤트 리스너 연결 계열
- 따라서 Ready 진입 시 Section 개방 상태 및 버튼 UI가 구성된다.

### 2.3 ReadyMono.ClickEnterBattle
- RVA: `00e63570`
- Calls OUT에 `DataCenter.IsSectionOpening`, `BaseExtensions.IsOpenChapter`, Section data 조회, 날짜 비교, TextTips/Notify 등이 확인된다.
- Listing의 클릭 처리 자체에는 `ProtocolGame_SendRequest.CreateBattle`, `CSBehaviour.RequestOp`, `NetworkCenter.Send` 직접 호출이 나타나지 않는다.
- 조건에 따라 안내/Notify 경로로 빠지는 분기가 존재한다.
- 따라서 클릭 함수만으로 실제 서버 요청이 발생한다고 단정하지 않는다. callback/delegate 또는 GoToBattle 계층으로 이어지는 후속 경로를 찾아야 한다.

## 3. 실제 전투 시작 Request — 기존 정적 계약 재확인

기존 `2026-09-29-인게임-네트워크-경로-분석.md`의 Listing 분석 결과:

대상: `ProtocolGame_SendRequest.CreateBattle @ 00dded04`

```
OpInfo +0x14 = 0x16
OpInfo +0x30 = w0
OpInfo +0x34 = w1
CSBehaviour.RequestOp(OpInfo)
```

현재 확정된 계약:
- Opcode: `0x16`
- Payload: 32-bit 인자 2개
- 저장 위치: OpInfo `+0x30`, `+0x34`
- 두 인자의 구체적인 의미는 아직 이 보고서에서 확정하지 않는다.

전송 계층은 기존 보고서의 공통 경로를 따른다.

```
ProtocolGame_SendRequest.CreateBattle
 → CSBehaviour.RequestOp
 → NetworkCenter.Send
 → Request queue
 → Tube Send
```

## 4. 현재 증거와 미확정 사항

| 항목 | 상태 |
|---|---|
| Ready 버튼 상태 갱신 함수 | 정적 확인 |
| Energy/Section의 클라이언트 사전 조건 참조 | 정적 확인 |
| 실제 전투 시작 함수 | CreateBattle @ 00dded04 확인 |
| CreateBattle Opcode | 0x16 확정 |
| Request payload 크기/위치 | u32 2개, +0x30/+0x34 확정 |
| ClickEnterBattle → CreateBattle 호출 연결 | 미확정 |
| 두 payload 인자의 실제 의미 | 미확정 |
| KCP runtime에서 던전 입장 Request/Response 상관관계 | 미확정 |
| 성공 응답 후 전투 화면 전환 조건 | 미확정 |
| 서버 거절 응답과 UI 안내 매핑 | 미확정 |

## 5. 다음 작업

1. `ReadyMono.ClickEnterBattle`가 전달하는 callback/delegate 및 화면 전환 계층을 추적한다.
2. `GoToBattleMono`의 CreateBattle 계열 함수에서 실제 `ProtocolGame_SendRequest.CreateBattle` 호출 및 인자 생성 지점을 찾는다.
3. `CreateBattle`의 두 u32 값이 어떤 Section/Chapter/Mission ID인지 실제 호출자에서 확정한다.
4. 기존 `research/PCAP`의 변환 JSON 중 던전 선택/전투 시작 캡처에서 Opcode `0x16` 요청과 응답을 찾아 시간/SerialNumber 기준으로 연결한다.
5. runtime hook은 `ProtocolGame_SendRequest.CreateBattle`, `KCPTube.Send`, `KCPTube.TryRead`, `NetworkCenter.TryHandleResponse`, `DataCenter.ProccessRequestRes` 경계만 우선 관찰한다.
6. 성공 응답 후 전투 씬 진입, 실패 응답 후 안내 UI를 확인한다.

## 분석 원칙
- Energy의 회복/증가 알고리즘은 더 추적하지 않는다.
- 클라이언트 Energy는 버튼 상태/표시용 사전 조건으로만 기록한다.
- 실제 소모/입장 가능 여부는 서버 권한 처리로 분리한다.
- 정적 Listing, runtime hook, PCAP 관측 결과를 서로 구분해 기록한다.
- 서버 요청/응답 계약이 확정되면 내부 UI 구현의 세부 추적을 종료한다.


## 6. PCAP 변환 데이터에서 CreateBattle 요청/응답 연결

대상 파일:
- `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.txt`
- 상위 캡처: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화.json`

### 6.1 실제 C→S 요청 — packet 368

변환된 KCP 메시지에서 다음 요청을 찾았다.

| 항목 | 값 |
|---|---|
| Packet | 368 |
| 방향 | Client → Server |
| Flags | 128 |
| decrypt | ok |
| SerialNumber | 2551705438 |
| Opcode | 22 (0x16) |
| OpInfo field 6 | 20000100 |
| OpInfo field 7 | 21000060 |

요청 protobuf 핵심:

```
field 1 = 2551705438   // SerialNumber
field 2 = 22           // Opcode 0x16
field 6 = 20000100
field 7 = 21000060
```

이는 Ghidra에서 확인한 CreateBattle의 opcode 0x16 및 두 개의 u32 payload(+0x30/+0x34)와 일치한다.

### 6.2 실제 S→C 응답 — packet 370

바로 이어지는 packet 370에서:

| 항목 | 값 |
|---|---|
| Packet | 370 |
| 방향 | Server → Client |
| Flags | 132 |
| decrypt | ok |
| SerialNumber | 2551705438 |
| Opcode | 22 (0x16) |
| field 6 | 20000100 |
| field 7 | 21000060 |

요청과 응답의 SerialNumber 및 Opcode가 동일하고 두 payload 값도 echo되어 있다.

따라서 이 캡처에서 **CreateBattle(0x16) 요청 → 동일 SerialNumber의 서버 응답**이 실제 KCP 메시지로 확인됐다.

응답에는 추가 field 21 데이터가 포함되어 있다. 현재 이 값들의 의미는 확정하지 않으며, Client의 `NetworkCenter.TryHandleResponse` / `DataCenter.ProccessRequestRes` 처리와 대조할 대상이다.

### 6.3 후속 opcode 0x17은 별도 요청으로 분리

packet 390에서 Client → Server opcode 23 (0x17) 요청이 관측된다.

- SerialNumber: 2551705439
- nested field 30 포함
- field 30 내부에 숫자 값 및 nested field 3/4/5가 존재

이는 CreateBattle 요청/응답과 별도의 후속 요청이다. 전투 결과/전투 보고 계열일 가능성은 있으나, 함수 Listing과 호출 시점을 대조하기 전에는 의미를 확정하지 않는다.

### 6.4 중요한 결론

현재 확보한 증거 사슬:

```
ReadyMono.RefreshBtnState
  → 클라이언트 버튼/비용 사전 조건
ReadyMono.ClickEnterBattle
  → Section/Chapter/날짜 조건 검사
  → 실제 Request 직접 호출은 미확인
ProtocolGame_SendRequest.CreateBattle
  → Opcode 0x16, u32 2개
PCAP packet 368
  → 0x16, Serial=2551705438
  → field6=20000100, field7=21000060
PCAP packet 370
  → 0x16, 동일 Serial 및 두 값
```

즉 서버 요청/응답은 실캡처로 연결됐지만, Ready 클릭 콜백과 CreateBattle 함수 사이의 정적 호출 연결은 아직 남아 있다.

## 7. 다음 작업

1. `20000100`과 `21000060`을 기존 Chapter/Section Record 및 런타임 객체 ID와 대조해 두 인자의 의미를 확정한다.
2. `ReadyMono.ClickEnterBattle`에서 실제 delegate/callback으로 넘어가는 지점을 추적한다.
3. `GoToBattleMono`의 CreateBattle 관련 callback에서 `ProtocolGame_SendRequest.CreateBattle` 호출을 연결한다.
4. packet 370의 field 21 응답 데이터를 Client response handler가 어떻게 처리하는지 확인한다.
5. opcode 0x17 / packet 390은 별도 전투 후속 요청으로 분리해 함수 매핑을 진행한다.


## 8. Chapter/Mission ID 대조 — Unity 원본 데이터

Unity 관련 판단은 먼저 다음 Git 문서를 읽고 원본 JSON을 확인했다.
- `참고용-unity-behavior-data/데이터_파일_역할_및_계층.md`
- `참고용-unity-behavior-data/데이터_분석/README.md`
- `참고용-unity-behavior-data/데이터_분석/output/analyze_game_systems/07_system_candidates.md`

문서의 계층 정의는 `Chapter → Tollgate`이며, 각 Record의 실제 ID 참조를 기준으로 해석해야 한다.

### 8.1 첫 번째 CreateBattle 인자
- PCAP 값: `20000100`
- 원본: `MonoBehaviour/ChapterRecord.json`
- `ChapterTable`에 ID `20000100`이 존재한다.
- 따라서 첫 번째 인자는 ChapterRecord ID와 일치한다.

### 8.2 두 번째 CreateBattle 인자
- PCAP 값: `21000060`
- data_catalog `09_record_samples.json`에서 `record_id=21000060`의 `source_file=MissionRecord.json`, `source_path=$.MissionTable[6]`로 확인된다.
- 따라서 두 번째 인자는 MissionRecord ID와 일치한다.
- 아직 이 MissionRecord가 런타임의 어떤 Section/Tollgate/전투 맵에 연결되는지 전체 참조는 미확정이다.

### 8.3 앞선 GetSections 요청과 응답
동일 KCP 캡처에서 CreateBattle보다 앞서 다음 요청/응답이 확인된다.

| Packet | 방향 | Opcode | SerialNumber | payload/결과 |
|---|---|---:|---:|---|
| 336 | C→S | 0x13 | 2551705436 | field 6 = 20000000 |
| 338 | S→C | 0x13 | 2551705436 | field 44 항목 ID: 21000010, 21000020, 21000040 |
| 340 | C→S | 0x13 | 2551705437 | field 6 = 20000100 |
| 343/346 | S→C | 0x13 | 2551705437 | field 44 항목 ID: 21000050 |
| 368 | C→S | 0x16 | 2551705438 | field 6 = 20000100, field 7 = 21000060 |
| 370 | S→C | 0x16 | 2551705438 | 동일 ID echo |

따라서 현재 가장 유력한 Request Contract는:

```
CreateBattle(
    chapterId = 20000100,   // ChapterRecord
    missionId = 21000060    // MissionRecord
)
```

두 인자의 Record 종류는 데이터 카탈로그로 확인됐지만, 메서드 인자명 자체와 내부 호출부의 값 전달은 다음 정적 추적으로 최종 확인한다.


## 9. Runtime 관찰 hook v4.24

`research/justice_hook.js`에 던전 입장 전용 관찰 hook을 추가했다.

- `ReadyMono.RefreshBtnState` → `[DUNGEON_READY_STATE]`
- `ReadyMono.ClickEnterBattle` → `[DUNGEON_READY_CLICK]`
- `GoToBattleMono.CreateBattleBack` → `[DUNGEON_GOTO_BATTLE]`
- `ProtocolGame_SendRequest.CreateBattle(int,int)` → `[DUNGEON_CREATE_BATTLE]`

요청 계층은 기존 hook을 재사용한다.
- `KCPTube.Send` / `[KCP_SEND_ARGS]`: Request의 SerialNumber와 OpCode
- `NetworkCenter.TryHandleResponse`
- `DataCenter.ProccessRequestRes`

### 실행 후 확인할 로그 순서

```
[DUNGEON_READY_STATE]
[DUNGEON_READY_CLICK]
[DUNGEON_GOTO_BATTLE]
[DUNGEON_CREATE_BATTLE] arg0=20000100 arg1=21000060
[KCP_SEND_ARGS] ... OpCode=22
[NET_RESP] ...
[NET_RESP_STATUS] ...
```

위 순서는 기대 관찰 지점이며 실제 호출 순서를 미리 단정하지 않는다. 일부 UI 함수가 발견되지 않으면 해당 hook은 경고를 출력하고 나머지 hook 설치는 계속한다.

### 실행 방법
게임이 IL2CPP 로딩을 마친 뒤 기존 방식으로 `research/justice_hook.js`를 attach하고, 실제로 던전 입장 버튼을 한 번 눌러 로그를 수집한다. 로그에는 계정 Token/device 식별값이 포함되지 않도록 기존 민감정보 마스킹 원칙을 유지한다.

현재 스크립트는 관찰 전용이며 게임 메모리나 서버 데이터를 변경하지 않는다.


## 10. Runtime 결과 — v4.24 (2026-10-02)

로그 원본:
`research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`

### 10.1 Hook 설치 확인
- `ProtocolGame_SendRequest.CreateBattle(System.Int32, System.Int32)` 설치 확인
- `GoToBattleMono.CreateBattleBack(Alioth.S1.Net.Request)` 설치 확인
- Ready 상태/클릭 hook도 실제 호출 로그가 발생했다.

### 10.2 실제 클릭부터 서버 응답까지

| 순서 | 로그 | 관측 |
|---|---|---|
| 1 | `DUNGEON_READY_STATE` | Ready 화면 버튼 상태 갱신 |
| 2 | `DUNGEON_READY_CLICK` | 입장 버튼 클릭 함수 진입 |
| 3 | `DUNGEON_CREATE_BATTLE` | arg0=`20000000`, arg1=`21000010` |
| 4 | `KCP_SEND_ACCEPTED` | Serial=`139954761`, OpCode=`22` (0x16), ret=1 |
| 5 | `NET_RESP_STATUS` | status=4, `ProccessRequestRes` 경로 |
| 6 | `BOOT_RESP` | OpCode=22, ReturnCode=0 |
| 7 | `DUNGEON_READY_STATE` | 응답 처리 후 Ready 상태 재갱신 |
| 8 | `DUNGEON_GOTO_BATTLE` | `GoToBattleMono.CreateBattleBack` 진입 |

이번 실행에서 클릭부터 서버 응답 처리 및 `CreateBattleBack` 진입까지 한 번의 흐름으로 관측했다.

### 10.3 요청 인자 비교
이번 runtime 값:
- arg0 = `20000000`
- arg1 = `21000010`

이전 PCAP 값:
- arg0 = `20000100`
- arg1 = `21000060`

값이 다른 것은 서로 다른 Chapter/Mission을 선택한 실행으로 해석할 수 있다. 이번 두 ID의 Record 종류/참조 관계는 다음 정적 데이터 대조에서 확인한다. 이전 PCAP의 ID 의미를 이번 runtime 값에 그대로 대입하지 않는다.

### 10.4 응답 해석 범위
- KCP Send 반환값 1: 클라이언트 전송 계층에서 요청이 수락된 것으로 관측.
- `NET_RESP_STATUS status=4`: 기존 hook의 분기 기준상 `ProccessRequestRes` 실행 경로.
- `BOOT_RESP OpCode=22 ReturnCode=0`: 응답 OpInfo의 ReturnCode가 0.
- `CreateBattleBack` 진입: 서버 응답 처리 뒤 후속 callback이 호출된 사실을 확인.

단, ReturnCode=0만으로 실제 전투 씬 로딩 완료까지 확정하지 않는다. 이번 로그에는 씬 전환 완료를 직접 확인하는 hook은 없다.

## 11. 남은 확인 사항

1. 이번 실행의 `20000000 / 21000010`을 ChapterRecord/MissionRecord 원본과 대조한다.
2. `CreateBattleBack(Alioth.S1.Net.Request)` 인자로 전달된 Request의 상태/응답 필드를 안전하게 읽어 성공·실패 분기를 확인한다.
3. `CreateBattleBack` 이후 실제 전투 씬 로딩/진입 완료 지점을 찾는다.
4. 서버 거절 케이스가 가능하면 별도 캡처하여 ReturnCode 및 실패 UI 경로를 비교한다.

Energy 회복 경로는 추가 추적하지 않는다.

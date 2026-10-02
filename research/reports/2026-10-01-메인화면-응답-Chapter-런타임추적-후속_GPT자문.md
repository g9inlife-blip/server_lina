# 1001-2026-10-01 메인화면 응답 / Chapter 런타임 추적 후속

## 1. 작업 목적

1001-1의 다음 단계로 **던전 보상부터 다시 추적하지 않고 로그인 이후 메인화면에서 서버가 내려주는 상태 데이터**를 먼저 추적한다.

목표 흐름:

```
로그인
 ↓
세션/로그인 정보
 ↓
메인화면 진입
 ↓
서버 응답
 ↓
Deserialize
 ↓
OpInfo
 ├─ Items
 ├─ Weapons
 ├─ Equipments
 ├─ Chapters
 └─ Sections
 ↓
메인화면 UI 표시
```

핵심은 `OpInfo.Chapters`와 `ProtoChapter.BoxStatus`가 실제 response 처리 과정에서 어떻게 연결되는지 확인하는 것이다.

## 2. 현재까지 확정된 구조

### 2.1 ProtoChapter

Ghidra Listing 기준:

```
ProtoChapter +0x10 = Id
ProtoChapter +0x14 = Status
ProtoChapter +0x18 = Progress
ProtoChapter +0x1C = BoxStatus
```

`IsBoxReceived`는 다음 논리로 동작한다.

```
(BoxStatus & mask) != 0
mask = 1 << boxIndex
```

따라서 BoxStatus는 Box 획득 여부 bitmask로 확정한다.

### 2.2 OpInfo

```
OpInfo +0xC0 = Chapters
```

getter/setter Listing으로 offset은 확정되었다.

## 3. Chapter Dictionary 연결점

`BattleMapMono$$LayChapterItem @ 00e4f918`에서는 ChapterData ID → Dictionary 조회 → ProtoChapter → Chapter UI 구성 흐름이 확인된다.

`ProtoChapter$$IsBoxReceived @ 015acfe8`의 Calls IN에는:

```
ChapBoxMono$$LayBoxItem
BattleMapMono$$LayChapterItem
BattleSectionMono$$SetStageBoxAndBar
```

가 존재한다.

## 4. 네트워크 Deserialize 경로

Ghidra Listing:

```
Alioth.S1.Net.KCPTube$$TryRead
        ↓
DecryptUnSafe
        ↓
ProtoBuf.Serializer$$Deserialize<object> @ 017cec0c
        ↓
response object
```

`TCPTube$$TryRead`에서도 동일한 Deserialize 호출이 확인된다.

현재까지 확인된 논리 경로:

```
KCP/TCP message
 ↓
Decrypt
 ↓
Deserialize<object>
 ↓
OpInfo/response object
 ↓
NetworkCenter.TryHandleResponse
 ↓
DataCenter.ProccessRequestRes
```

## 5. Runtime hook

`research/justice_hook.js`에는 다음 추적이 구성되어 있다.

```
NetworkCenter.TryHandleResponse
DataCenter.ProccessRequestRes
OpInfo.get_Chapters
ProtoChapter.get_BoxStatus
ProtoChapter.set_BoxStatus
Dictionary<int, ProtoChapter> enumeration
```

## 6. 2026-10-01 로그인 Bootstrap 실제 확인

실제 runtime에서:

```
[BOOT_RESP] seq=1 ... OpCode=2 ReturnCode=0
[BOOT_STATE] User=ProtoUser
[BOOT_STATE] Items=Dictionary
[BOOT_STATE] Heros=Dictionary
[BOOT_STATE] Chapters=Dictionary
[BOOT_USER] Id=871038 Level=5 Exp=300
```

Chapter Dictionary는 61개이며 대표적으로:

```
20000000 -> BoxStatus=7
20000100 -> BoxStatus=1
```

가 확인됐다.

이는 `OpInfo +0xC0 → Chapters → ProtoChapter +0x1C` 연결이 runtime에서도 확인됐다는 의미다.

`seq=2`는 `OpCode=0`이고 User/Items/Heros/Chapters가 null이므로 현재 bootstrap 추적 대상에서 제외한다.

## 7. Bootstrap Dictionary dump 문제

v4.15에서 다음 출력 로직을 추가했다.

```
[BOOT_DICT]
[BOOT_ITEM]
[BOOT_CHAPTER]
```

하지만 실제 실행에서는 출력되지 않았다.

대신 다음까지만 확인됐다.

```
[BOOT_STATE] Items@+0x98=Dictionary...
[BOOT_STATE] Heros@+0x90=Dictionary...
[BOOT_STATE] Chapters@+0xc0=Dictionary...
```

따라서 **Dictionary 포인터 획득은 성공했지만 v4.15 enumeration/dump 단계는 실행되지 않은 상태**다.

이 상태에서는 Items의 실제 ItemId/Count를 추측하지 않는다.

## 8. 2026-10-01 추가 관찰: 창고/메뉴 진입

사용자가 창고나 메뉴에 진입하면 다음 로그가 반복된다.

```
[MAIN_CURRENCY] Level=5 UserInfo=0x75d317e680
[MAIN_CURRENCY] Level=5 UserInfo=0x75d317e680
```

그러나 창고 화면에는 실제 아이템 목록이 표시된다.

즉 현재 `MAIN_CURRENCY` hook은 창고 데이터 획득 경로를 잡고 있지 않다.

현재까지는 다음을 분리해서 보는 것이 맞다.

```
MAIN_CURRENCY
    ↓
UserInfo.get_Level / get_Exp 등 UI polling
    ↓
Level/Exp만 반복 출력

창고 UI
    ↓
실제 Item list 존재
    ↓
현재 hook에서는 item 데이터 접근 로그 없음
```

따라서 창고 데이터를 찾기 위해서는 `MAIN_CURRENCY`를 계속 확장하기보다 **창고 UI가 실제로 어떤 Dictionary/List에서 Item을 꺼내는지 역추적**해야 한다.

우선 Ghidra에서 `ProtoItem` getter와 창고 UI의 Item 생성/갱신 함수, Dictionary의 `get_Item / TryGetValue / Enumerator` 호출 관계를 찾아 runtime hook 대상으로 삼는다.

## 9. 중요한 네트워크 구조 가설

현재 로그와 기존 Ghidra 분석을 함께 보면 **로그인 이후 정보가 빠진 것처럼 보이는 이유가 TCP/KCP 계층 차이일 가능성**을 확인할 필요가 있다.

현재 확정된 사실은:

- `TCPTube.TryRead`에도 `Deserialize<object>`가 있다.
- `KCPTube.TryRead`에도 `Deserialize<object>`가 있다.
- `DH64.Secret`의 호출자는 `KCPTube.Handshake2`와 `TCPTube.TryOutput`로 확인되어 있다.
- 기존 네트워크 분석에서 실제 최종 송수신 계층은 `KCPTube / TCPTube`로 분리되어 있다.
- KCP handshake 및 DH64 관련 분석에서는 UDP 계층의 별도 처리 때문에 PCAP 기반 Local Server 구현이 아직 완성되지 않았다.

따라서 현재 단계에서 **"인게임 데이터가 없다"라고 판단하면 안 된다.**

가능한 구조는 다음과 같다.

```
로그인
  ↓
TCP/TCPTube
  ↓
OpCode=2 Login response
  ↓
OpInfo / User / Items / Chapters
  ↓
메인화면

인게임/창고/실시간 상태
  ↓
KCPTube(KCP/UDP) 또는 별도 request path
  ↓
Decrypt
  ↓
Deserialize<object>
  ↓
다른 OpInfo/response 또는 별도 상태 객체
  ↓
UI
```

이것은 현재 단계의 **가설**이며 아직 확정하지 않는다.

특히 Unity 게임이라고 해서 반드시 모든 게임 상태가 UDP라는 의미는 아니다. Unity는 단지 클라이언트 런타임이고 실제 네트워크 구조는 게임 자체의 `TCPTube/KCPTube` 구현을 따라간다.

## 10. 네트워크 확인을 위한 다음 순서

창고 데이터 추적과 Local Server 구현을 동시에 섞지 않고 다음 순서로 분리한다.

### A. Runtime에서 transport 확인

창고 진입 직전/직후:

```
TCPTube.TryRead
KCPTube.TryRead
TCPTube.TryOutput
KCPTube.Send/Receive 관련 함수
NetworkCenter.TryHandleResponse
DataCenter.ProccessRequestRes
```

호출 발생 여부와 시간순서를 기록한다.

핵심은 **창고 진입 시 실제로 어느 Tube의 TryRead가 호출되는지** 확인하는 것이다.

### B. response가 있으면 바로 response root 확인

```
TryRead
 ↓
Deserialize<object>
 ↓
class name
 ↓
OpCode
 ↓
OpInfo field
```

이렇게 잡으면 PCAP을 먼저 복호화하지 않아도 해당 응답의 구조를 확인할 수 있다.

### C. response가 없으면 request/output 확인

창고 진입 시:

```
UI action
 ↓
request 생성
 ↓
TCPTube.TryOutput 또는 KCPTube 송신
 ↓
server
 ↓
response
```

중 어디까지 실행되는지를 확인한다.

### D. Local Server는 그 다음

현재 Local Server에서 TCP와 UDP/KCP가 분리되어 있는 문제는 **런타임에서 실제 transport를 먼저 특정한 뒤** 해결하는 것이 효율적이다.

현재 확보된 코드상 TCP/KCP 양쪽 모두 최종적으로 protobuf Deserialize 경로를 가질 수 있으므로, 먼저 실제 게임에서 어떤 Tube가 창고/인게임 데이터를 전달하는지 확정한다.

## 11. 현재 결론

확정:

- Login response `OpCode=2`에서 User/Items/Heros/Chapters가 존재한다.
- Chapters 61개와 BoxStatus 값이 runtime에서 확인됐다.
- 창고/메뉴 진입 시 UI에는 실제 Item list가 존재한다.
- 현재 `MAIN_CURRENCY` hook은 창고 Item list 접근을 잡지 못한다.
- TCPTube/KCPTube 양쪽에 Deserialize 경로가 존재한다.
- DH64 호출 구조상 TCP와 KCP가 별도 transport 경로로 구현되어 있다.

미확정:

- 창고 Item list가 TCP인지 KCP/UDP인지
- 창고 진입 시 추가 response의 OpCode
- 창고 데이터가 `OpInfo.Items`를 직접 사용하는지
- 별도 cache/state 객체를 사용하는지
- Local Server에서 TCP와 KCP를 모두 구현해야 하는지

## 12. 다음 작업

1. `justice_hook.js`에서 `TCPTube.TryRead` / `KCPTube.TryRead` 호출 로그 추가
2. 창고 진입 시 어느 Tube에서 response가 들어오는지 확인
3. 해당 response의 Deserialize 결과 class/OpCode 확인
4. response가 `OpInfo`이면 Items/Weapons/Equipments/기타 field 확인
5. response가 별도 class이면 해당 class부터 Ghidra 역추적
6. 그 결과를 기준으로 Local Server의 TCP/KCP 구현 범위를 결정

**현재 느낌대로 "로그인 이후 데이터가 빠진다"는 관찰은 의미가 있다. 다만 다음 단계에서는 TCP/UDP를 추측하지 말고 Unity 런타임에서 실제 호출된 Tube를 직접 잡아 확인하는 것이 가장 빠르다.**


## 13. 2026-10-01 Transport 런타임 추적 결과 — KCPTube 확정

사용자가 로그인 → 메인화면 구간에서 수집한 최신 runtime 로그를 기준으로 transport 경로를 확인했다.

### 13.1 실제 응답 수신 경로

로그에서 다음 순서가 직접 확인됐다.

```
KCPTube.Send
  ↓
KCPTube.Update
  ↓
KCPTube.TryRead
  ↓ ret=1
NetworkCenter.TryHandleResponse
  ↓
DataCenter.ProccessRequestRes
  ↓
OpInfo
```

실제 응답 직전에는:

```
[TRANSPORT] KCPTube.TryRead enter
[CHAPTERS_GET] OpInfo=... ret=null
[TRANSPORT] KCPTube.TryRead leave ret=1
[NET_RESP_STATUS] status=4 route=ProccessRequestRes
[NET_RESP] ProccessRequestRes enter ... response=OpInfo
```

같은 구간에서 `TCPTube.TryRead`는 `ret=0`이었다.

따라서 **이번 로그인 Bootstrap OpCode=2 응답은 KCPTube 경로에서 수신된 것으로 확정**한다.

### 13.2 Bootstrap OpInfo 전체 상태 구조 재확인

실제 `OpCode=2 / ReturnCode=0` 응답의 `OpInfo`에서 다음 field가 모두 존재했다.

```
+0x88 User
+0x90 Heros
+0x98 Items
+0xA0 Weapons
+0xA8 Equiments
+0xB0 Mails
+0xB8 Olds
+0xC0 Chapters
+0xC8 Sections
+0xD0 Teams
+0xD8 ViewItems
+0xE0 Fashions
+0xE8 Quests
+0xF0 Shops
+0xF8 Charges
+0x100 Friends
+0x108 Exam
+0x110 Rival
+0x118 Ranks
+0x120 Activities
...
```

즉 메인화면에서 사용 가능한 상태 데이터가 `Chapters` 하나에 한정되지 않으며, **Items / Weapons / Equiments 등이 동일 Bootstrap OpInfo에 포함될 수 있음**을 runtime에서 직접 확인했다.

### 13.3 Chapter runtime 결과

이번 응답에서도:

```
Chapters Dictionary count = 61
20000000 -> BoxStatus=7
20000100 -> BoxStatus=1
```

가 확인됐다.

따라서 기존에 확인한:

```
OpInfo +0xC0
  ↓
Dictionary<int, ProtoChapter>
  ↓
ProtoChapter +0x1C
  ↓
BoxStatus
```

연결은 재현됐다.

### 13.4 중요한 정정

이전에는 로그인/인게임 데이터가 TCP와 KCP로 분리될 가능성을 가설로 두었다.

현재 로그만으로는 **로그인 Bootstrap 자체는 KCP/KCPTube로 확인되었으므로 '로그인은 TCP'라는 가정은 폐기**한다.

다만 다음은 아직 미확정이다.

- 창고 진입 후 추가 응답도 KCPTube인지
- 창고 Item UI가 Bootstrap의 `OpInfo.Items`를 그대로 사용하는지
- 창고 진입 시 별도 OpCode/response가 발생하는지
- TCPTube가 어떤 다른 기능에 사용되는지

### 13.5 KCPTube.Update 반환값에 대한 판단

`KCPTube.Update`에서 `-139, -74, -38, -6` 등의 값이 반복되지만, 이후 정상적인 `KCPTube.TryRead ret=1`과 `OpInfo` 처리가 발생했다.

따라서 현재 단계에서는 이 반환값들을 곧바로 네트워크 오류로 해석하지 않는다.

특히:

```
KCPTube.Update
  ↓
KCPTube.TryOutput
  ↓
KCPTube.TryRead
  ↓
정상 OpInfo 처리
```

가 실제로 이어지고 있으므로, 반환값의 의미는 Ghidra에서 해당 Update 구현을 확인한 후 판단한다.

## 14. 다음 추적 우선순위 변경

현재는 TCP/KCP 구분보다 **KCPTube에서 실제 request/response OpCode를 잡는 것**이 우선이다.

다음 순서:

```
KCPTube.Send
  ↓
Send 인자/호출 객체 확인
  ↓
request class / OpCode 확인
  ↓
KCPTube.TryRead
  ↓
Deserialize 결과 class / OpCode
  ↓
OpInfo.Items / Weapons / Equiments 확인
  ↓
창고 UI Item 접근 함수와 연결
```

특히 `KCPTube.Send`에서 실제 request의 객체와 OperationCode를 확인하면, 창고 진입 시 어떤 요청이 서버로 전송되는지 직접 특정할 수 있다.

**Local Server의 TCP/KCP 구현 변경은 이 단계 이후로 보류한다.**

## 15. 2026-10-01 KCPTube.Send 요청 객체 추적 hook v4.17

### 15.1 Ghidra Listing 확인

`Alioth.S1.Net.KCPTube$$Send` 오버로드가 두 개 확인된다.

| 주소 | 정적 호출 관계 | 판단 |
|---|---|---|
| `015aeb18` | `KCP.Send` 호출, Lua delegate 경로 | 송신 보조 오버로드 |
| `015aeddc` | `ProtoBuf.Serializer.Serialize<object>` → `Tools.EncryptUnSafe` → `KCP.Send` | 직렬화/암호화가 수행되는 요청 송신 경로 |

`015aeddc` Listing에서 ARM64 인자 흐름은 다음과 같다.

- `x0`: `KCPTube this`
- `x1`: 직렬화 대상 객체
- `x2`: Serialize에 전달되는 stream/buffer 객체
- `x3`: 암호화 결과를 담는 stream/buffer 객체

Listing상 `Serialize<object>` 호출 직전에 `x0=x21`, `x1=x22`가 설정되며 함수 진입 시 `x22=x1`, `x21=x2`이므로, **Send의 첫 번째 매개변수(arg1)가 실제 직렬화 대상 객체**다.

### 15.2 justice_hook.js v4.17 반영

파일: `research/justice_hook.js`

추가한 출력:

```
[KCP_SEND_ARGS] signature=(...) arg1=request=ClassName@...
[KCP_SEND_ARGS] ... OpCode=...
```

추적 항목:
- Send 오버로드별 매개변수 형식
- `arg1` 요청 객체의 IL2CPP 클래스명
- 클래스가 `OpInfo`이면 알려진 `+0x14 OpCode`, `+0x18 ReturnCode`
- 그 외 객체는 필드명에 `OpCode` 또는 `OperationCode`가 포함된 필드의 이름/offset/type 및 정수값만 출력
- `arg2`, `arg3`는 객체 클래스명과 주소만 출력

보안/로그 크기 제한:
- 요청 객체의 임의 필드 전체 dump 금지
- protobuf 직렬화 버퍼 및 암호화 버퍼 내용 출력 금지
- 토큰, 계정정보, 패킷 원문 출력 금지

### 15.3 Git 반영

- commit: `4618c3b6f68dc224861b6fd9b635315110c36c8b`
- message: `trace: inspect KCPTube Send request class and opcode`

### 15.4 다음 실행에서 확인할 것

실기기 ARM64 + 기존 hook-patched APK 환경에서 v4.17을 실행한다.

1. 로그인 후 메인화면까지 진입
2. 창고를 열기 전후 로그를 구분해 수집
3. `[KCP_SEND_ARGS]`에서 각 Send의 signature와 arg1 class를 기록
4. 요청 객체에서 OpCode가 출력되면 창고 진입 전후 값을 비교
5. 같은 시간대 `KCPTube.TryRead`, `NetworkCenter.TryHandleResponse`, `DataCenter.ProccessRequestRes`의 로그와 대조
6. 창고 진입 직후 발생한 요청과 응답을 연결해 `OpInfo.Items/Weapons/Equiments` 또는 별도 상태 객체 경로를 확정

**현재는 hook 코드 반영까지 완료됐고, 실제 요청 클래스/OpCode는 다음 실기기 실행 로그로 검증해야 한다.** Local Server의 TCP/KCP 구현은 계속 보류.

## 16. 2026-10-01 v4.17 실기기 로그 분석 및 v4.18 보강

### 16.1 실기기 관측

사용자 제공 로그에서 `KCPTube.Send`의 실제 오버로드와 요청 객체가 확인됐다.
- Signature: `(Alioth.S1.Common.OpInfo, System.IO.MemoryStream, System.IO.MemoryStream)`
- 요청 객체: `OpInfo`, `OpCode=2`, `ReturnCode=0`
- 동일 객체 주소 `0x75d3209e60`가 반복 사용됨
- 같은 요청으로 Send가 반복 호출됐고, 관측된 반환은 `ret=0` 반복 후 `ret=1` 한 번
- 같은 구간의 `KCPTube.TryRead` 및 `TCPTube.TryRead`는 모두 `ret=0`
- `KCPTube.Update` 중 `TryOutput ret=-1`도 관측됐으나, 이것만으로 연결 실패라고 단정하지 않는다.

### 16.2 Send 반환값의 정적 의미

`research/Ghidra_Listing_txt/AL/015aeddc_Alioth.S1.Net.KCPTube__Send.txt` 확인 결과:
- `KCP.WaitSnd()`가 0보다 크면 `ret=0` 경로로 빠진다.
- `IsWorking`, KCP 객체 유효성, stream 유효성, 암호화 결과 등의 조건 실패도 `ret=0` 경로로 이어진다.
- 실제 `KCP.Send` 호출 뒤 `DateTime.Now`를 `KCPTube +0x40`에 기록하고 `ret=1`을 반환한다.

따라서 이번 로그에서 `ret=1`은 **KCPTube 내부의 KCP.Send 호출까지 통과한 요청**으로 볼 수 있다. 다만 `ret=0`만으로 원인을 `WaitSnd` 하나로 확정할 수는 없다.

### 16.3 응답은 아직 확인되지 않음

제공된 로그 조각에서는 해당 `OpCode=2` 송신 뒤 `KCPTube.TryRead ret=1` 또는 `BOOT_RESP`가 보이지 않는다. 로그가 중간에서 잘렸을 수 있으므로 응답 미수신으로 단정하지 않는다. 기존 별도 실행에서 확인한 Bootstrap 응답과 이번 조각은 구분한다.

### 16.4 v4.18 hook 보강

`research/justice_hook.js`를 v4.18로 수정했다.
- `OpInfo +0x10 SerialNumber` 출력 추가
- `OpCode`, `ReturnCode`와 함께 요청 식별값 출력
- `KCPTube.Send ret=1`일 때만 `[KCP_SEND_ACCEPTED]` 한 줄을 추가
- 요청/버퍼의 임의 데이터는 계속 출력하지 않음

Git commit: `a7cc39631d44087b5551614f7149c127af798595`
message: `trace: correlate accepted KCP sends with OpInfo serial numbers`

### 16.5 다음 실행

1. v4.18로 로그인부터 메인화면까지 실행한다.
2. `[KCP_SEND_ACCEPTED]`의 `SerialNumber`와 `OpCode`를 기록한다.
3. 직후 `KCPTube.TryRead ret=1` 및 `BOOT_RESP`의 SerialNumber/OpCode와 대조한다.
4. 창고 진입 전후 동일 로그를 수집해 새 요청이 생기는지 비교한다.
5. 창고 진입 후에도 Send 요청이 없다면, Bootstrap의 `OpInfo.Items/Weapons/Equiments` 캐시를 읽는 UI 바인딩 경로로 추적을 전환한다.

**현재 확인된 요청은 Bootstrap `OpCode=2`다. 창고 전용 요청은 아직 관측되지 않았다.**
## 17. 2026-10-01 v4.18 요청-응답 SerialNumber 일치 확인

사용자가 제공한 v4.18 로그에서 Bootstrap 요청과 응답의 상관관계를 직접 확인했다.

### 17.1 송신 요청

- KCPTube.Send request=OpInfo
- SerialNumber=66149422
- OpCode=2
- ReturnCode=0
- Send ret=1 및 KCP_SEND_ACCEPTED 출력

같은 OpInfo 객체와 같은 SerialNumber/OpCode가 Send 재시도 구간에서 반복되다가 ret=1 한 번이 관측됐다.

### 17.2 수신 응답

이후 다음 순서가 확인됐다.

- KCPTube.TryRead leave ret=1 69ms
- NET_RESP_STATUS status=4 route=ProccessRequestRes
- DataCenter.ProccessRequestRes response=OpInfo
- SerialNumber=66149422
- OpCode=0x2
- ReturnCode=0

송신과 응답의 SerialNumber 및 OpCode가 모두 일치한다.

**따라서 Bootstrap OpCode=2 요청 → KCPTube 송신 수락 → KCPTube 응답 수신 → DataCenter.ProccessRequestRes 처리가 한 건의 동일 요청으로 연결된 것이 확정됐다.**

### 17.3 응답 상태

동일 응답의 OpInfo에서 다음 필드가 실제로 non-null로 확인됐다.

- User +0x88
- Heros +0x90
- Items +0x98
- Weapons +0xA0
- Equiments +0xA8
- Chapters +0xC0
- Sections +0xC8
- Teams +0xD0
- Fashions +0xE0
- Quests +0xE8
- Charges +0xF8
- Activities +0x120

OpInfo 필드 45개가 출력됐으며, Chapters Dictionary는 61개 항목이다. 기존에 확인한 20000000 → BoxStatus=7, 20000100 → BoxStatus=1도 재현됐다.

뒤이어 수신된 seq=2 / OpCode=0 / ReturnCode=0 응답은 User/Items/Heros/Chapters가 null이었다. Bootstrap 본 응답과 별도 응답으로 분리한다.

### 17.4 Update/TryOutput 반환값 해석

응답이 도착하기 전후로 KCPTube.Update의 음수 반환값과 KCPTube.TryOutput ret=-1이 여러 차례 관측됐다. 그 뒤 동일 SerialNumber의 응답이 정상 수신됐으므로, 이 값만으로 연결 실패나 요청 실패라고 판단하지 않는다. 각 반환값의 의미는 별도 Ghidra 분석 대상으로 유지한다.

### 17.5 AssetBundle 요청 분리

Bootstrap 응답 처리 뒤 다음 UnityWebRequest가 관측됐다.

- activityicon_001__cn.assetbundle
- yingyuanuiatlas.assetbundle
- ui_eff_mainsence.assetbundle

이들은 OSS AssetBundle 로드 요청이며, OpInfo 게임 상태 요청/응답과 구분한다. 현재 로그에서는 body가 없고 method 문자열도 비어 있으므로 이를 창고 데이터 요청으로 해석하지 않는다.

## 18. 창고 UI의 DataCenter 캐시 사용 경로 — Ghidra 정적 분석

research/Ghidra_Listing_txt/WA.txt와 DA.txt를 확인해 창고 화면이 데이터를 표시하는 흐름을 역추적했다.

### 18.1 DemandOpen은 화면 진입 처리

WareHousePanelMono.DemandOpen @ 0104e508의 Calls OUT은 XLua.DelegateBridge, AliothEngine.GUIScreen.DemandOpen, System.Int32.Parse다.

해당 함수 Listing에는 ProtocolGame_SendRequest, CSBehaviour.RequestOp, NetworkCenter.Send, KCPTube.Send 호출이 없다.

따라서 이 함수 자체는 화면을 열고 인자를 파싱하는 UI 진입점이며, **창고 진입 시 서버 요청을 직접 만드는 함수가 아니다.**

### 18.2 RefreshWareHouse → InitData → Show

정적 호출 관계:

- WareHousePanelMono.RefreshWareHouse @ 0104c1f8
  - InitData @ 0104ace0
  - Show @ 0104c170
    - ShowEquip @ 0104bb14
    - ShowGoods @ 0104d6e8

즉 창고 갱신 시 먼저 InitData에서 목록을 만들고, 그 다음 Show가 화면 유형에 맞춰 목록을 표시한다.

### 18.3 InitData가 DataCenter 캐시에서 목록 구성

WareHousePanelMono.InitData @ 0104ace0에서 확인된 호출:

- DataCenter singleton 접근
- DataCenter +0x78의 category dictionary 접근
- Dictionary Values, ContainsKey, get_Item
- LINQ Where, OrderBy, OrderByDescending, ThenBy, ThenByDescending, ToList
- 생성한 List를 창고 panel 객체의 여러 필드에 저장

Listing상 panel의 +0x10, +0x18, +0x20, +0x28, +0x30, +0x38, +0x40, +0x48 및 +0xD8, +0xE0, +0xE8, +0xF0에 목록 객체가 설정된다.

모든 목록 필드의 정확한 UI 분류 의미는 아직 매핑 중이지만, **창고 화면에 사용할 목록을 DataCenter 내부 데이터에서 필터링/정렬하여 별도 List로 만드는 동작**은 Listing으로 확인됐다.

### 18.4 ShowGoods가 List를 LoopScrollRect에 바인딩

WareHousePanelMono.ShowGoods @ 0104d6e8:

- panel +0xD4의 모드 값에 따라 +0xE0, +0xE8, +0xF0 중 목록 선택
- 선택한 목록을 panel +0xF8에 저장
- List<object>.ToArray
- LoopScrollRect.set_objectsToFill
- LoopScrollRect.ClearCells
- LoopScrollRect.RefillCells

따라서 창고 아이템 목록은 이 시점에 이미 만들어진 List를 스크롤 UI에 바인딩하는 구조다.

### 18.5 개별 아이템 UI 구성

WareHousePanelMono.SetGoodsItemByInfo @ 0104dd38는 전달받은 UI 객체/정보 객체를 사용해 BaseMono.GetUIData, UIData.set_data, EquipInfo.get_Id, EquipInfo.get_EquipmentId, EquipInfo.get_HeroId, EquipItemMono.Show, ShowNew, ShowUser, ShowLocked 등을 호출한다.

이 함수도 UI 항목 구성 함수이며 네트워크 요청 함수가 아니다.

### 18.6 Bootstrap Items → DataCenter MergeItem → 창고 캐시

research/Ghidra_Listing_txt/DA.txt에서 확인:

- DataCenter.ProccessRequestRes @ 016e203c가 DataCenter.MergeItem @ 016e4700을 호출한다.
- MergeItem은 입력 Dictionary를 순회한다.
- DataCenter +0x78의 Dictionary<Int32Enum, Dictionary<int, object>> 구조를 조회/갱신한다.
- DataManager.TryGetBaseData를 통해 BaseData를 얻고 BaseData.type에 따라 category key를 선택한다.
- 확인된 type/category 분기: 0x1F → 2, 0x22 → 0, 0x41 → 1.
- ProtoItem.Status == 1인 항목은 해당 category dictionary에서 제거하는 경로가 있다.
- ProtoItem.Count <= 0인 항목도 제거 경로로 들어가며, 양수 Count는 유지된다.

따라서 현재 증거를 연결하면:

Bootstrap OpInfo.Items
→ DataCenter.ProccessRequestRes
→ DataCenter.MergeItem
→ DataCenter +0x78 category별 item cache
→ WareHousePanelMono.InitData
→ 필터/정렬된 List 생성
→ WareHousePanelMono.ShowGoods
→ LoopScrollRect
→ 창고 아이템 UI

**창고 기본 목록은 Bootstrap 응답에서 병합된 DataCenter 캐시를 사용해 구성되는 경로가 정적 분석으로 연결됐다.** 다만 런타임에서 각 category의 실제 항목 수와 UI 목록의 일치 여부는 다음 hook으로 확인한다.

## 19. v4.19 창고 캐시 추적 hook 반영

research/justice_hook.js를 v4.19로 갱신했다.

추가 hook:

- DataCenter.MergeItem
- WareHousePanelMono.DemandOpen
- WareHousePanelMono.RefreshWareHouse
- WareHousePanelMono.InitData
- WareHousePanelMono.ShowGoods
- WareHousePanelMono.RefreshScroll
- WareHousePanelMono.SetGoodsItemByInfo
- WareHousePanelMono.RefreshEquipItem

출력 범위:
- 객체 class/address
- Dictionary/List count
- panel mode 및 +0xD8/+0xE0/+0xE8/+0xF0/+0xF8 목록 포인터/count
- 인자가 정확히 ProtoItem인 경우에 한해 Id(+0x10), Status(+0x14), Count(+0x18)

인증 토큰, 계정 식별자, 임의 객체 필드 전체, protobuf/encrypted buffer, 패킷 원문은 출력하지 않는다.

Git commit: e6243b1f2482756eb06dfbba3af3d9f0e3b72ee8
message: trace: inspect warehouse cached inventory binding

### 다음 runtime 검증

1. v4.19 hook으로 로그인 후 메인화면 진입
2. 창고 열기
3. 로그에서 ITEM_MERGE와 WAREHOUSE 구간을 분리
4. WAREHOUSE_STATE의 list count 확인
5. WAREHOUSE_ITEM에서 실제 arg class가 ProtoItem, EquipInfo, 기타 어떤 형식인지 확인
6. 기본 창고 및 장비/재료/소품 탭 전환 시 목록 count가 어떻게 바뀌는지 비교

이 결과로 Bootstrap Items가 DataCenter 캐시에 들어간 뒤 창고 화면의 어떤 List로 전달되는지 runtime에서 확정한다.

**Local Server/KCP DH64 구현은 계속 보류한다. 현재 우선순위는 Bootstrap Player State와 창고 UI의 데이터 연결을 완성하는 것이다.**

## 20. 2026-10-02 Bootstrap 최소 Response 계약 분석 착수

### 20.1 분석 기준

Local Private Server 목표에 맞춰 Bootstrap OpCode=2를 게임 내부 전체 구조가 아니라 **Client가 Main 진입에 요구하는 Response 계약** 관점에서 분석한다.

현재 Git/runtime 증거:
- KCPTube.Send의 요청 객체는 OpInfo이며 OpCode=2, ReturnCode=0.
- SerialNumber=66149422 요청과 응답이 일치한다.
- 응답은 KCPTube.TryRead → Deserialize<object> → NetworkCenter.TryHandleResponse → DataCenter.ProccessRequestRes로 처리된다.
- Bootstrap OpInfo에는 User, Heros, Items, Weapons, Equiments, Chapters, Sections, Teams, ViewItems, Fashions, Quests, Shops, Charges, Friends, Exam, Rival, Ranks, Activities 등이 존재한다.
- Items는 ProccessRequestRes → MergeItem → DataCenter category cache로 병합된다.
- Chapters는 runtime에서 61개가 확인되며 OpInfo +0xC0에 위치한다.

### 20.2 현재 계약 분류

| 필드 | 현재 상태 | 서버 구현 관점 |
|---|---|---|
| User | CONFIRMED | 필수 후보 |
| Items | CONFIRMED | 필수 후보 |
| Heros | CONFIRMED | 필수 후보 |
| Weapons | CONFIRMED | 필수 후보 |
| Equiments | CONFIRMED | 필수 후보 |
| Chapters | CONFIRMED | 메인/진행 상태 후보 |
| Sections | CONFIRMED | 메인/진행 상태 후보 |
| Teams | CONFIRMED | 사용 여부 추가 확인 |
| ViewItems | CONFIRMED | 사용 여부 추가 확인 |
| Fashions | CONFIRMED | 사용 여부 추가 확인 |
| Quests | CONFIRMED | 사용 여부 추가 확인 |
| Shops | CONFIRMED | 사용 여부 추가 확인 |
| Charges | CONFIRMED | 사용 여부 추가 확인 |
| Friends/Exam/Rival/Ranks/Activities | CONFIRMED | 메인 진입 필수 여부 미확정 |

주의: CONFIRMED는 'OpInfo에 존재/런타임 관측됨'이라는 의미이며 'Main 화면 진입에 반드시 필요'하다는 의미가 아니다.

### 20.3 다음 분석

1. DataCenter.ProccessRequestRes의 실제 field 처리 순서를 Ghidra 기준으로 정리한다.
2. 각 Merge 계열 호출이 Main 진입 전에 반드시 실행되는지 확인한다.
3. Main Menu 최초 화면에서 접근되는 State를 XREF/런타임 로그로 좁힌다.
4. 필수 필드만 최소 Bootstrap Response 계약으로 분리한다.
5. 아이템/캐릭터의 실제 이름/설명은 필요할 때만 참고용 Unity 데이터 경로를 사용한다.
6. 계약 확정 후 별도 Local Server 구현 TASK로 넘긴다.

### 20.4 분석 중단 기준

다음이 확인되면 해당 내부 구조 분석을 종료하고 서버 구현으로 이동한다.

- Request 식별값/OpCode
- Response type 및 성공 ReturnCode
- Main 진입에 필요한 필드
- Client response 처리 순서
- 최소 State 값
- 다음 Request 또는 Main 진입 조건

전체 Item/Character namespace와 UI 내부 구현은 서버 계약에 필요하지 않으면 더 이상 추적하지 않는다.


## 21. 2026-10-02 v4.21 창고/Bootstrap 런타임 추적 보강

### 21.1 변경

`research/justice_hook.js`를 **v4.21**로 갱신했다.

- v4.20 창고 추적 로그를 유지
- `[ITEM_MERGE]` / `[WAREHOUSE]` / `[WAREHOUSE_STATE]` / `[WAREHOUSE_ITEM]` 추적 유지
- Bootstrap dictionary dump 변수의 중복 선언을 제거해 스크립트 실행 충돌 가능성을 수정
- 시작 시 `justice_hook v4.21` 버전 로그 출력
- 기존 보안 제한(토큰/패킷 원문/임의 객체 전체 dump 금지) 유지

Git commit: `e9616638a19f5b7bfa114076b5f5d14fb87b0f5c`

### 21.2 다음 실기기 확인

로그인 → 메인 → 창고 순서로 실행하고 다음 4개를 확인한다.

1. `[ITEM_MERGE]` incoming Dictionary count
2. `[WAREHOUSE_STATE]` InitData/ShowGoods List count
3. `[WAREHOUSE_ITEM]` 실제 정보 객체 class와 ProtoItem 여부
4. 창고 탭 전환 시 List count 변화

판정 기준:

```
Bootstrap Items count > 0
 → MergeItem 정상
 → Warehouse List count > 0
 → SetGoodsItemByInfo 호출
```

까지 연결되면 **Bootstrap Items → DataCenter cache → Warehouse UI** 경로를 runtime에서도 확정하고, 별도 창고 요청 탐색을 종료한다.

반대로 `MergeItem`은 정상인데 `InitData` List가 비어 있으면 category/type 필터 분기를 추가 추적한다.

현재는 코드 반영까지 완료됐으며, 실제 List/Item count는 다음 실기기 로그에서 확정한다.

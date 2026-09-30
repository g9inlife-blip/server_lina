# 2026-09-30 인게임 네트워크 Chapter Box 후속 분석

## 14. Chapter BoxStatus 직접 write 추적 결과

이번 단계에서는 `ProtoChapter.BoxStatus`의 실제 변경 지점을 찾는 것을 우선했다.

### 14.1 setter 자체는 단순 field write

`ProtoChapter$$set_BoxStatus @ 015acf8c`:

```text
015acf8c  str w1,[x0,#0x1c]
015acf90  ret
```

즉 `ProtoChapter + 0x1C = BoxStatus`가 확정된다.

### 14.2 setter caller는 현재 Listing에서 직접 확보되지 않음

GitHub Ghidra Listing 검색에서는 `set_BoxStatus`의 Calls IN이 비어 있다. 따라서 현재 자료만으로 특정 response/merge 함수가 setter를 직접 호출한다고 단정할 수 없다.

특히 `DataCenter.ProccessRequestRes @ 016e203c`가 opcode `0x14` 처리 후 `set_BoxStatus`를 호출한다고 아직 확정하지 않는다.

### 14.3 BoxStatus 읽기 경로는 확정

```text
ChapBoxMono.LayBoxItem @ 00e55c80
BattleMapMono.LayChapterItem @ 00e4f918
BattleSectionMono.SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
        ↓
BoxStatus & mask
```

Chapter Box UI와 Section Box UI가 동일한 `BoxStatus` bitmask를 사용한다.

## 15. Chapter 상태 merge 후보 재추적

### 15.1 MergeSectionSnapShot

`DataCenter.MergeSectionSnapShot @ 016e5908`는 실제 함수 주소가 여러 Listing의 Calls IN에서 확인되지만, 현재 저장소에는 이 함수의 독립 Function Listing 본문이 없다.

따라서 현재 확인 가능한 것은 **함수 존재 및 DataManager 관련 참조**까지이며, 내부에서 `ProtoChapter +0x1C`를 쓰는지는 미확정이다.

### 15.2 MergeSections

`DataCenter.MergeSections @ 016e55dc`도 존재가 확인된다.

검색 결과에서는 `Dictionary<int, object>` 계열 입력을 순회하는 구조라는 기존 분석 기록이 있으나, 현재 검색 결과만으로 `ProtoChapter.BoxStatus`와 직접 연결되는 field write는 확인되지 않았다.

따라서:

```text
GetSections(0x13)
 → MergeSections
 → ProtoChapter
```

의 전체 연결은 아직 가설 단계로 유지한다.

### 15.3 MergeItem / MergeEquip / MergeWeapon

다음 함수들의 존재 및 DataManager 관계는 확인된다.

```text
MergeItem  @ 016e4700
MergeEquip @ 016e4348
MergeWeapon @ 016e5be4
```

하지만 현재 Listing 인덱스에는 독립 본문이 없어 Chapter BoxStatus와의 직접 관계는 확인되지 않았다.

특히 `MergeItem`은 Chapter Box 수령 후 실제 아이템 보상이 추가되는 경로와 연결될 가능성은 있으나, 현재 증거만으로 opcode `0x14`의 보상 처리 함수라고 확정하지 않는다.

## 16. ProccessRequestRes 주변의 현재 결론

`NetworkCenter.TryHandleResponse @ 015b41e0`에서:

```text
Request.SetResponse(OpInfo)
        ↓
callback
        ↓
DataCenter.ProccessRequestRes @ 016e203c
```

호출은 확정되어 있다.

그러나 `ProccessRequestRes`의 독립 Listing 본문이 현재 저장소에 없기 때문에 opcode `0x14` 분기와 `BoxStatus` 갱신을 직접 확인하지 못했다.

따라서 현재 가장 안전한 모델은:

```text
GetChapterBoxReward
  opcode 0x14
        ↓
NetworkCenter / TCPTube
        ↓
Deserialize → OpInfo
        ↓
ProccessRequestRes
        ↓
[Chapter state merge 지점 미확정]
        ↓
ProtoChapter.BoxStatus +0x1C
```

이다.

## 17. 추가로 확인된 Section 상태 경로

`GetSections @ 00ddea78`는 opcode `0x13`이고 u32 인자 1개를 전달한다.

현재 `MergeSections @ 016e55dc`가 별도로 존재하므로 Section 목록 응답을 DataCenter 상태로 병합하는 후보로 볼 수 있다.

다만 `MergeSections`와 `MergeSectionSnapShot` 중 어느 것이 특정 response opcode를 처리하는지는 현재 증거만으로 결정하지 않는다.

## 18. 다음 작업

다음 단계는 함수 이름 추정이 아니라 **ProtoChapter 타입/필드 자체를 역으로 추적**한다.

우선순위:

1. `ProtoChapter` 생성자/초기화 함수 검색
2. `ProtoChapter.Id/Status/Progress/BoxStatus` setter의 Calls IN 비교
3. `set_Progress`, `set_Status`, `set_Id`가 같은 함수에서 연속 호출되는지 검색
4. 그 함수가 `MergeSections`, `MergeSectionSnapShot`, `ProccessRequestRes`와 연결되는지 확인
5. 가능하면 원본 Ghidra Listing에서 `str w?,[x?,#0x1c]` 직접 검색
6. 마지막으로 opcode `0x14` response와 BoxStatus bit 변경을 PCAP/runtime에서 검증

현재는 `0x14 → BoxStatus`를 아직 미확정으로 유지한다.

## 19. ProtoChapter 생성자/Setter 역추적 결과

이번 단계에서 실제 Listing을 다시 확인했다.

### 19.1 생성자는 상태 필드를 초기화하지 않음

`ProtoChapter$$.ctor @ 015acff8`:

```text
015acff8  mov x1,xzr
015acffc  b 0x02194104
```

즉 현재 확보된 생성자 Listing에는 `Id/Status/Progress/BoxStatus`에 대한 명시적 초기화가 없다. 단순히 `System.Object$$.ctor`로 전달된다.

### 19.2 4개 setter 모두 단순 field write

확인된 offset:

```text
set_Id         @ 015acf5c → [x0,#0x10]
set_Status     @ 015acf6c → [x0,#0x14]
set_Progress   @ 015acf7c → [x0,#0x18]
set_BoxStatus  @ 015acf8c → [x0,#0x1c]
```

특히 `set_BoxStatus`의 Calls IN은 비어 있으며, 다른 3개 setter 역시 현재 저장된 Function Listing에서 Calls IN이 확인되지 않는다.

### 19.3 중요한 결과

따라서 **setter 호출 체인을 따라가는 방식은 현재 Listing 데이터에서는 막혀 있다.**

현재 가장 유효한 다음 방향은:

```text
ProtoChapter setter 호출 추적
        X  (Calls IN 미확보)
        
        ↓ 전환
        
ProtoChapter 객체를 생성/채우는 상위 함수
        ↓
field offset +0x10/+0x14/+0x18/+0x1c
        ↓
MergeSections / MergeSectionSnapShot / ProccessRequestRes
```

즉 다음 단계에서는 함수명보다 **`[x?,#0x10]`, `[x?,#0x14]`, `[x?,#0x18]`, `[x?,#0x1c]`가 함께 등장하는 Listing**을 찾는 것이 우선이다.

### 19.4 현재 결론

- `ProtoChapter +0x1C = BoxStatus`: 확정
- `BoxStatus & mask` 방식: 확정
- 생성자에서 BoxStatus 초기화: 현재 Listing상 확인되지 않음
- setter 직접 호출자: 미확인
- `opcode 0x14 → BoxStatus`: 아직 미확정
- 다음 핵심 목표: **4개 필드 offset을 함께 쓰는 상위 merge/deserialize 함수 확보**


## 20. Merge 계열 재추적 결과

이번에는 후보 함수 자체의 의미를 좁혔다.

### 20.1 MergeSectionSnapShot은 Section 상태 병합 쪽으로 확인

기존 Assembly 분석 기록에서 `MergeSectionSnapShot @ 016e5908`는 `Dictionary<int,int>`를 순회하고 기존 dictionary와 비교한 뒤 변경된 값을 `set_Item`으로 갱신한다.

또한 현재 기록된 응답 경로는:

```text
opcode 0x13
 → response
 → ProccessRequestRes
 → MergeSectionSnapShot
 → Section field
```

형태다.

따라서 이 함수는 **Chapter BoxStatus 갱신 후보라기보다 Section snapshot 병합 함수**로 보는 것이 더 타당해졌다.

### 20.2 MergeSections도 Section dictionary 처리

`MergeSections @ 016e55dc` 역시 Section dictionary를 처리하며, 기존 분석에는 특정 Status 조건에서 dictionary `set_Item`을 수행하는 구조가 기록되어 있다.

따라서 현재까지는:

```text
MergeSectionSnapShot → Section snapshot
MergeSections        → Section collection
```

으로 역할이 좁혀진다.

둘 모두에서 `ProtoChapter +0x1C` 직접 write는 확인되지 않았다.

### 20.3 ProccessRequestRes의 역할

`ProccessRequestRes @ 016e203c`는 여러 상태 처리 함수의 호출자로 확인되지만 독립 Listing 본문이 없다.

따라서 현재 증거로는:

```text
ProccessRequestRes
 ├─ Section 관련 처리
 ├─ Item/Equip/Weapon 관련 처리
 ├─ UserInfo 관련 처리
 └─ 기타 상태 처리
```

정도로만 확정할 수 있다.

### 20.4 중요한 방향 전환

Chapter BoxStatus를 찾기 위해 `MergeSections / MergeSectionSnapShot`를 계속 파는 것보다,

**Chapter 객체 자체가 DataCenter 내부에서 어디에 저장되고 어떤 함수가 갱신하는지 찾는 것**이 다음 핵심이다.

다음 검색 대상:

1. `Dictionary<int, ProtoChapter>` 또는 `Dictionary<int, object>` 형태의 Chapter 저장소
2. `ProtoChapter`를 반환/검색하는 DataCenter 함수
3. Chapter Id를 key로 사용하는 함수
4. `GetChapterBoxReward(0x14)`와 같은 opcode 주변의 상태 객체 처리
5. 실제 PCAP에서 `0x14` response payload 변화와 BoxStatus bit 변화를 대조

현재 결론은 그대로다.

**`0x14 → BoxStatus`는 아직 미확정이며, Section merge 계열은 Chapter BoxStatus의 직접 갱신점이 아닌 것으로 범위를 좁혔다.**


## 21. OpInfo.Chapters 진입점 재확인

`OpInfo$$get_Chapters @ 015aadec`는 `[x0,#0xc0]`를 읽고, `set_Chapters @ 015aadf4`는 `[x0,#0xc0]`에 저장한다. 따라서 `OpInfo +0xC0 = Chapters`가 확정된다.

`set_Chapters`의 Calls IN은 비어 있어 실제 deserialize 호출자는 아직 확인되지 않았다. `ProtoChapter` 검색에서도 상위 호출자가 거의 잡히지 않아, Chapter 객체를 직접 추적하기보다 **OpInfo.Chapters가 `ProccessRequestRes`로 넘어가는 지점**을 찾는 것이 더 효율적이다.

`DataCenter$$RefreshBoxList @ 016e6c64`와 두 람다(`016ea0d4`, `016ea154`)도 확인했지만, 현재 참조는 `ItemData.isBoxItem` 및 Excel Item 데이터 처리 쪽이므로 `ProtoChapter.BoxStatus` 갱신점으로 연결할 근거가 없다.

현재 흐름은 다음 수준까지 확정한다.

```text
Server response
  ↓ deserialize
OpInfo.Chapters (+0xC0)
  ↓
ProccessRequestRes
  ↓
Chapter 상태 저장/병합  ← 미확정
  ↓
ProtoChapter.BoxStatus (+0x1C)
```

다음은 `OpInfo$$get_Chapters` 호출자와 `ProccessRequestRes` 내부의 Chapters 처리 지점을 집중 추적한다.

현재 결론: `OpInfo +0xC0 = Chapters` **확정**, `ProtoChapter +0x1C = BoxStatus` **확정**, `0x14 → BoxStatus`는 **미확정**.


## 22. OpInfo.Chapters 상위 사용처 재추적

이번 단계에서는 `get_Chapters`의 직접 호출자 확보를 다시 시도하고 Chapter UI 진입점과 대조했다.

### 22.1 직접 setter/caller는 여전히 미확보

`ProtoChapter$$set_Id`, `set_Status`, `set_Progress`, `set_BoxStatus` Function Listing은 모두 Calls IN이 비어 있다.

따라서 현재 Listing 인덱스만으로는 Chapter 객체를 채우는 deserialize/merge 함수가 setter를 직접 호출한다고 볼 수 없다.

### 22.2 Chapter 데이터의 실제 소비 지점은 확인

`BattleMapMono$$InitChapters @ 00e4e080`가 `Chapters` 관련 처리의 핵심 UI 진입점으로 반복 확인된다.

Calls IN 검색에서도 `BattleMapMono$$InitChapters`가 여러 UI/데이터 접근 함수에서 반복 참조된다. 따라서 `OpInfo.Chapters`가 최종적으로 Chapter 맵 UI 구성에 사용되는 구조는 뒷받침된다.

현재 구조:

```text
OpInfo.Chapters (+0xC0)
        ↓
DataCenter 상태
        ↓
BattleMapMono.InitChapters @ 00e4e080
        ↓
Chapter/Box UI
```

### 22.3 중요한 제한

`BattleMapMono.InitChapters`의 독립 Listing 본문은 현재 인덱스에서 확보되지 않았다. 따라서 이 함수가 `get_Chapters`를 직접 호출하는지, 별도 Chapter cache를 읽는지는 아직 확정하지 않는다.

PCAP 파일 자체도 GitHub repository에 binary로 존재하지 않아 현재 GitHub connector만으로 `0x14` response payload bytes를 직접 대조할 수 없다.

### 22.4 다음 우선순위

1. `BattleMapMono.InitChapters @ 00e4e080` 실제 Listing 확보
2. 내부의 `get_Chapters` / `ProtoChapter` / `BoxStatus` 접근 확인
3. `new ProtoChapter` 또는 deserialize 코드 탐색
4. `Id/Status/Progress/BoxStatus` 4개 field 동시 접근 코드 탐색
5. 로컬 PCAP이 있으면 `0x13/0x14` response 직접 추출 및 상태 대조

현재 결론:

**`OpInfo +0xC0 = Chapters` 확정 / `ProtoChapter +0x1C = BoxStatus` 확정 / `BattleMapMono.InitChapters` Chapter 소비 지점 확인 / `0x14 → BoxStatus` 미확정.**


## 23. 2026-09-30 Chapter 전투 PCAP JSON 확보

`research/PCAP/챕터선택_전투승리보상까지.json`이 push되어 실제 패킷 JSON을 직접 대조할 수 있게 되었다.

### 23.1 확인 결과

```text
총 164 packet
UDP/KCP: 10.215.173.1:33922 ↔ 182.92.62.79:8000
```

주요 application packet:

```text
89   client → server    77 bytes
91   server → client   221 bytes
93   client → server    77 bytes
95   server → client   301 bytes
137  client → server    93 bytes
139  server → client   269 bytes
146  client → server    77 bytes
147  client → server    77 bytes
149  server → client   237 bytes
159  client → server   109 bytes
162  server → client  1400 bytes
163  server → client   481 bytes
```

162/163은 연속된 대형 서버 응답으로 확인되며 KCP fragment 재조립 대상으로 잡는다.

### 23.2 Framing

application packet 앞부분에 다음 공통 값이 반복된다.

```text
1eee45d6fd69e607
51 ...  client → server
52 ...  server → client
```

예:

```text
frame 139
1eee45d6fd69e607 51 0020 00a6e338c2 0f000000 f1000000 ...

frame 149
1eee45d6fd69e607 51 0020 00e0ea38c2 10000000 d1000000 ...
```

따라서 framing 영역과 application 데이터 영역을 분리해서 추적할 수 있다.

### 23.3 Chapter/BoxStatus 추적에 대한 의미

현재 JSON에서 application 데이터 자체는 암호화된 형태이므로 plaintext `0x13/0x14`는 아직 직접 확인되지 않는다.

따라서 현재 가장 중요한 후보 구간은:

```text
frame 159
   ↓
frame 162 + 163
```

이 구간을 기준으로 이후 `OpInfo.Chapters`와 `ProtoChapter.BoxStatus` 변화를 대조한다.

단, 현재 단계에서 **162/163이 0x14 응답이라고 확정하지 않는다.**

### 23.4 상태 갱신

- PCAP JSON 확보: 확인
- 164 packet 분석: 확인
- KCP application packet 식별: 확인
- 162+163 대형 응답 확인: 확인
- plaintext opcode 0x13/0x14: 미확인
- 0x14 → BoxStatus: 미확정

다음은 159 → 162/163 구간의 실제 application message 복원과 `OpInfo.Chapters` 대조를 우선한다.


## 24. 2026-09-30 KCP 64-bit Header 및 암호화 메시지 경계 확정

PCAP JSON과 Ghidra의 `Alioth.S1.Core.KCP$$EncodeSegment @ 015b8774`를 교차 확인한 결과, 이번 PCAP의 KCP header 구조를 직접 확정했다.

### 24.1 게임 KCP Segment 구조

`EncodeSegment`가 다음 순서로 기록한다.

```text
+0x00  uint64  Segment.Conv
+0x08  uint8   Cmd
+0x09  uint8   Frg
+0x0A  uint16  Wnd
+0x0C  uint32  Ts
+0x10  uint32  Sn
+0x14  uint32  Una
+0x18  uint32  Len
+0x1C  data
```

즉 이 게임의 KCP segment header는 **28 bytes**이며, 일반적인 32-bit conv가 아니라 64-bit conv를 사용한다.

실제 PCAP frame 162:

```text
conv = 1eee45d6fd69e607
cmd  = 0x51
frg  = 1
wnd  = 0x0020
sn   = 0x11
una  = 0x06
len  = 0x55c = 1372
```

frame 163:

```text
conv = 1eee45d6fd69e607
cmd  = 0x51
frg  = 0
wnd  = 0x0020
sn   = 0x12
una  = 0x06
len  = 0x1c5 = 453
```

따라서 두 packet은 같은 conv에서 `frg 1 → 0`, `sn 0x11 → 0x12`로 이어지는 하나의 KCP message로 확정할 수 있다.

### 24.2 실제 application message 재조립

```text
frame 162 data = 1372 bytes
frame 163 data =  453 bytes
------------------------
총              1825 bytes
```

재조립 후 첫 부분은:

```text
80
5710e3494fa79b32be5d738c23d85593
...
```

Ghidra에서 확인한 `KCPTube.TryRead → DecryptUnSafe` 경로와 대조하면 application message는 다음 구조로 해석된다.

```text
[0x80 flags]
[16-byte IV]
[ciphertext]
```

이번 162+163 응답의 경우:

```text
flags      = 0x80
IV         = c4f0862cf0271983b553998be415226a
ciphertext = 1808 bytes
```

`1808 % 16 == 0`이므로 AES/Rijndael block ciphertext 경계도 정확히 맞는다.

### 24.3 요청 frame 159도 동일 구조

frame 159는 KCP data 81 bytes이며:

```text
flags      = 0x80
IV         = 5710e3494fa79b32be5d738c23d85593
ciphertext = 64 bytes
```

즉 전투 직전/직후의 요청도 동일한 암호화 application framing을 사용한다.

### 24.4 중요한 변경점

이제 단순히 `162/163이 큰 응답이다` 수준이 아니라:

```text
frame 159
  KCP reassembly
  ↓
  0x80 + IV16 + ciphertext64

frame 162 + 163
  KCP reassembly
  ↓
  0x80 + IV16 + ciphertext1808
```

까지 확정했다.

따라서 다음 단계는 KCP 분석이 아니라 **session Key 확보 → 159 request / 162+163 response 복호화**다.

### 24.5 Chapter/BoxStatus 추적 목표

복호화가 성공하면 다음 순서로 바로 확인한다.

```text
plaintext
 ↓
OperationCode
 ↓
OpInfo / response object
 ↓
Chapters (+0xC0)
 ↓
ProtoChapter
 ├─ Id       +0x10
 ├─ Status   +0x14
 ├─ Progress +0x18
 └─ BoxStatus+0x1C
```

특히 162+163의 1808-byte 응답에서 `ProtoChapter.BoxStatus`가 포함되는지 직접 확인한다.

### 24.6 현재 결론

- 64-bit KCP conv: **확정**
- KCP header 28 bytes: **확정**
- frame 162+163 단일 fragmented message: **확정**
- 응답 flags `0x80`: **확정**
- IV 16 bytes: **확정**
- ciphertext 1808 bytes: **확정**
- 16-byte block alignment: **확정**
- plaintext opcode `0x13/0x14`: **아직 미확인**
- `0x14 → BoxStatus`: **아직 미확정**

다음 작업은 `KCPTube.Handshake2 → Key` 생성값을 runtime/코드에서 확보하여 이 두 메시지를 실제 복호화하는 것이다.


## 25. 2026-09-30 KCP 실제 복호화 결과에 따른 경로 정정

이번 단계에서 `research/PCAP/챕터선택_전투승리보상까지.json`의 KCP session key를 실제 복구하고 frame 159 / 162+163을 복호화했다.

### 25.1 session key 실제 확보

KCP client public:

```text
0x3B235655562743FA
0xD4BED6816A9F1C5C
```

server public:

```text
0x7637ACF954E564B3
0xDD73013D938774B9
```

DH modulus:

```text
p = 0xFFFFFFFFFFFFFFC5
  = 2^64 - 59
```

discrete log으로 복구한 client private:

```text
private1 = 0x12499F5C0DDB1AF5
private2 = 0x6D0F828A5EA102C2
```

shared secret:

```text
secret1 = 0xEB751E69D959ADC0
secret2 = 0xAD53F6266C3490EA
```

실제 Key:

```text
c0ad59d9691e75ebea90346c26f653ad
```

### 25.2 frame 159 실제 plaintext

frame 159는:

```text
flag = 0x80
OpCode = 0x17
```

으로 복호화된다.

따라서 기존에 frame 159를 `GetChapterBoxReward` 요청으로 연결한 것은 잘못된 연결이다.

### 25.3 frame 162+163 실제 plaintext

두 KCP fragment를 재조립하면:

```text
flag = 0xC4
IV = f0862cf0271983b553998be415226aee
ciphertext = 1808 bytes
```

복호화 결과는 gzip stream이며 gzip 해제 후 5749-byte protobuf-like data가 나온다.

Top-level:

```text
field 1 = SerialNumber
field 2 = OpCode 0x17
```

즉:

```text
159 request
   ↓
OpCode 0x17

162+163 response
   ↓
OpCode 0x17
```

이다.

### 25.4 현재 가설 변경

기존:

```text
159
 ↓
162+163
 ↓
0x14
 ↓
BoxStatus
```

는 폐기한다.

현재:

```text
159
 ↓
0x17 request
 ↓
162+163
 ↓
0x17 response
 ↓
[Chapter state 포함 여부 별도 확인]
```

으로 수정한다.

### 25.5 0x14 Box reward는 별도 capture 필요

정적 분석상:

```text
GetChapterBoxReward @ 00ddeea8
opcode = 0x14
payload = u32 x2
```

이므로 실제 BoxStatus 변경을 확정하려면 **box를 실제로 클릭하여 보상을 수령하는 별도 PCAP**에서 `0x14` request/response를 확보해야 한다.

현재 PCAP에는 직접 복호화 가능한 application message 중 `0x14`가 확인되지 않았다.

따라서 현재 결론:

- ProtoChapter +0x1C = BoxStatus: 확정
- BoxStatus bitmask 읽기: 확정
- GetChapterBoxReward opcode 0x14: 정적 분석상 확정
- 159 → 162+163 = 0x14: **반증**
- 0x14 response → BoxStatus: 미확정


## 26. 2026-09-30 이벤트던전 Box 보상 선택/오픈/획득 PCAP JSON 분석

추가된 `research/PCAP/이벤트던전_box보상선택_오픈_획득.json`을 Git blob 기준으로 직접 파싱했다.

### 26.1 캡처 규모 및 Game Server 구간

- 총 packet: **103**
- TCP Game Server: `43764 ↔ 8000`
- KCP/UDP Game Server: `45186 ↔ 8000`
- TCP handshake 직후 DH 공개값 교환 확인

TCP client handshake frame 84:

``
length = 0x169
marker = 0x01
public1 raw = `ae a5 9a b9 34 02 73 6d`
public2 raw = `9b 90 eb db b5 0a a6 ed`
```

※ 위 값은 Listing/PCAP 바이트 순서를 구분해서 기록해야 하므로, 실제 분석에서는 raw 8-byte LE 기준으로 사용한다.

서버 frame 86은:

``
length = 0x19
marker = 0x01
serverPublic1 = 0x1e0f84d1514c8dbf
serverPublic2 = 0xe187d59f859685ba
```

이다.

### 26.2 핵심 KCP application packet

```
frame 92  C→S  UDP 45186→8000  UDP length 85
frame 93  S→C  ACK              UDP length 36
frame 94  S→C  UDP 8000→45186  UDP length 389
frame 95  C→S  ACK              UDP length 36
```

KCP header는 28 bytes이므로:

```
frame 92 KCP data length = 0x31 = 49 bytes
frame 94 KCP data length = 0x161 = 353 bytes
```

frame 92 header:

```
conv = 0x43c7af942c0bf54d
cmd  = 0x51
frg  = 0
wnd  = 0x0001
sn   = 0x10
una  = 0x13
len  = 0x31
```

frame 94 header:

```
conv = 0x43c7af942c0bf54d
cmd  = 0x51
frg  = 0
wnd  = 0x0020
sn   = 0x11
una  = 0x13
len  = 0x161
```

즉 이번 캡처는 요청/응답 모두 단일 KCP segment이며 fragment 재조립은 필요 없다.

### 26.3 매우 중요한 암호화 framing 확인

frame 92의 KCP data 49 bytes는 정확히:

```
0x80
+ 16-byte IV
+ 32-byte ciphertext
= 49 bytes
```

즉:

```
flag = 0x80
IV   = b3c9617c319f7d74ffe8d10b33d9bcae
CT   = 32 bytes
```

frame 94도:

```
KCP data = 353 bytes
flag     = 0xC4
IV       = a51324f4b36f138fe67259daee379cd3
CT       = 336 bytes
```

으로 `1 + 16 + (16 × N)` 구조가 정확히 성립한다.

따라서 기존에 확보한 `flag + IV16 + AES/Rijndael ciphertext` 구조와 동일하다.

### 26.4 현재 Box reward 분석에서의 의미

정적 분석으로 이미:

```
ClickGetReward
 → GetChapterBoxReward @ 00ddeea8
 → opcode 0x14
 → chapterId + boxIndex
```

가 확정되어 있다.

이번 캡처는 제목상 Box 보상 선택/오픈/획득 동작을 포함하고 있고, 실제 Game Server KCP application traffic이 **단일 요청(frame 92) → 단일 응답(frame 94)** 형태로 존재한다.

따라서 현재 가장 유력한 매칭은:

```
frame 92  C→S  encrypted request  ← 0x14 후보
frame 94  S→C  encrypted response ← 0x14 후보
```

이다.

단, **복호화 전에는 0x14라고 확정하지 않는다.**

### 26.5 다음 핵심 작업

현재 막힌 부분은 PCAP packet 추출이 아니라 **이번 세션의 DH64 session key**다.

이미 Ghidra에서:

``
DH64::.ctor
 → System.Random::.ctor

DH64::KeyPair
 → Random.Next() #1/#2
 → private = (Next1 << 32) | (Next2 + 1)
 → public = 5^private mod (2^64-59)
```

가 확정되어 있다.

따라서 이번 캡처는 다음 순서로 진행한다.

1. `System.Random` seed/구현 확인
2. 이번 handshake 시점의 private1/private2 재현 가능성 확인
3. session key 생성
4. frame 92 복호화 → request opcode 확인
5. frame 94 복호화 → response opcode/Chapter state 확인
6. response의 `ProtoChapter +0x1C`(BoxStatus) 변화 확인

### 26.6 현재 결론

- 이벤트 Box 보상 PCAP JSON: **확보 및 직접 파싱 완료**
- Game Server KCP request/response pair: **확인**
- request frame 92: **0x14 유력 후보**
- response frame 94: **0x14 response 유력 후보**
- plaintext opcode: **미확정**
- BoxStatus 갱신: **미확정**
- 다음 병목: **이번 세션 DH64 private/session key 재현**


## 27. 2026-09-30 후속 추적 — IsBoxReceived 호출부 및 추가 계정 PCAP 확인

### 27.1 IsBoxReceived 호출부 3곳 확정

`ProtoChapter$$IsBoxReceived @ 015acfe8`의 Calls IN Listing에서 다음 3개 호출부가 확인된다.

```text
ChapBoxMono$$LayBoxItem              @ 00e55c80
BattleMapMono$$LayChapterItem        @ 00e4f918
BattleSectionMono$$SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
```

따라서 Box 수령 상태는 Box 전용 UI뿐 아니라 Chapter Map과 Section Stage Box에서도 동일한 `ProtoChapter.BoxStatus` bitmask를 사용한다.

### 27.2 실제 mask 값은 아직 미확인

현재 GitHub Listing 검색에서는 위 3개 함수의 실제 본문 파일 경로가 검색 인덱스에 바로 노출되지 않아 `BL 015acfe8` 직전의 `w1` 설정값을 확보하지 못했다.

```text
ProtoChapter +0x1C = BoxStatus       확정
IsBoxReceived(mask) = (BoxStatus & mask)!=0 확정
boxIndex → mask 대응               미확정
```

특히 `boxIndex 5 → mask 1`은 아직 단정하지 않는다.

### 27.3 다른 계정 PCAP 추가 확인

사용자가 지정한:

`research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json`

파일명을 GitHub 검색으로 확인했으나 현재 connector 검색 인덱스에서는 정확한 파일명이 반환되지 않았다.

따라서 파일이 Git에 없다고 단정하지 않고, 현재 연결된 GitHub 검색 결과에서는 직접 읽지 못한 상태로 기록한다.

이 PCAP은 제목상 `던전 2회 → Box 오픈 → 보상 획득 → 장비 착용` 순서가 포함되어 있어 BoxStatus 전후 비교에 매우 유용한 후보이다.

### 27.4 다음 추적 순서

1. 해당 다른 계정 PCAP의 Git 존재/검색 가능 여부 재확인
2. 확보되면 KCP session key 복구 후 Box 전후 response 복호화
3. 동일 Chapter snapshot 전후 비교
4. `field 43` Chapter snapshot의 `field 4` 전후 비교
5. Ghidra에서 `00e55c80 / 00e4f918 / 00e53380`의 `IsBoxReceived` 호출 직전 `w1` 상수 확보
6. ProtoChapter serializer/deserializer에서 BoxStatus protobuf field 번호 직접 확정

### 27.5 현재 누적 결론

```text
ProtoChapter +0x1C = BoxStatus                  확정
IsBoxReceived = (BoxStatus & mask) != 0         확정
IsBoxReceived 호출부 3곳                         확정
GetChapterBoxReward = opcode 0x14               확정
0x14 request/response = 이벤트 Box PCAP 후보     유력
0x14 response가 BoxStatus를 갱신                 미확정
boxIndex → mask 값                               미확정
다른 계정 PCAP 직접 비교                         아직 파일 미검색
```

다음 세션은 다른 계정 PCAP의 Git 존재/복호화 → BoxStatus 전후 비교부터 재개한다.


## 28. 2026-09-30 다른 계정 PCAP 복호화 및 실제 0x14 검증

### 28.1 Git 파일 존재 및 DH endian 정정

`research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json`은 Git blob으로 실제 존재한다.

- packet: 306
- blob SHA: `faeb47f64d76158c731c36abb741773e376e46a2`
- KCP client port: `51943`
- KCP server: `182.92.62.79:8000`

기존 기록의 candidate key에는 **server public 8-byte LE 해석 오류**가 있었다.

실제 KCP Handshake2 기준 offset 17/25의 raw bytes:

```
server public #1 raw = cb 43 ff 46 bc 8a d1 d4
server public #2 raw = a8 59 ce f7 2e 5f cc a8
```

BitConverter.ToUInt64 기준 실제 정수:

```
serverPublic1 = 0xd4d18abc46ff43cb
serverPublic2 = 0xa8cc5f2ef7ce59a8
```

client public raw:

```
a6 0f f3 68 ac df 81 d8
ee c2 4e ec ff 6a c7 3b
```

실제 정수:

```
clientPublic1 = 0xd881dfac68f30fa6
clientPublic2 = 0x3bc76affec4ec2ee
```

discrete log으로 검증된 client private:

```
private1 = 0x1021bdff42518bc9
private2 = 0x1711d8ad4dc70e26
```

shared secret:

```
secret1 = 0x490b1c9b2ce9abdc
secret2 = 0xcf8fdf34709590da
```

따라서 이번 세션의 실제 KCP key:

```
dcabe92c9b1c0b49da90957034df8fcf
```

이 key로 실제 application ciphertext의 CBC/PKCS7 복호화가 성공했다.

### 28.2 복호화 성공으로 암호화 경로 재검증

예:

```
frame 260 C→S
flag = 0x80
opcode = 0x16
```

plaintext:

```
field 1 = serial
field 2 = 0x16
field 6 = 20000100
field 7 = 21000080
```

또한:

```
frame 273 C→S
opcode = 0x17
```

까지 정상 복호화되었다.

따라서 새 계정 PCAP에서도:

```
DH64
 ↓
16-byte key
 ↓
Rijndael CBC/PKCS7
 ↓
KCP encrypted application
 ↓
protobuf-like OpInfo
```

경로가 실제 bytes 수준에서 검증된다.

### 28.3 실제 Box reward request 확정

**frame 283 C→S**:

```
KCP cmd = 0x51
encrypted flag = 0x80
plaintext:
field 1 = serial
field 2 = 0x14
field 4 = { field 1 = 20000100, field 2 = 5 }
field 6 = 20000100
field 7 = 1
```

따라서:

```
opcode = 0x14
chapterId = 20,000,100
boxIndex = 5
```

가 실제 PCAP plaintext로 직접 확정된다.

이는 정적 분석의:

```
ChapBoxMono.ClickGetReward
 ↓
GetChapterBoxReward(chapter.id, UIData.data)
 ↓
opcode 0x14
 ↓
chapterId + boxIndex
```

와 정확히 일치한다.

### 28.4 실제 Box reward response 확정

**frame 285 S→C**도 정상 복호화된다.

Top-level:

```
field 1 = serial
field 2 = 0x14
```

그리고:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = nested Chapter data
```

nested Chapter data:

```
field 1 = 20000100
field 3 = 12
field 4 = 3
field 9 = { field1 = 1, field2 = 15 }
field10 = { field1 = 1, field2 = 15 }
field11 = 1
```

즉 **0x14 response에 chapterId=20000100인 Chapter snapshot이 실제 포함**되는 것은 확정이다.

### 28.5 BoxStatus 해석은 여기서 보류

정적 분석으로:

```
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(mask) = (BoxStatus & mask) != 0
mask = 1 << boxIndex
```

가 확정되어 있다.

frame 283의 boxIndex=5이므로 UI 코드 기준 검사 mask는:

```
1 << 5 = 0x20
```

그런데 frame 285의 nested Chapter data에서 field 4 값은:

```
3
```

이다.

따라서 **nested protobuf field 4 = BoxStatus라고 지금 단정하면 안 된다.**

현재 안전한 결론:

- 0x14 request의 chapterId=20000100: 확정
- 0x14 request의 boxIndex=5: 확정
- 0x14 response의 동일 Chapter snapshot: 확정
- ProtoChapter +0x1C = BoxStatus: 확정
- boxIndex 5의 UI 검사 mask = 0x20: 확정
- response nested field 4 = BoxStatus: **보류**
- 0x14 response가 BoxStatus +0x1C를 갱신: **아직 미확정**

특히 field 4=3은 mask 0x20과 직접 일치하지 않으므로, **protobuf field 번호와 ProtoChapter 메모리 field 번호를 동일하다고 가정했던 이전 해석은 폐기**한다.

### 28.6 현재 가장 중요한 다음 작업

이제 암호/PCAP은 병목이 아니다.

다음은 **ProtoChapter protobuf field tag ↔ C# property/메모리 offset 매핑**을 직접 확보하는 것이다.

우선순위:

1. ProtoChapter deserialize/merge 코드에서 field tag 처리 확인
2. field 1 → Id 여부 확인
3. field 2 → Status 여부 확인
4. field 3 → Progress 여부 확인
5. field 4 → BoxStatus 여부 확인
6. field 9/10/11의 실제 property 확인
7. 0x14 response에서 +0x1C write가 발생하는지 확인
8. 필요하면 frame 285 직후 runtime state를 별도 hook으로 비교

### 28.7 이번 단계 최종 상태

```
다른 계정 PCAP Git 존재              확정
DH64 endian 정정                     확정
실제 KCP session key                 dcabe92c9b1c0b49da90957034df8fcf
실제 PCAP CBC/PKCS7 복호화            성공
frame 283 opcode 0x14                확정
frame 283 chapterId 20000100         확정
frame 283 boxIndex 5                 확정
frame 285 opcode 0x14 response       확정
frame 285 Chapter snapshot           확정
ProtoChapter +0x1C = BoxStatus       확정
boxIndex 5 → mask 0x20              확정
protobuf field4 = BoxStatus          보류
0x14 → BoxStatus write               미확정
```

**현재 분석의 핵심 병목은 BoxStatus 값 자체가 아니라 protobuf field tag와 ProtoChapter 메모리 field의 대응 관계다.**

## 29. 2026-09-30 ProtoChapter field mapping 재추적 결과

### 29.1 ProtoChapter Listing 범위 확인

Git의 `research/Ghidra_Listing_txt/AL`에서 `ProtoChapter$$`를 검색한 결과, 현재 저장된 Listing에는 다음 accessor/constructor가 확인된다.

```
get/set_Id
get/set_Status
get/set_Progress
get/set_BoxStatus
get/set_URL1
get/set_URL2
get/set_Readed
get/set_Timeout
get/set_OpeningTime
IsBoxReceived
.ctor
```

현재 Git Listing 검색 결과에는 `MergeFrom/ParseFrom/WriteTo/CalculateSize/Descriptor/Parser` 명시적 serializer 함수가 없다.

### 29.2 현재 강한 정적 증거

```
Id         +0x10
Status     +0x14
Progress   +0x18
BoxStatus  +0x1C
```

`get_BoxStatus`, `set_BoxStatus`, `IsBoxReceived` 모두 `+0x1C`를 직접 사용하므로 메모리 구조는 확정이다.

반면 0x14 response Chapter snapshot은:

```
field 1 = 20000100
field 3 = 12
field 4 = 3
field 9 = {1,15}
field10 = {1,15}
field11 = 1
```

이 값만으로 protobuf field tag와 C# property를 단순 1:1 대응시키면 안 된다.

### 29.3 핵심 재평가

가설 A는 `field 4 = BoxStatus`이지만, boxIndex=5의 단순 mask `1 << 5 = 0x20`과 field4=3이 직접 맞지 않는다.

따라서 현재는 가설 B, 즉 protobuf field 번호와 메모리 offset/property 순서가 단순 대응하지 않을 가능성도 유지한다.

### 29.4 0x14 이후 packet도 비교 대상

Box request 이후:

```
frame 285  S→C  0x14 response
frame 287  C→S
frame 289  S→C
frame 294  C→S
frame 296  S→C
```

가 이어진다. 따라서 BoxStatus가 frame 285에서 즉시 반영되지 않고 후속 response에서 갱신될 가능성도 확인해야 한다.

특히 `285 vs 289 vs 296`의 Chapter snapshot 변화가 중요하다.

### 29.5 다음 정적 분석 목표

1. `ProccessRequestRes @ 016e203c` 실제 Listing 확보
2. response object의 Chapter collection 접근 확인
3. Chapter 생성/병합 함수 확인
4. 해당 함수의 `ProtoChapter.set_*` 또는 `+0x1C` write 확인
5. `StarStatus`와 `BoxStatus`가 같은 merge 경로에서 갱신되는지 비교
6. 0x14 후속 response의 Chapter snapshot 변화와 대조

### 29.6 현재 상태

```
ProtoChapter +0x1C = BoxStatus              확정
IsBoxReceived가 +0x1C를 읽음              확정
0x14 request chapterId/boxIndex             확정
0x14 response Chapter snapshot              확정
protobuf field 4 = BoxStatus                미확정
field 3/4/9/10/11 의미                     미확정
0x14 response 직후 상태 갱신 시점            미확정
serializer Listing 직접 확인                현재 Git 자료에 없음
```

**다음 실질 목표는 285 → 289 → 296의 Chapter snapshot을 비교하거나, 그 값을 생성하는 merge 함수에서 +0x1C write를 직접 잡는 것이다.**
## 30. 2026-09-30 0x14 응답 Chapter snapshot 교차 비교

### 30.1 다른 계정 frame 285

실제 복호화된 frame 285의 field 43:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = Chapter
     ├─ field 1 = 20000100
     ├─ field 3 = 12
     ├─ field 4 = 3
     ├─ field 9 = {1,15}
     ├─ field10 = {1,15}
     └─ field11 = 1
```

### 30.2 기존 통합 PCAP frame 430

기존 계정 frame 430의 동일 구조:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = Chapter
     ├─ field 1 = 20000100
     ├─ field 3 = 6
     ├─ field 4 = 1
     ├─ field 9 = {1,15}
     ├─ field10 = {1,15}
     └─ field11 = 1
```

두 계정에서 동일 chapterId에 대해 `account A: field3=6, field4=1`, `account B: field3=12, field4=3`가 관찰된다.

### 30.3 핵심 관찰

두 PCAP 모두 0x14 request는 `chapterId=20000100`, `boxIndex=5`이다. 그런데 response Chapter의 field4는 각각 1과 3이다.

따라서 현재 데이터만으로 `field4 == BoxStatus`와 `boxIndex 5 == bit 5`를 동시에 만족하는 수령 완료 변화는 관찰되지 않는다.

가능성은 분리한다:

1. field4가 BoxStatus가 아니다.
2. 0x14 response의 Chapter snapshot이 요청 처리 후 최종 BoxStatus가 아니라 기존/부분 snapshot이다.
3. request boxIndex와 UI index가 동일하지 않다.

단, UI의 `IsBoxReceived` 호출부에서는 실제 mask가 `1 << w23`임이 확인되었으므로 UI index와 request boxIndex의 동일성은 별도 검증이 필요하다.

### 30.4 현재 결론 수정

```
ProtoChapter +0x1C = BoxStatus       확정
protobuf Chapter field3 = Progress   유력
protobuf Chapter field4 = 상태값     확정
protobuf Chapter field4 = BoxStatus  유력하지만 미확정
boxIndex → UI mask = 1 << index     정적 코드 확정
request boxIndex == UI index         미확정
0x14 response가 최종 BoxStatus 반환  미확정
```

### 30.5 다음 작업

1. `GetChapterBoxReward @ 00ddeea8`에서 request 두 번째 값의 원천 추적
2. `UIData.data` index와 request `+0x34` 관계 확인
3. `DataCenter.ProccessRequestRes @ 016e203c`의 Chapter 관련 merge 분기 추적
4. `MergeSectionSnapShot` 외 Chapter merge 후보 확인
5. raw Listing 전체에서 `set_BoxStatus @ 015acf8c` callsite 주소 검색
6. Box 요청 전 Chapter snapshot 확보

## 31. 2026-09-30 ClickGetReward / Box index 직접 Listing 재검증

### 31.1 ClickGetReward의 두 번째 인자는 변환 없이 UIData.data

`ChapBoxMono$$ClickGetReward @ 00e5705c` 실제 CH.txt Listing에서 `BaseMono.GetUIData → UIData.get_data` 후 boxed int를 `ldr w19,[x0]`로 꺼내고, `BaseData.get_id` 결과와 함께 `GetChapterBoxReward @ 00ddeea8`로 전달한다.

즉:

```text
UIData.data → boxed int 해제 → w19
Chapter(+0xd0).BaseData.id → chapterId
GetChapterBoxReward(chapterId, w19)
```

**boxIndex에 +1/-1 등의 별도 변환이 없다.**

### 31.2 Box UI index와 IsBoxReceived mask도 같은 index

`ChapBoxMono$$LayBoxItem @ 00e55c80`에서:

```text
00e55ebc  ldr w23,[x0]       ; UIData.data
00e56024  ldr x0,[x19,#0xd8] ; Chapter runtime object
00e56044  mov w8,#0x1
00e56048  lsl w1,w8,w23
00e56050  bl  0x015acfe8     ; ProtoChapter.IsBoxReceived
```

따라서 동일한 `UIData.data = i`가:

```text
수령 검사 → mask = 1 << i
클릭 요청 → boxIndex = i
```

양쪽에 그대로 사용된다.

실제 다른 계정 PCAP의 `boxIndex=5`는 정적 코드 기준 검사 mask `0x20`이 확정된다.

### 31.3 Chapter reward pair에 대한 추가 증거

`LayBoxItem`의 `List<KeyValuePair<int,int>>.get_Item @ 01ba5934` 반환값은 64비트 packed 값으로 취급된다.

```text
00e55ee4  mov x21,x0
00e55f24  lsr x1,x21,#0x20
00e55f2c  bl  0x01736d60   ; Ali.GetExcelData<object>
```

즉 pair의 **상위 32비트가 Excel data 조회 ID로 직접 사용**된다.

동일한 `get_Item`/`lsr #0x20` 패턴이 `RewardPanelMono$$ShowItem @ 0100e49c`에서도 확인된다. 따라서 Chapter reward pair는 최소한:

```text
high 32 = Excel Item ID 계열
low  32 = 수량/조건값 계열
```

로 좁혀진다. 다만 `SplitToInt32Dict @ 00df3f10` 본문을 직접 확보하기 전까지 threshold/rewardId의 key/value 방향은 최종 확정하지 않는다.

### 31.4 BoxStatus 해석 정리

현재 다음 3개는 모두 직접 확정된다.

```text
① request boxIndex = UIData.data
② IsBoxReceived mask = 1 << UIData.data
③ ProtoChapter +0x1C = BoxStatus
```

따라서 `boxIndex=5`의 최종 BoxStatus를 확인하려면 반드시 `0x20` bit를 확인해야 한다.

현재 0x14 response snapshot의 nested field4 값 `1` 또는 `3`은 `0x20`과 일치하지 않는다. 따라서 아직:

- response snapshot이 최종 수령 후 상태가 아닐 가능성
- field4가 BoxStatus가 아닐 가능성
- 후속 response에서 상태가 갱신될 가능성

을 모두 유지한다.

**현재 `protobuf field4 = BoxStatus`는 확정하지 않는다.**

### 31.5 다음 작업

1. 다른 계정 PCAP에서 0x14 이후 `Chapter 20000100` snapshot 검색
2. 후속 response의 Chapter 상태값 변화 확인
3. 다른 boxIndex의 0x14 요청이 있으면 `1 << index`와 response 상태 비교
4. 이후 `DataCenter.ProccessRequestRes @ 016e203c` Chapter merge 경로 재추적


## 32. 2026-09-30 실제 0x14 응답 재복호화 확인

추가 계정 PCAP blob을 직접 다시 읽어 `frame 285`를 DH64 복구 key로 AES-CBC 복호화했다.

```text
KCP frame 285
  flag = 0x84
  IV   = 945ec753adab00499a5cf5fd41f9cf42
  opcode = 0x14
```

복호화 protobuf top-level:

```text
field 1 = serial
field 2 = 0x14
field 4 = nested request/result data
field 6 = 20000100
field 7 = 1
field 43 = Chapter snapshot container
```

field43:

```text
field1 = 20000100
field2 = ProtoChapter-like nested message
```

nested Chapter:

```text
field1  = 20000100
field3  = 12
field4  = 3
field9  = { field1=1, field2=15 }
field10 = { field1=1, field2=15 }
field11 = 1
```

따라서 기존에 확인했던 `frame 285 / field43 / Chapter 20000100 / field4=3`은 단순 패킷 추측이 아니라 **실제 AES-CBC 복호화 결과**로 재확인됐다.

### 32.1 중요한 추가 확인

동일 PCAP의 후속 `frame 289`도 같은 key로 복호화했으며:

```text
opcode = 0x11
field6 = 10000001
field43 없음
```

이었다.

즉 frame 285의 Chapter snapshot이 frame 289에서 그대로 반복되는 구조는 아니다.

`frame 296`은 현재 동일 단일-fragment 복호화 방식으로 유효 protobuf가 나오지 않아, 별도 재검증 대상으로 남긴다.

### 32.2 현재 BoxStatus 판단

정적 분석은:

```text
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(i) = (BoxStatus & (1 << i)) != 0
```

를 확정한다.

실제 0x14 request는:

```text
chapterId = 20000100
boxIndex  = 5
```

이므로 기대되는 수령 bit는:

```text
1 << 5 = 0x20
```

하지만 0x14 response의 Chapter nested `field4=3`은 `0x20`이 아니다.

따라서 현재 증거로는 **protobuf field4를 BoxStatus라고 매핑하면 모순**이다.

현재 가장 중요한 다음 작업은 `DataCenter.ProccessRequestRes @ 016e203c`에서 `OpInfo.Chapters`가 실제 `ProtoChapter` 객체로 병합되는 지점을 찾고, `set_BoxStatus @ 015acf8c`에 도달하는 값을 확인하는 것이다.

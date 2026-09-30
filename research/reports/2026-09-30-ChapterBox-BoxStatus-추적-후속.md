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

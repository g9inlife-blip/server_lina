# 2026-09-30 [0930-3] ChapterBox / BoxStatus / 0x14 후속 분석

## 기준
- Git 기준 `research/*.md`, `research/reports/*.md`
- `Ghidra_Listing_txt` 함수명 검색은 실제 저장 규칙에 따라 `$$`, `<>` 등을 파일명에서 `_`로 치환
- `research/PCAP/*.json`은 PCAP 구조/패킷 대조 자료로 사용
- 확인되지 않은 값은 추측으로 확정하지 않음

## 1. 현재 0x14 Request는 재확정

```text
ClickGetReward @ 00e5705c
  ↓
GetChapterBoxReward(chapterId, boxIndex) @ 00ddeea8
  ↓
OpCode = 0x14
OpInfo +0x30 = chapterId
OpInfo +0x34 = boxIndex
  ↓
RequestOp
```

즉 서버에 Itembox rewardId 자체를 보내는 구조가 아니라 **Chapter ID + Box index**를 전달한다.

## 2. BoxStatus의 실제 의미 범위가 더 좁혀짐

Ghidra Listing:

```text
ProtoChapter.IsBoxReceived @ 015acfe8

ldr w8,[x0,#0x1c]
tst w8,w1
cset w0,ne
```

따라서:

```text
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(indexMask)
    → BoxStatus & mask
    → non-zero = received
```

이것은 BoxStatus가 단순한 단일 상태값이 아니라 **bit-mask 형태의 수령 상태**로 사용된다는 것을 직접 확정한다.

현재까지는 특정 box index가 정확히 어느 bit인지까지는 확정하지 않는다.

## 3. 중요한 구조적 결론

현재 경로는 다음처럼 분리된다.

```text
[정적 보상 정의]
ChapterRecord.m_chapterReward
    ↓
threshold * rewardId
    ↓
ItemboxRecord
    ↓
itemId / 실제 아이템

[실제 수령 상태]
ProtoChapter +0x1C
    ↓
BoxStatus bit mask
    ↓
IsBoxReceived(mask)

[수령 요청]
ClickGetReward
    ↓
GetChapterBoxReward(chapterId, boxIndex)
    ↓
opcode 0x14
```

따라서 **rewardId와 BoxStatus는 같은 값이 아니다.**
rewardId는 보상 정의 쪽이고, BoxStatus는 해당 Box 수령 상태를 표현한다.

## 4. 0x14 Response는 아직 직접 증명하지 않음

현재 저장소의 PCAP JSON 목록에서 확인되는 주요 자료는:

- 로그인/메인 진입
- 챕터 선택 → 전투 승리 보상
- 장비 조각 → 장비 제작/착용

이다.

현재 확인된 JSON 자료만으로는 **실제 Box 클릭 직후의 opcode 0x14 request/response 캡처가 별도 확보되어 있지 않다.**

따라서 현재 단계에서:

```text
0x14 response
    ↓
ProtoChapter.BoxStatus 갱신
```

을 사실로 확정하지 않는다.

## 5. 응답 처리 경계는 이미 확정

```text
TCP
 ↓
TCPTube.TryRead
 ↓
DecryptUnSafe
 ↓
DecompressUnSafe(if 0x40)
 ↓
ProtoBuf.Deserialize
 ↓
OpInfo
 ↓
NetworkCenter.TryHandleResponse @ 015b41e0
 ↓
DataCenter.ProccessRequestRes @ 016e203c
 ↓
Game State / callback
```

따라서 다음 정적 분석의 핵심은 암호가 아니라 **ProccessRequestRes에서 response object를 어떤 state object에 merge하는지**다.

## 6. 다음 분석 우선순위

### A. ClickGetReward 인자 생성
`00e5705c`에서:
- chapterId가 어디서 오는지
- boxIndex가 UIData.data에서 어떻게 만들어지는지
- index가 그대로 서버로 전달되는지

확인.

### B. BoxStatus bit mapping
`IsBoxReceived` 호출자의 두 번째 인자 생성부를 추적하여:

```text
boxIndex 0 → mask ?
boxIndex 1 → mask ?
boxIndex 2 → mask ?
...
```

를 확정.

### C. 0x14 response state merge
`DataCenter.ProccessRequestRes @ 016e203c`의 본문이 저장소에 없는 현재 상태에서는:
- Calls IN/OUT
- 관련 Merge 함수
- ProtoChapter/Chapter 관련 함수
- response object 타입

을 교차 추적한다.

### D. 실제 Box PCAP 확보 후 검증
Box 하나를 실제로 열기 전/후 상태가 포함된 PCAP JSON이 추가되면:

```text
0x14 request
  chapterId
  boxIndex
        ↓
0x14 response
        ↓
ProtoChapter
  BoxStatus
        ↓
box bit 변화
```

를 직접 대조한다.

## 7. 현재 확정/미확정

| 항목 | 상태 |
|---|---|
| GetChapterBoxReward opcode | CONFIRMED 0x14 |
| request chapterId | CONFIRMED |
| request boxIndex | CONFIRMED |
| ProtoChapter.BoxStatus offset | CONFIRMED +0x1C |
| IsBoxReceived가 bit-mask 검사 | CONFIRMED |
| rewardId와 BoxStatus 동일 | REJECTED |
| boxIndex → bit mask | UNKNOWN |
| 0x14 response → BoxStatus 갱신 | UNKNOWN |
| 0x14 실제 PCAP | 현재 자료 없음 |

## 결론

**0930-3 단계에서는 BoxStatus의 핵심 표현 방식까지 확정했다.**

특히:

```text
BoxStatus = ProtoChapter +0x1C
IsBoxReceived = (BoxStatus & mask) != 0
```

가 Ghidra assembly로 직접 확인됐다.

이제 가장 가치 있는 작업은 **0x14 response를 억지로 추정하는 것이 아니라, 실제 Box 클릭 PCAP을 확보하거나 ProccessRequestRes/merge 경로에서 해당 response의 state 반영점을 찾는 것**이다.

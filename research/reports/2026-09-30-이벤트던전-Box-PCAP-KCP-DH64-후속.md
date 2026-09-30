# 2026-09-30 이벤트던전 Box PCAP / KCP DH64 후속 분석

## 기준
- Git 기준 `research/*.md`, `research/reports/*.md`
- `Ghidra_Listing_txt` 함수명은 앞 2글자 기준이며 `< > $` 등은 `_` 치환
- 대상 신규 PCAP JSON: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화.json`
- 확인되지 않은 opcode/상태는 추측으로 확정하지 않음

## 1. 신규 통합 PCAP 확인
신규 JSON은 총 **479 packet**이며 로그인부터 여러 게임 행동을 하나의 세션 흐름으로 포함한다.

사용자 행동 순서:
```
로그인 → 출석 → 퀘스트/업적 → 우편 → 토벌 → 던전
→ 승리/보상 → 던전 업적 → Box 보상 → 무기 제작 → 강화
```

## 2. KCP DH64 / session key 확정
Game Server UDP:
```
10.215.173.1:40193 ↔ 182.92.62.79:8000
```

이번 세션:
```
client private #1 = 0x20A728990271B002
client private #2 = 0x237FCE167BB3CC9F
secret1 = 0xFE15868045F4F544
secret2 = 0x3F3287258010223F
KCP key = 44f5f445808615fe1b2e224c5e05e718
```

frame 189 실제 application 복호화 성공으로 전체 경로가 검증되었다.

## 3. 0x14 Box request/response 확정

### frame 428 — C→S
```
opcode = 0x14
chapterId = 20,000,100
boxIndex = 5
```

정적 분석의 `GetChapterBoxReward @ 00ddeea8` 계약과 일치한다.

### frame 430 — S→C
```
flag = 0x84
application bytes = 353
plaintext = 329 bytes
opcode(field #2) = 0x14
```

## 4. analyzer 수정
frame 430 누락 원인은 KCP 재조립이 아니라 암호화 flag 목록에서 `0x84`가 빠져 있었던 것이다.

수정:
```
ENC_FLAGS = {0x80, 0x84, 0xC0, 0xC4}
```

수정 commit:
```
076e991f0513b9ace469553a1c87f13b3b6a688d
```

현재 Git에는 수정 후 생성된:
```
plaintext/000430_s2c.bin
```
이 존재하며 **실제 329-byte plaintext가 확인되었다.**

## 5. frame 430 ProtoChapter 구조 확인

frame 430의 핵심 nested 구조:

```
field 43
 └─ length 30
    ├─ field 1 = 20,000,100
    ├─ field 3 = 6
    ├─ field 4 = 1
    ├─ field 9 = { field1=1, field2=15 }
    ├─ field10 = { field1=1, field2=15 }
    └─ field11 = 1
```

특히 field 43 내부의 **field 1 = 20,000,100**은 요청 chapterId와 정확히 일치한다.

Ghidra에서 확인된 `ProtoChapter` 메모리 필드:
```
+0x10 = Id
+0x14 = Status
+0x18 = Progress
+0x1C = BoxStatus
```

이에 따라 protobuf의 연속적인 Chapter 핵심 필드가:
```
protobuf field 1 → Id
protobuf field 2 → Status
protobuf field 3 → Progress
protobuf field 4 → BoxStatus
```
로 대응하는 것이 **frame 430에서 직접 관측된 값과 일치한다.**

따라서 이번 frame 430에서는:

```
ProtoChapter.Id        = 20,000,100
ProtoChapter.Progress  = 6
ProtoChapter.BoxStatus = 1
```

로 해석할 근거가 확보되었다.

**중요:** field 4 → BoxStatus는 단순 이름 추측이 아니라, Ghidra의 필드 순서/offset과 frame 430의 Chapter 구조가 동시에 일치한 결과다. 다만 protobuf serializer/deserializer 함수 자체에서 field 번호를 직접 확인하면 최종 확정이 된다.

## 6. BoxStatus 의미
```
IsBoxReceived(mask)
= (BoxStatus & mask) != 0
```

현재 frame 430:
```
BoxStatus = 1
```

요청은:
```
boxIndex = 5
```

이므로 **BoxStatus=1이 boxIndex 5의 수령 완료를 직접 의미한다고 아직 해석하면 안 된다.**

현재 확인된 것은:
- opcode 0x14 요청에서 boxIndex=5가 서버로 전달됨
- 같은 response의 chapterId=20,000,100 Chapter snapshot에 BoxStatus 후보값 1이 존재
- 실제 BoxStatus는 bit mask이므로 boxIndex와 bit 위치의 매핑을 추가 확인해야 함

## 7. 다음 추적 포인트

다음은 frame 430 자체보다 **0x14 이전/이후의 동일 chapter snapshot 비교**가 중요하다.

확인 순서:
```
1. chapterId=20,000,100인 field 43 검색
2. BoxStatus 후보(field 4)의 이전 값 확인
3. frame 428 boxIndex=5 요청
4. frame 430 response의 field 4=1 확인
5. boxIndex 5 ↔ BoxStatus bit 매핑 확인
6. ProtoChapter protobuf serializer/deserializer에서 field 번호 직접 확인
```

현재 가장 중요한 확정 경로:
```
frame 428
→ opcode 0x14
→ chapterId 20,000,100
→ boxIndex 5
→ server response frame 430
→ field 43 Chapter snapshot
→ Id=20,000,100
→ Progress=6
→ BoxStatus 후보/매핑 field=4
→ 값=1
```


## 8. 2026-09-30 chapterId=20000100 상태 변화 추적

### 8.1 이전 동일 Chapter 응답
통합 PCAP에서 동일 `chapterId=20000100`은 먼저 frame 340/341의 0x13 요청과 frame 343/346의 0x13 응답에 등장한다. frame 343/346에는 `field 6 = 20000100` 및 `field 44` 계열 데이터가 있지만, frame 430에서 확인된 `field 43` Chapter snapshot은 확인되지 않는다.

### 8.2 Box 요청 직전/직후
```text
frame 428 C→S
  opcode = 0x14
  chapterId = 20000100
  boxIndex = 5

frame 430 S→C
  opcode = 0x14
  chapterId = 20000100
  field 43 = Chapter snapshot
```

frame 430:
```text
field 1 = 20000100
field 3 = 6
field 4 = 1
field 9 = {1,15}
field10 = {1,15}
field11 = 1
```

따라서 0x14 요청 직후 Chapter state가 response에 포함되는 것은 확인된다.

### 8.3 BoxStatus 0→1 변화는 미증명
현재 PCAP에는 0x14 요청 직전의 동일 Chapter snapshot이 없으므로 `이전 BoxStatus=0 → boxIndex 5 수령 → 이후 BoxStatus=1`의 시간적 변화는 직접 증명되지 않는다.

정적 분석에서 확정된 것은:
```text
IsBoxReceived(mask) = (BoxStatus & mask) != 0
```
뿐이다. 따라서 boxIndex 5의 실제 mask가 1인지도 아직 확정하지 않는다.

### 8.4 현재 가장 강한 연결
```text
0x14 request
 ├─ chapterId = 20000100
 └─ boxIndex  = 5
        ↓
0x14 response
 └─ Chapter snapshot
     ├─ Id = 20000100
     ├─ Progress = 6
     └─ field 4 = 1  ← BoxStatus 후보
```

Ghidra의 `ProtoChapter +0x10=Id`, `+0x14=Status`, `+0x18=Progress`, `+0x1C=BoxStatus`와 대응한다. 다만 protobuf serializer/deserializer에서 field 번호를 직접 확인하기 전까지 field 4의 최종 매핑과 bit 의미는 보수적으로 유지한다.

### 8.5 다음 추적
1. 다른 PCAP에서 `chapterId=20000100` Chapter snapshot 검색
2. Box 수령 전/후 field 4 비교
3. `IsBoxReceived(mask)` 호출부에서 실제 mask 확보
4. ProtoChapter serializer/deserializer에서 field 번호 직접 확인

현재 결론:
```text
chapterId=20000100 동일성       확정
0x14 request ↔ chapterId       확정
0x14 response ↔ Chapter state 확정
ProtoChapter +0x1C=BoxStatus   확정
BoxStatus bitmask              확정
BoxStatus 0→1 변화             미확정
boxIndex 5 ↔ mask 1            미확정
```

## 9. IsBoxReceived 실제 mask 생성 코드 확보

이번 단계에서 호출부 Listing을 직접 확보했다.

### 9.1 ChapBoxMono.LayBoxItem @ 00e55c80

Box UI의 실제 index 값은 `w23`이며, `ProtoChapter.IsBoxReceived` 직전에:

```text
00e56024  ldr x0,[x19,#0xd8]
00e56044  mov w8,#0x1
00e56048  lsl w1,w8,w23
00e56050  bl  0x015acfe8
```

즉:

```text
mask = 1 << boxIndex
IsBoxReceived(chapter, mask)
```

### 9.2 BattleSectionMono.SetStageBoxAndBar @ 00e53380

Section Box도 동일한 방식이다. `w23`을 0부터 증가시키며:

```text
00e5356c  mov w21,w0
00e53570  lsl w1,w26,w23
00e53574  mov x0,x8
00e5357c  bl  0x015acfe8
...
00e53870  add x23,x23,#0x1
00e53874  cmp w23,#0x3
```

여기서 `w26=1`이므로 역시 `mask = 1 << index`이다.

### 9.3 중요한 PCAP 대조 결과

기존 PCAP의 frame 428 요청은:

```text
opcode = 0x14
chapterId = 20000100
boxIndex = 5
```

따라서 UI/정적 코드 기준으로 해당 Box의 상태 검사 mask는:

```text
1 << 5 = 0x20
```

그런데 frame 430의 Chapter snapshot은 현재 파서 기준으로:

```text
field 1 = 20000100
field 3 = 6
field 4 = 1
```

이다.

따라서 **field 4를 BoxStatus=1로 단정하면 boxIndex=5의 mask 0x20과 충돌한다.** 이 결과로 기존의 `field 4 = BoxStatus` 해석은 보류한다.

현재 더 안전한 결론은:

- `ProtoChapter +0x1C = BoxStatus`는 확정
- `IsBoxReceived(mask) = BoxStatus & mask != 0`는 확정
- Box UI index `i`의 검사 mask는 `1 << i`로 확정
- frame 428의 `boxIndex=5`라면 검사 mask는 `0x20`
- frame 430의 nested `field 4=1`은 **BoxStatus라고 아직 확정할 수 없음**

### 9.4 다음 추적

1. `ProtoChapter` protobuf field 번호를 serializer/deserializer에서 직접 확보
2. frame 430 nested field 3/4의 실제 의미 확정
3. frame 428의 boxIndex가 UI index와 동일한지 `GetChapterBoxReward @ 00ddeea8` 호출 인자까지 재검증
4. `DataCenter.ProccessRequestRes @ 016e203c`의 0x14 응답 merge 경로 확보

## 10. 다른 계정 PCAP 교차 기준 추가

사용자가 추가한 다른 계정 PCAP:
```
research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json
blob SHA = faeb47f64d76158c731c36abb741773e376e46a2
```

Git에서 실제 파일 존재를 확인했다. 파일은 대용량이라 일반 `fetch_file` 내용 반환은 비어 있지만 blob 직접 조회로 **306 packet**을 확인했다.

### 10.1 KCP 세션 구조

Game Server KCP:
```
client 51943 ↔ server 8000
KCP data packet = 76개
conv = 0xc6... 계열
```

초기 DH/KCP handshake:
```
frame 143 C→S
  8-byte zero prefix
  client public #1 = a60ff368acdf81d8 (LE)
  client public #2 = eec24eecff6ac73b (LE)
  이후 handshake parameter

frame 147 S→C
  8-byte zero prefix
  marker = 01
  offset 17 public #1 = cb43ff46bca8d1d4 (LE)
  offset 25 public #2 = a859cef72e5fcca8 (LE)
```

여기서 server response의 marker 직후 첫 8바이트는 DH peer public으로 사용되지 않는다. Ghidra `KCPTube.Handshake2 @ 015b1f68`가 실제로:
```
BitConverter.ToUInt64(buffer, 0x11)
BitConverter.ToUInt64(buffer, 0x19)
```
를 수행하므로 실제 peer public은 **offset 17/25**이다.

### 10.2 새 계정 DH 계산

동일한 `p=2^64-59`, `g=5`를 적용하면 client private residue는:
```
private #1 = 0x1021bdff42518bc9
private #2 = 0x1711d8ad4dc70e26
```

server peer public에 대한 shared secret 후보:
```
secret #1 = 0x6cdbdcad6a7846d7
secret #2 = 0xcf8fdf34709590da
candidate KCP key = d746786aaddcdb6cda90957034df8fcf
```

이 값은 정적 코드의 Handshake2 흐름과 계산상 일치하지만, **현재 PCAP application ciphertext에 대한 실제 복호화 성공은 아직 확인하지 않았다.** 따라서 이 단계에서는 candidate key로만 기록한다.

### 10.3 다른 계정 PCAP의 분석 가치

파일명 기준으로 이 PCAP은:
```
로그인 → 던전 2회 → Box 오픈 → 이후 장비 착용
```
순서가 포함된 별도 계정 캡처다.

따라서 계정별 chapter/아이템 값 자체를 동일하다고 보면 안 되지만, 다음 프로토콜 상관관계 검증에는 유용하다.

1. Box 오픈 직전/직후의 `0x14` request/response 위치
2. Box 오픈 뒤 장비 관련 request/response opcode
3. Box 수령 후 Chapter snapshot의 상태 필드 변화
4. 기존 계정의 `boxIndex=5` 사례와 다른 Box index의 mask 비교

### 10.4 현재 상태

```
ProtoChapter +0x1C = BoxStatus       확정
IsBoxReceived(mask)                 확정
mask = 1 << boxIndex                확정
기존 boxIndex=5 → mask=0x20         확정
frame430 field4=1 = BoxStatus       보류
다른 계정 PCAP 존재                 확정
다른 계정 KCP candidate key         계산 완료
다른 계정 KCP plaintext             미확인
```

다음은 새 PCAP의 KCP 복호화 성공 여부를 먼저 해결한 뒤, Box 오픈 전후의 동일 Chapter snapshot을 비교하는 것으로 진행한다.

# 2026-10-02 Bootstrap OpCode=2 응답 / KCP Fragment 재분석_GPT자문

## 1. 결론

221B 이후 28B 분석은 완료됐다.

- 221B: Client → Server KCP DATA + Application
- 28B: Server → Client KCP ACK
- Bootstrap OpCode=2 응답: KCP DATA이며 실제 PCAP에서는 단일 UDP packet이 아니라 KCP fragment로 전송되는 대형 응답이 관측된다.

현재 필요한 계층은:

```
KCP DATA 수신
→ KCP ACK
→ KCP fragment 처리/재조립
→ Application decrypt
→ protobuf deserialize
→ OpCode=2 dispatch
→ Bootstrap OpInfo 생성
→ KCP fragment 송신
```

## 2. 실제 PCAP의 Bootstrap 후보 fragment

Git의 `research/PCAP/게임시작로그인메인화면까지.json`에서 동일 Session `a68a593a85bc5439`의 서버 DATA가 확인된다.

frame 180~188:

```
180 → frg=8, SN=0
181 → frg=7, SN=1
182 → frg=6, SN=2
183 → frg=5, SN=3
184 → frg=4, SN=4
185 → frg=3, SN=5
186 → frg=2, SN=6
187 → frg=1, SN=7
188 → frg=0, SN=8
```

즉 `frg=8 → 0`은 하나의 KCP message를 구성한다.

KCP header 뒤 데이터 크기는 frame 180~187이 1372B, frame 188이 417B이므로 총 payload 규모는:

```
1372 × 8 + 417 = 11,393B
```

이다.

## 3. 재전송도 별도로 확인됨

frame 191~197에서 SN=2..8 / frg=6..0이 다시 관측되며 앞선 fragment와 payload가 동일하다.

따라서 이는 새 Application response가 아니라 KCP retransmission으로 보는 것이 타당하다.

Local Server는 동일 SN의 중복 fragment를 Application layer에 두 번 전달하면 안 된다.

## 4. frame 203은 앞의 Bootstrap message와 분리

frame 203은:

```
CMD = 0x51
frg = 0
SN = 9
Application length = 209
Flag = 0x84
IV = 16B
Ciphertext = 192B
```

형태다.

따라서 SN=0~8의 `frg=8→0` message와 SN=9를 하나의 protobuf로 합치면 안 된다. frame 203은 다음 KCP DATA message로 분리해서 처리해야 한다.

## 5. Bootstrap Response의 Runtime 계약은 이미 확인됨

기존 runtime 분석에서:

```
KCPTube.Send
  request = OpInfo
  SerialNumber = 66149422
  OpCode = 2
        ↓
KCPTube.TryRead
        ↓
NetworkCenter.TryHandleResponse
        ↓
DataCenter.ProccessRequestRes
        ↓
response = OpInfo
```

가 확인됐다.

Response OpInfo에는 실제로 다음 계열이 존재한다.

```
User
Heros
Items
Weapons
Equiments
Mails
Olds
Chapters
Sections
Teams
ViewItems
Fashions
Quests
Shops
Charges
Friends
Exam
Rival
Ranks
Activities
...
```

특히:

```
+0x88 User
+0x90 Heros
+0x98 Items
+0xA0 Weapons
+0xA8 Equiments
+0xC0 Chapters
```

가 확인됐다.

Chapters는 61개이며 대표적으로:

```
20000000 → BoxStatus=7
20000100 → BoxStatus=1
```

이 관측됐다.

## 6. 현재 서버 코드의 핵심 공백

현재 `app/kcp/server_udp.py`는 221B를 직접 처리하는 단계까지 구현돼 있지만 다음은 완성되어 있지 않다.

- 28B KCP ACK 송신
- KCP SN/UNA state
- FRG 기반 reassembly
- duplicate/retransmission 처리
- OpCode=2 response builder
- response AES encryption
- response KCP fragmentation

따라서 **Bootstrap protobuf를 먼저 추측해서 구현하는 것보다 KCP transport 상태 처리를 먼저 완성하는 것이 맞다.**

## 7. 구현 순서 판단

### A. KCP RX state

Session별로 최소:

```
SN
UNA
FRG
received fragment cache
duplicate detection
```

을 유지한다.

### B. ACK

수신 DATA SN=N에 대해 관측된 계약상:

```
CMD=0x52
ACK SN=N
UNA=N+1
```

관계를 유지한다.

Window, timestamp, trailing field의 의미는 아직 상수로 확정하지 않는다.

### C. Fragment reassembly

```
frg=N ... 0
```

을 완성해야 Application layer로 넘긴다.

### D. Application decode

재조립된 Application payload에 대해서만:

```
Length
Flag
IV
Ciphertext
↓
AES
↓
protobuf
```

를 수행한다.

### E. Bootstrap

```
OpCode=2
→ SerialNumber correlation
→ OpInfo 최소 상태
```

로 처리한다.

### F. TX fragmentation

응답 Application payload가 커지면:

```
Application payload
→ KCP fragment 분할
→ SN 증가
→ frg 설정
→ UDP send
```

가 필요하다.

## 8. Bootstrap 최소 계약의 현재 증거 등급

| 항목 | 상태 |
|---|---|
| SerialNumber request/response correlation | CONFIRMED |
| OpCode=2 | CONFIRMED |
| ReturnCode=0 | CONFIRMED |
| User 존재 | CONFIRMED |
| Items 존재 | CONFIRMED |
| Heros 존재 | CONFIRMED |
| Weapons 존재 | CONFIRMED |
| Equiments 존재 | CONFIRMED |
| Chapters 존재 | CONFIRMED |
| Sections 존재 | CONFIRMED |
| Teams 존재 | CONFIRMED |
| 기타 OpInfo field | 존재는 CONFIRMED, Main 필수 여부 UNKNOWN |

여기서 CONFIRMED는 실제 Response에 존재한다는 뜻이지 전부 Main 진입 필수라는 뜻은 아니다.

## 9. 이번 단계에서 확정하지 않는 것

- frame 203을 Bootstrap 전체 response로 규정하지 않는다.
- 11,393B 전체를 protobuf라고 단정하지 않는다.
- OpInfo 모든 field를 Main 필수로 취급하지 않는다.
- protobuf field 번호를 임의 생성하지 않는다.
- KCP window/timestamp를 상수로 고정하지 않는다.
- retransmission fragment를 새 response로 처리하지 않는다.

## 10. 최종 판단

현재 흐름은 다음으로 정리된다.

```
221B Client→Server
    ↓
KCP DATA SN=0
    ↓
28B Server→Client
KCP ACK UNA=1
    ↓
Server Bootstrap response
KCP DATA fragments
SN=0..8
frg=8..0
    ↓
KCP reassembly
    ↓
Application decrypt
    ↓
OpCode=2 / OpInfo
    ↓
User / Items / Heros / Chapters ...
    ↓
Main screen
```

따라서 현재 Local Server에서 가장 먼저 해결할 것은 **Bootstrap protobuf를 추측하는 것이 아니라 KCP ACK + fragmentation/reassembly를 실제 PCAP 계약에 맞게 구현하는 것**이다.

Bootstrap OpInfo의 runtime 구조는 이미 상당 부분 확보되어 있으므로 transport 계층이 정상화된 다음 최소 Response 필드를 좁히는 것이 안전하다.

## 관련 문서

- `2026-10-02-221B-복호화-메시지-구조-분석_lina.md`
- `2026-10-02-221B-이후-28B-KCP-ACK-구조-분석_GPT자문.md`
- `2026-10-02-KCP-221B-RAW-DH-키-매핑-검증_GPT자문.md`
- `2026-10-01-메인화면-응답-Chapter-런타임추적-후속_GPT자문.md`

# 2026-10-02 Bootstrap OpCode=2 응답 계약 검증_GPT자문

## 1. 이번 자문의 기준

현재 Local Server는 KCP transport 자체는 정상적으로 동작하는 단계까지 진행됐다.

실기기에서 확인된 최신 상태:

```
Client 221B
→ Server KCP DATA 수신
→ Server 28B ACK
→ Server KCP DATA SN=0 FRG=0 전송
→ Client의 Login request retransmission 중단
```

그러나 Client UI는 Login 화면에 그대로 남고 Loading bar가 나타나지 않는다.

따라서 현재 문제는 **KCP packet delivery 자체보다 Bootstrap OpCode=2 Response의 Application 계약이 부족한 것**으로 보는 것이 가장 합리적이다.

---

## 2. 현재까지 확정된 Bootstrap 요청

Client가 보내는 최초 Bootstrap 요청은 runtime에서 다음과 같이 확인됐다.

```
KCPTube.Send
    request = OpInfo
    SerialNumber = <session별 값>
    OpCode = 2
    ReturnCode = 0
        ↓
KCPTube.TryRead
        ↓
NetworkCenter.TryHandleResponse
        ↓
DataCenter.ProccessRequestRes
        ↓
response = OpInfo
```

현재 실기기 요청 예:

```
field 1 = SerialNumber
field 2 = 2
field 4 = bytes
field 5 = device model
field 12 = device identifier
field 13 = client identifier
field 14 = Handheld
field 15 = Android OS / API 정보
```

즉 현재 Local Server가 221B를 복호화하고 `field 1/2`를 읽는 것까지는 올바른 방향이다.

---

## 3. 현재 Probe Response의 한계

현재 Local Server는 테스트 목적으로 다음과 같은 응답을 보내고 있다.

```
field 1 = request SerialNumber
field 2 = 2
```

즉 의미상:

```
OpInfo
    SerialNumber = request.SerialNumber
    OpCode       = 2
```

정도의 최소 protobuf만 전달한다.

이 응답은 다음 목적에는 성공했다.

- AES/KCP 송신 경로 검증
- KCP SN=0 송신 검증
- Client의 request retransmission 중단 확인

그러나 이것만으로 실제 Bootstrap Response가 완성됐다고 볼 수 없다.

runtime에서 실제 Response가 `DataCenter.ProccessRequestRes`로 들어간 뒤 Client가 사용하는 객체는 단순한 OpCode/SerialNumber 객체가 아니라 **상태 데이터가 포함된 OpInfo**다.

따라서 현재 Probe는 transport probe로는 유효하지만 실제 Login→Main Bootstrap response로는 불충분하다.

---

## 4. 실제 Bootstrap Response에서 확인된 OpInfo 상태

기존 runtime 분석에서 실제 OpCode=2 Response의 OpInfo에는 다음 계열이 non-null로 관측됐다.

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

확인된 주요 내부 offset:

```
OpInfo +0x88 = User
OpInfo +0x90 = Heros
OpInfo +0x98 = Items
OpInfo +0xA0 = Weapons
OpInfo +0xA8 = Equiments
OpInfo +0xC0 = Chapters
OpInfo +0xC8 = Sections
OpInfo +0xD0 = Teams
OpInfo +0xE0 = Fashions
OpInfo +0xE8 = Quests
OpInfo +0xF8 = Charges
OpInfo +0x120 = Activities
```

중요한 점은 이 offset이 protobuf field 번호를 의미하는 것이 아니라 **Client가 deserialize한 C# 객체의 메모리 offset**이라는 것이다.

따라서 서버 protobuf field 번호를 이 offset과 직접 동일시해서는 안 된다.

---

## 5. Main 진입에 필요한 최소 Response를 찾아야 한다

전체 OpInfo를 그대로 복제하는 것은 현재 목표가 아니다.

목표는:

```
OpCode=2 Response
    ↓
Deserialize
    ↓
DataCenter.ProccessRequestRes
    ↓
필수 State 초기화
    ↓
Main 화면 진입
```

을 만족하는 최소 필드를 찾는 것이다.

현재 우선순위는 다음과 같다.

### 1순위

```
SerialNumber
OpCode
ReturnCode
```

Response correlation 및 성공 상태.

### 2순위

```
User
```

계정/플레이어 기본 상태.

### 3순위

```
Items
Heros
Weapons
Equiments
```

Bootstrap 이후 DataCenter cache에 병합되는 핵심 게임 상태.

### 4순위

```
Chapters
Sections
Teams
```

Main/진행 상태 및 Chapter UI와 직접 연결되는 상태.

그 외 필드는 실제 Main 진입을 막는 것이 확인되기 전까지 선택 상태로 둔다.

---

## 6. Chapters는 현재 별도 중요도가 높다

runtime에서:

```
OpInfo +0xC0
    ↓
Chapters Dictionary
    ↓
ProtoChapter
```

가 확인됐다.

대표 Chapter:

```
20000000 → BoxStatus = 7
20000100 → BoxStatus = 1
```

ProtoChapter 구조:

```
+0x10 = Id
+0x14 = Status
+0x18 = Progress
+0x1C = BoxStatus
```

BoxStatus는 bitmask 방식으로 확인됐다.

```
IsBoxReceived(mask)
    = (BoxStatus & mask) != 0

mask = 1 << boxIndex
```

따라서 BoxStatus 자체는 현재 분석에서 확정 상태로 취급한다.

다만 이것을 protobuf field 번호로 직접 변환하는 것은 별도의 문제다.

---

## 7. 창고 데이터와 Bootstrap의 연결

현재 Ghidra 분석으로 다음 경로가 연결됐다.

```
Bootstrap OpInfo.Items
        ↓
DataCenter.ProccessRequestRes
        ↓
DataCenter.MergeItem
        ↓
DataCenter +0x78 category cache
        ↓
WareHousePanelMono.InitData
        ↓
필터 / 정렬
        ↓
List
        ↓
ShowGoods
        ↓
LoopScrollRect
        ↓
창고 Item UI
```

따라서 창고 기본 목록은 Bootstrap Response의 Items가 정상적으로 들어오지 않으면 만들어질 수 없다.

이 점에서 현재 Login 화면에 머무는 현상은 창고 요청 문제보다 먼저 **Bootstrap OpInfo 자체가 불완전한 문제**일 가능성이 높다.

---

## 8. 현재 KCP Probe 결과의 정확한 해석

실기기 로그:

```
221B 수신
    ↓
ACK SN=0 UNA=1
    ↓
Bootstrap probe 응답 전송
    ↓
KCP DATA SN=0 FRG=0
    ↓
Client retransmission 중단
```

이 결과로 확정할 수 있는 것은:

- Server가 Client의 221B를 정상 수신했다.
- KCP header parsing이 동작한다.
- Server가 ACK를 올바른 형식으로 반환하고 있다.
- Server→Client KCP DATA가 Client까지 전달되고 있다.
- 최소한 Client가 해당 송신을 transport 측에서 처리했다.

그러나 다음은 아직 확정할 수 없다.

- Probe가 정상적인 Bootstrap OpInfo로 deserialize됐는가
- Client가 Bootstrap 성공 상태로 전환했는가
- Main scene 전환 조건을 만족했는가
- User/Items/Chapters 등의 필수 상태가 생성됐는가

따라서 **'KCP는 된다'와 'Bootstrap이 성공했다'를 분리해서 판단해야 한다.**

---

## 9. 다음 분석에서 가장 중요한 비교 대상

가장 가치가 높은 자료는 운영 PCAP의 실제 Bootstrap Response다.

기존 분석에서 동일 Session의 Server→Client KCP DATA가 다음과 같이 확인됐다.

```
SN=0 FRG=8
SN=1 FRG=7
SN=2 FRG=6
SN=3 FRG=5
SN=4 FRG=4
SN=5 FRG=3
SN=6 FRG=2
SN=7 FRG=1
SN=8 FRG=0
```

총 payload:

```
1372 × 8 + 417 = 11,393 bytes
```

따라서 이 9개 fragment를 하나의 KCP message로 재조립한 후 Application layer를 해석해야 한다.

SN=9 / FRG=0의 frame 203은 별도의 다음 KCP message이므로 Bootstrap response와 합치지 않는다.

---

## 10. 실제 Bootstrap Response 분석 순서

운영 PCAP에서 다음 순서로 분석하는 것이 안전하다.

```
KCP SN=0..8
    ↓
FRG=8..0 순서 검증
    ↓
payload 연결
    ↓
Application Length 확인
    ↓
Flag 확인
    ↓
IV 추출
    ↓
AES decrypt
    ↓
protobuf 전체 bytes 확보
    ↓
field tree 생성
```

그 후 runtime OpInfo와 비교한다.

비교 항목:

```
protobuf field
    ↔
Deserialize 결과 OpInfo member
    ↔
DataCenter.ProccessRequestRes 처리
    ↔
실제 Main 진입 동작
```

이 네 계층을 연결해야 한다.

---

## 11. 현재 서버에서 추가로 확인해야 할 부분

현재 `server_udp.py`의 Bootstrap handler는 실제 OpInfo builder가 아니라 Probe builder다.

현재 형태:

```
if opcode == 2:
    probe = field1(serial) + field2(2)
    send_kcp_message(...)
```

이 부분을 바로 거대한 OpInfo protobuf로 교체하는 것은 권장하지 않는다.

먼저 실제 운영 Response의 field tree를 확보해야 한다.

그 이유는:

1. protobuf field 번호를 추측하면 잘못된 객체가 만들어질 수 있다.
2. repeated message의 nested schema가 필요하다.
3. User/Items/Heros/Chapters의 내부 message 구조가 필요하다.
4. DataCenter.Merge 계열이 실제로 요구하는 값이 있다.
5. 일부 field는 null/empty와 존재 상태가 서로 다른 의미를 가질 수 있다.

따라서 지금은 Probe를 유지한 채 실제 Response contract를 확보하는 편이 안전하다.

---

## 12. Local Server 구현 우선순위

현재 기준 권장 순서:

```
[완료]
DH/session key
    ↓
[완료]
221B decrypt
    ↓
[완료]
KCP ACK
    ↓
[완료]
KCP TX
    ↓
[완료/검증 중]
KCP fragment 처리
    ↓
[현재 핵심]
실제 Bootstrap Response protobuf
    ↓
OpInfo 최소 상태
    ↓
Client Main 진입
    ↓
0x14 Box
    ↓
기타 gameplay operation
```

특히 현재는 0x14 Box보다 Bootstrap을 먼저 정상화해야 한다.

Bootstrap에서 Items/Chapters가 만들어져야 이후 창고 및 Box 상태 분석 결과도 실제 Client 화면과 연결할 수 있기 때문이다.

---

## 13. 현재 증거 등급

| 항목 | 상태 |
|---|---|
| 221B = KCP DATA + Application | CONFIRMED |
| 28B = KCP ACK | CONFIRMED |
| Bootstrap request OpCode=2 | CONFIRMED |
| SerialNumber request/response correlation | CONFIRMED |
| 실제 Response type = OpInfo | CONFIRMED |
| User 존재 | CONFIRMED |
| Items 존재 | CONFIRMED |
| Heros 존재 | CONFIRMED |
| Weapons 존재 | CONFIRMED |
| Equiments 존재 | CONFIRMED |
| Chapters 존재 | CONFIRMED |
| Sections 존재 | CONFIRMED |
| BoxStatus 구조 | CONFIRMED |
| Probe만으로 Main 진입 가능 | NOT CONFIRMED |
| 전체 OpInfo field의 Main 필수성 | UNKNOWN |
| 실제 protobuf field 번호 | 추가 분석 필요 |
| 실제 Bootstrap 최소 필드 집합 | 추가 분석 필요 |

---

## 14. 결론

현재 Local Server는 **KCP transport 검증 단계는 넘어섰지만 실제 Bootstrap Application Response 계약은 아직 구현되지 않은 상태**다.

특히:

```
KCP DATA SN=0 전송
→ Client retransmission 중단
→ Login 화면 유지
```

라는 결과는 Probe가 transport 검증에는 성공했지만 실제 Bootstrap state 초기화에는 충분하지 않다는 방향을 강하게 보여준다.

다음 핵심 작업은 Ghidra에서 더 많은 UI 함수를 무작정 찾는 것이 아니라:

```
운영 PCAP
    ↓
Bootstrap SN=0..8 재조립
    ↓
실제 Response decrypt
    ↓
protobuf field tree
    ↓
OpInfo runtime member와 대조
    ↓
DataCenter.ProccessRequestRes 처리 필드 확인
    ↓
Main 진입 최소 Response 확정
```

으로 진행하는 것이다.

이 작업이 완료되면 현재의 임시 Probe Response를 실제 Bootstrap Response builder로 교체할 수 있다.

## 관련 문서

- `2026-10-02-Bootstrap-OpCode2-KCP-Fragment-후속_GPT자문.md`
- `2026-10-02-운영PCAP-서버요청응답-계약분석_GPT자문.md`
- `2026-10-01-메인화면-응답-Chapter-런타임추적-후속_GPT자문.md`
- `2026-10-02-221B-복호화-메시지-구조-분석_lina.md`
- `2026-10-02-221B-이후-28B-KCP-ACK-구조-분석_GPT자문.md`

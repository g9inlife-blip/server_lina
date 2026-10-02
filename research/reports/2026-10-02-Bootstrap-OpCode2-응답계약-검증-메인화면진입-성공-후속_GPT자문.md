# 2026-10-02 Bootstrap OpCode=2 응답계약 검증 - 메인화면 진입 성공 후속_GPT자문

## 1. 이번 문서의 목적

2026-10-02 `091aeea3` 커밋에서 **Local Server가 운영 KCP 데이터를 복제하여 실제 클라이언트의 메인화면까지 진입하는 1차 마일스톤을 달성**했다.

기존 문서에서는 Bootstrap OpCode=2 응답 계약이 미완성인 상태를 기준으로 분석했으나, 이번 실험으로 그 핵심 블로커가 실제 동작 가능한 형태로 검증되었다.

이번 문서는 성공한 Replay 실행을 기준선으로 고정하고, 이후 구현 방향을 **KCP/암복호화 문제 해결 단계에서 자체 Bootstrap Response 생성 단계로 전환**하기 위한 자문 기록이다.

---

## 2. 1차 마일스톤

Git 커밋:

`091aeea3cefbd82555fc457d755100dc4512547d`

커밋 메시지:

`🎉 1차 마일스톤 달성: 메인 화면 진입 (2026-10-02 16:08)`

Git에서 확인된 상태:

| 구성 요소 | 상태 | 근거 |
|---|---|---|
| HTTP Login | ✅ | 기존 구현 |
| UDP/DH Session | ✅ | 기존 구현 |
| KCP C→S | ✅ | 운영 흐름에서 정상 수신 |
| Bootstrap Request parsing | ✅ | field 1/2 및 기타 request field 확인 |
| Serial correlation | ✅ | 요청 Serial로 Response Serial 패치 |
| Bootstrap S→C | ✅ | Replay 응답 전송 |
| KCP fragmentation | ✅ | 10 fragment 전송 |
| Client TryRead | ✅ | Replay 성공 |
| Deserialize | ✅ | Bootstrap 정상 처리 |
| OpCode=2 | ✅ | 실제 Bootstrap 응답 |
| OpInfo 상태 반영 | ✅ | 기존 runtime 관측과 연결 |
| 메인화면 진입 | ✅ | 실제 기기에서 확인 |

이 시점부터 **KCP transport 자체를 주 분석 대상으로 유지할 필요가 없다.**

---

## 3. 성공한 Replay 전체 흐름

이번 성공 로그의 핵심 흐름은 다음과 같다.

```
Client Login / Bootstrap Request
        ↓
Server에서 221B 수신
        ↓
KCP Header parsing
        ↓
ACK 전송
        ↓
Application Length / Flag / IV / Ciphertext 추출
        ↓
Server에서 request 복호화
        ↓
Protobuf field parsing
        ↓
field 1 = Serial
field 2 = OpCode 2
        ↓
실측 Bootstrap gzip 로드
        ↓
request Serial로 Response Serial 패치
        ↓
gzip 재압축
        ↓
현재 Session Key로 암호화
        ↓
KCP 10 fragment 전송
        ↓
Client KCP 수신 / 재조립
        ↓
TryRead 성공
        ↓
Bootstrap Deserialize
        ↓
OpInfo 생성
        ↓
메인화면 진입
```

따라서 이번 성공은 단순한 KCP packet delivery 성공이 아니라 **실제 Application Response가 클라이언트의 Bootstrap 상태 초기화를 통과했다는 증거**다.

---

## 4. 이번 실험에서 확인된 Replay 데이터

성공 로그에서 Bootstrap 원본 gzip은 다음 크기였다.

```
실측 gzip 로드: 13290B
```

Request의 Serial을 현재 세션 값으로 패치한 후 gzip을 다시 압축했다.

```
serial 패치
    ↓
gzip 재압축: 13325B
```

즉 원본 gzip과 재전송 gzip은 byte-for-byte 동일하지 않았다.

그럼에도 메인화면 진입에 성공했다.

### 결론

클라이언트가 요구하는 것은 **특정 gzip 결과의 byte 동일성**이 아니라:

```
gzip decompress
    ↓
정상적인 protobuf bytes
    ↓
Deserialize
    ↓
OpInfo
```

라는 논리적 데이터 계약이다.

따라서 앞으로 자체 protobuf builder를 구현할 때 gzip 결과가 운영 원본과 동일한 byte sequence가 될 필요는 없다.

---

## 5. KCP fragmentation도 독립적으로 검증됨

이번 성공 Replay에서는 총 10개의 fragment가 전송됐다.

```
SN=0 FRG=9  chunk=1372B
SN=1 FRG=8  chunk=1372B
SN=2 FRG=7  chunk=1372B
SN=3 FRG=6  chunk=1372B
SN=4 FRG=5  chunk=1372B
SN=5 FRG=4  chunk=1372B
SN=6 FRG=3  chunk=1372B
SN=7 FRG=2  chunk=1372B
SN=8 FRG=1  chunk=1372B
SN=9 FRG=0  chunk=997B
```

총 메시지 크기:

```
13345B
```

따라서 Bootstrap이 반드시 특정 fragment 개수여야 한다는 가정은 폐기한다.

필요한 조건은:

```
Application payload 생성
    ↓
정상적인 encryption framing
    ↓
KCP fragmentation
    ↓
Client reassembly
```

가 성립하는 것이다.

---

## 6. Serial correlation은 실동작 조건으로 확인

이번 실험에서는 Client가 보내는 Bootstrap request에서 Serial을 읽고, 운영 Bootstrap 데이터의 Serial을 현재 request 값으로 패치했다.

로그 흐름:

```
request Serial 확인
    ↓
실측 Bootstrap Serial 패치
    ↓
gzip 재압축
    ↓
Response 전송
    ↓
메인화면 진입
```

이 결과를 통해 **Bootstrap Response의 Serial correlation이 실제 성공 조건에 포함될 가능성이 매우 높다.**

따라서 자체 Response builder에서도 반드시:

```
Response.SerialNumber = Request.SerialNumber
```

형태를 유지한다.

Serial을 고정값으로 넣는 구현은 기준 구현으로 사용하지 않는다.

---

## 7. 이번 성공으로 더 이상 우선 조사할 필요가 낮아진 영역

다음 항목은 현재 성공 Replay가 확보되었으므로 우선순위를 낮춘다.

### 7.1 KCP 기본 송수신

이미 실제 Main 진입까지 성공했으므로 기본 KCP 송수신은 검증됐다.

### 7.2 AES/Session Key 자체

현재 세션 키를 이용한 Response 암호화가 Client TryRead 및 Bootstrap 처리까지 통과했다.

### 7.3 gzip 압축 여부

재압축 결과가 원본과 달라도 성공했으므로 gzip byte identity 문제는 아니다.

### 7.4 fragment 개수 고정

10 fragment에서도 성공했으므로 운영 PCAP의 fragment 개수를 그대로 고정할 필요가 없다.

### 7.5 최소 Probe의 transport 문제

이전 최소 Probe가 Main 진입에 실패했던 것은 KCP 전송 자체보다 **실제 Bootstrap application state가 부족했기 때문**이라는 해석이 현재 성공 Replay로 뒷받침된다.

---

## 8. 가장 중요한 다음 단계

현재 목표를 다음과 같이 변경한다.

기존:

```
KCP가 왜 TryRead를 통과하지 못하는가?
```

현재:

```
운영 Bootstrap Response를 어떻게 자체 생성할 것인가?
```

즉:

```
[현재 성공 기준선]

운영 protobuf/gzip
    ↓
Serial patch
    ↓
gzip
    ↓
encrypt
    ↓
KCP
    ↓
Main
```

에서:

```
[다음 목표]

자체 protobuf
    ↓
gzip
    ↓
encrypt
    ↓
KCP
    ↓
Main
```

으로 한 단계만 변경한다.

---

## 9. 자체 Bootstrap builder 전환 전략

한 번에 전체 OpInfo를 재구현하지 않는다.

현재 성공 Replay를 GOLDEN BASELINE으로 보존하고 다음 순서로 진행한다.

### 단계 A — 성공 Replay 고정

현재:

```
000192_s2c.bin
→ Serial patch
→ gzip
→ encrypt
→ KCP
→ Main
```

을 회귀 테스트 기준으로 유지한다.

### 단계 B — protobuf payload만 교체

KCP/암호화/압축 pipeline은 그대로 유지하고, 다음 부분만 변경한다.

```
실측 protobuf
        ↓
자체 생성 protobuf
```

처음에는 기존 실측 데이터를 그대로 구조화하여 동일한 의미의 message를 만드는 것을 목표로 한다.

### 단계 C — gzip

자체 protobuf를 gzip으로 압축한다.

이번 실험에서 재압축 크기가 13290B에서 13325B로 변했음에도 성공했으므로 gzip 결과의 크기 자체는 고정 조건으로 두지 않는다.

### 단계 D — 기존 encryption/KCP pipeline 재사용

이미 성공한 경로를 그대로 사용한다.

이렇게 하면 실패했을 때 문제 범위를 protobuf builder로 좁힐 수 있다.

---

## 10. 자체 protobuf 구현 시 주의사항

현재까지의 분석에서 가장 중요한 원칙은 **C# object memory offset과 protobuf field number를 절대 동일시하지 않는 것**이다.

예:

```
OpInfo +0x88 = User
OpInfo +0x98 = Items
OpInfo +0xC0 = Chapters
```

이 값들은 Client runtime object의 메모리 offset이다.

반면 protobuf field number는 별도의 값이다.

따라서 다음과 같이 직접 연결해서는 안 된다.

```
0x98 → protobuf field 98
```

실제 protobuf field mapping은 실측 serialized data와 Deserialize 결과를 통해 확인해야 한다.

---

## 11. 현재 확인된 Bootstrap 핵심 상태

runtime 분석에서 확인된 주요 OpInfo 상태는 다음과 같다.

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
```

기존 runtime offset:

```
+0x88 User
+0x90 Heros
+0x98 Items
+0xA0 Weapons
+0xA8 Equiments
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
```

이 목록은 **runtime object 상태 목록**으로 사용한다.

protobuf tag mapping은 별도 작업으로 유지한다.

---

## 12. 이번 성공에서 얻은 가장 큰 분석적 의미

이번 성공은 다음 두 가설을 실험적으로 분리했다.

### 이전 가설

```
KCP / encryption / compression / protobuf 중
어디에서 실패하는지 불명확
```

### 현재 상태

```
KCP                → 성공
Encryption         → 성공
Compression        → 성공
Fragment reassembly→ 성공
Deserialize        → 성공
Bootstrap          → 성공
Main transition    → 성공
```

따라서 이제 남은 핵심 문제는 **정상적인 Bootstrap Response를 우리 서버가 독립적으로 생성할 수 있도록 구조를 재구현하는 것**이다.

---

## 13. 2차 마일스톤 제안

### 2차 마일스톤

```
운영 데이터 Replay 없이
서버 자체 생성 Bootstrap Response
        ↓
Client Deserialize
        ↓
OpInfo 초기화
        ↓
Main 화면 진입
```

이것을 달성하면 Local Server가 특정 운영 Bootstrap blob에 의존하지 않는 구조로 한 단계 발전한다.

그 다음에는:

```
Warehouse
Chapter
Hero
Weapon
Equipment
기타 OpCode
```

순으로 실제 요청/응답 계약을 확장한다.

---

## 14. 실험 원칙

앞으로의 실험은 반드시 **한 번에 하나의 계층만 변경**한다.

권장:

```
성공 Replay
    ↓
protobuf만 변경
    ↓
결과 확인
```

비권장:

```
protobuf 변경
+ KCP 변경
+ encryption 변경
+ fragment 변경
    ↓
실패
    ↓
원인 불명
```

현재는 이미 성공 기준선이 있으므로, 성공 pipeline을 최대한 고정하는 것이 가장 중요하다.

---

## 15. 결론

2026-10-02 현재 Local Server는 **운영 Bootstrap 데이터를 복제하여 실제 Main 화면까지 진입하는 1차 마일스톤을 달성했다.**

이번 성공으로 다음이 실증됐다.

1. Request Serial을 Response에 반영하는 것이 정상 동작한다.
2. 운영 Bootstrap gzip을 수정 후 재압축해도 Client가 정상 처리한다.
3. KCP fragment 개수가 운영 데이터와 달라도 정상 처리할 수 있다.
4. 현재 Session Key를 이용한 encryption pipeline이 정상 동작한다.
5. Client의 TryRead → Deserialize → Bootstrap 처리 → Main 진입이 연결된다.

따라서 다음 분석의 중심은 KCP가 아니라 **자체 Bootstrap protobuf builder**로 이동한다.

최종 목표:

```
[현재]
운영 Bootstrap 데이터
    ↓
Serial patch
    ↓
Main

[다음]
자체 생성 Bootstrap protobuf
    ↓
gzip
    ↓
현재 encryption/KCP pipeline
    ↓
Main
```

현재 성공 Replay는 이후 모든 실험의 **GOLDEN BASELINE**으로 보존한다.

## 관련 문서

- `2026-10-02-Bootstrap-OpCode2-응답계약-검증_GPT자문.md`
- `2026-10-02-Bootstrap-OpCode2-KCP-Fragment-Response-Checkpoint_GPT자문.md`
- `2026-10-02-Bootstrap-실측-protobuf-구조_lina.md`
- `2026-10-02-KCP-디버깅-일지_lina.md`
- `2026-10-02-개발-핸드오프_lina.md`

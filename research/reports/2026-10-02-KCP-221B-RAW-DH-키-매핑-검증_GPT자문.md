# KCP 221B RAW 구조 및 DH 세션키 매핑 검증 (2026-10-02)

## 1. 분석 대상

2026-10-02 현재 `server_lina/app/kcp/server_udp.py`에서 368B Handshake1 처리 후 수신되는 221B RAW 로그를 기준으로 분석했다.

최근 Git 커밋에서 RAW hex 출력이 추가되어 실제 221B 전체 바이트를 확보할 수 있게 되었으며, 이번 분석에서는 서로 다른 두 세션의 221B를 비교했다.

분석 근거:

- `research/reports/2026-10-01-KCP-디버깅-일지_lina.md`
- `research/reports/2026-10-01-KCP-Handshake-구현정리_lina.md`
- `research/reports/2026-09-30-KCP-DH64-Key-Recovery-PCAP-복호화.md`
- `research/Ghidra_Listing_txt/AL.txt`
- `app/kcp/server_udp.py`
- `app/kcp/dh64.py`
- `app/kcp/crypto.py`

## 2. 221B 구조가 먼저 확정됨

첫 번째 221B:

```
e6eb6f3488f2894f
510000013f9d5bfa
0000000000000000
c1000000
80
51b30811be60b02dd1bcc430f2943e98558a12e...
```

offset 기준:

| Offset | Size | 내용 |
|---:|---:|---|
| 0x00 | 8B | Session ID |
| 0x08 | 16B | KCP/transport header 영역 |
| 0x18 | 4B | Application length = 0xC1 = 193 |
| 0x1C | 1B | Application flag = 0x80 |
| 0x1D | 16B | IV |
| 0x2D | 176B | AES ciphertext |

중요한 계산:

```
221 - 8 = 213
213 - 16(header) - 4(length) - 1(flag) = 192
192 = 16(IV) + 176(ciphertext)
176 % 16 = 0
```

따라서 기존의:

> 221B - 8B = 213B 전체를 AES 암호문으로 본다.

는 잘못된 접근이다.

실제 암호화 영역은:

```
221B
 └─ session 8B
 └─ transport/KCP header 16B
 └─ application length 4B (=193)
 └─ flag 1B (=0x80)
 └─ encrypted block 192B
      ├─ IV 16B
      └─ AES-CBC ciphertext 176B
```

이다.

## 3. Ghidra TryRead와 RAW 구조가 일치함

`KCPTube$$TryRead @ 015b08bc`에서 KCP 수신 데이터의 application length를 `BitConverter.ToInt32`로 읽고, 이후 Encrypt flag의 bit 7을 확인한다.

Encrypt flag가 설정된 경우:

```
KCPTube.get_Key()
    ↓
Tools.DecryptUnSafe
    ↓
flag의 0x80 제거
    ↓
flag의 0x40이 있으면 DecompressUnSafe
    ↓
ProtoBuf Deserialize
```

실제 221B에서는 application length가:

```
c1 00 00 00 = 193
```

이고 바로 다음 byte가:

```
80
```

이다.

즉 현재 RAW 패킷의 `0x80`은 IV가 아니라 **Encrypt flag**다.

## 4. DecryptUnSafe의 IV 위치와도 일치

Ghidra `Tools$$DecryptUnSafe @ 015b0d28` 분석 결과, 입력 데이터의 앞 16B를 별도 IV 영역으로 사용한 뒤 Rijndael/CBC 계열 TransformBlock/TransformFinalBlock을 수행한다.

따라서 현재 패킷에서는:

```
application flag
  0x80

encrypted payload
  51b30811be60b02dd1bcc430f2943e98   ← IV 16B
  558a12ea7afbbb56755ce92e5e6890fd...
  ...
  8f6abaaaf16366d60ccd7598bc5ee224...
```

로 해석하는 것이 맞다.

## 5. 그런데 기존 server_lina 세션키로는 복호화되지 않음

첫 번째 세션 서버 로그:

```
Client public #1 = 0x63b0a154d3670b16
Client public #2 = 0xd14e99ecb30a91

Secret #1 = 0xadf01acd533931c6
Secret #2 = 0x7a28a4a5edb3d907

현재 server_lina가 저장한 Key:
c6313953cd1af0ad07d9b3eda5a4287a
```

이 Key로:

```
IV = 51b30811be60b02dd1bcc430f2943e98
Ciphertext = 176B
AES-128-CBC
```

를 수행하면 평문이 랜덤 데이터로 나온다.

이는 단순 IV 위치 문제로 설명되지 않는다.

## 6. 핵심 원인 — Server public pair가 응답에서 역순으로 전달됨

현재 `server_udp.py`의 33B 응답은:

```python
struct.pack_into("<Q", resp, 0x11, srv_pub2)
struct.pack_into("<Q", resp, 0x19, srv_pub1)
```

이다.

반면 Ghidra `KCPTube$$Handshake2 @ 015b1f68`는:

```
packet + 0x11 -> peer public #1
packet + 0x19 -> peer public #2
```

로 읽는다.

따라서 클라이언트가 실제 사용하는 DH pairing은 서버 코드가 현재 계산하는:

```
client_pub1 ^ server_private1
client_pub2 ^ server_private2
```

가 아니라:

```
client_pub1 ^ server_private2
client_pub2 ^ server_private1
```

이다.

즉 현재 응답 형식을 유지한다면 서버의 세션키 계산도 역순 pairing이어야 한다.

## 7. 첫 번째 세션 실제 검증

고정 서버 public에서 discrete log을 계산해 서버 private residue를 복구했다.

```
server private #1 = 0xbbed94bfefcbcc0a
server private #2 = 0x48205a17fdba0a3d
```

클라이언트 public:

```
client #1 = 0x63b0a154d3670b16
client #2 = 0x0d14e99ecb30a91
```

현재 응답 순서에 맞는 실제 shared secret:

```
secret1 = client_pub1 ^ server_private2
        = 0xf29acffebda7d18f

secret2 = client_pub2 ^ server_private1
        = 0xd2cff949e99e8724
```

Little Endian 조합:

```
actual session key =
8fd1a7bdfecf9af224879ee949f9cfd2
```

이 Key + IV로 221B를 복호화하면:

```
0896f59c3c1002220b08e8d8c6a6e19f
d03f10052a1073616d73756e6720534d2d533933364e62
2065383962313538653462636639383865626430396562
383366353337386538376a206362636664663130643536
65353761383966376362313961343931643133396572
0848616e6468656c647a36416e64726f6964204f53203137
202f204150492d33372028435032412e3236303630352e3031362f533933364e4b535543445a494629
04040404
```

가 나온다.

문자열 영역에는 실제로:

```
samsung SM-S936N
Android OS 17 / API-37
CP2A.260605.016/S936NKSUCDZIF
```

가 복원된다.

이는 AES 복호화가 우연히 패딩만 통과한 것이 아니라 **실제 의미 있는 평문을 얻은 것**이다.

PKCS7 padding도 마지막:

```
04 04 04 04
```

로 정상 확인된다.

## 8. 두 번째 세션에서도 동일하게 재현

두 번째 세션:

```
Client public #1 = 0x03134f1973a8a557
Client public #2 = 0x25bdb48e5f5e7add
```

역순 pairing:

```
secret1 = 0xf09012f7e6b7055
secret2 = 0x53801c34df6b4c55
```

Key:

```
55706b7e2f01090f554c6bdf341c8053
```

두 번째 221B 역시 같은 의미의 평문으로 복호화된다.

특히 첫 번째와 두 번째 세션에서 동일한 디바이스 정보 문자열이 복원되므로, 단순 우연한 printable 결과일 가능성은 매우 낮다.

## 9. 이번 단계에서 확정된 구조

현재 기준 KCP application packet:

```
[Session ID 8]
[Transport/KCP header 16]
[Application Length 4]
[Flag 1]
[IV 16]
[AES-128-CBC ciphertext N]
```

현재 샘플:

```
Session       = 8B
Header        = 16B
Length        = 193
Flag          = 0x80
IV            = 16B
Ciphertext    = 176B
Plaintext     = 172B after PKCS7
```

또한:

```
Flag 0x80 = Encrypt
Flag 0x40 = Compress
```

라는 기존 Ghidra 분석과 실제 패킷 구조가 일치한다.

## 10. server_lina 구현에서 수정해야 할 핵심

현재 코드:

```python
secret1 = pow(pub1, dh.private1, P)
secret2 = pow(pub2, dh.private2, P)
session_key = LE64(secret1) + LE64(secret2)
```

는 현재 33B 응답의 public pair 순서와 맞지 않는다.

현재 응답을 그대로 유지한다면:

```python
secret1 = pow(pub1, dh.private2, P)
secret2 = pow(pub2, dh.private1, P)
session_key = LE64(secret1) + LE64(secret2)
```

로 계산해야 한다.

대상은 최소한:

- `handle_handshake_51()`
- `handle_handshake1()`

두 경로다.

단, 이번 자문에서는 코드를 직접 수정하지 않는다.

## 11. 33B 응답 자체는 당장 역순을 바꾸지 않는다

이번 분석으로 중요한 점은:

> 현재 서버가 public #2 → 0x11, public #1 → 0x19 순서로 보내고 있는 것이 틀렸다고 단정할 수 없다.

오히려 실제 221B 암호문을 이 순서에 맞춘 역순 DH pairing으로 복호화했을 때 의미 있는 평문이 나왔다.

따라서 다음 테스트에서는:

```
현재 33B response 유지
        ↓
DH secret pairing만 역순 적용
        ↓
session key 출력
        ↓
221B 복호화
```

를 먼저 검증한다.

응답 순서를 동시에 바꾸면 두 변수를 한 번에 변경하게 되어 원인 추적이 어려워진다.

## 12. 서버에서 다음 테스트 때 반드시 출력할 값

다음 실행에서는 221B RAW를 계속 출력하되, Handshake1 직후 다음 값을 같이 기록한다.

```
Server private #1
Server private #2

Server public #1
Server public #2

Client public #1
Client public #2

Normal secret #1
Normal secret #2
Normal key

Cross secret #1
Cross secret #2
Cross key
```

그리고 221B 수신 시:

```
session
application_length
flag
IV
ciphertext_length
```

를 출력한다.

복호화 성공 조건은:

1. ciphertext 길이 % 16 == 0
2. PKCS7 padding 정상
3. 평문에 protobuf/device-info 구조가 존재
4. printable 문자열이 우연히 하나만 나오는 것이 아니라 구조적으로 반복됨

으로 잡는다.

## 13. 현재 RAW 로그에서 중요한 추가 발견

첫 번째 221B:

```
... c1000000 80 51b30811...
```

두 번째 221B:

```
... c1000000 80 14ffdc081a...
```

앞부분의:

```
c1000000 = 193
80       = Encrypt
```

는 동일하다.

반면 IV:

```
51b30811be60b02dd1bcc430f2943e98
14ffdc081af22717d13f959bd7dbd5dd
```

는 세션마다 달라진다.

따라서 IV를 고정값으로 취급해서는 안 된다.

## 14. 현재 결론

**이번 RAW 221B 로그로 221B 복호화 블로킹 원인이 DH 계산식 자체가 아니라 public pair의 wire 순서와 서버 session-key pairing 불일치라는 점을 사실상 확정했다.**

정리:

```
33B server response
  +0x11 = server public #2
  +0x19 = server public #1
          ↓
Client Handshake2
  +0x11 -> peer public #1
  +0x19 -> peer public #2
          ↓
client private #1 × server public #2
client private #2 × server public #1
          ↓
actual key = cross pairing
          ↓
221B
  flag=0x80
  IV=16B
  ciphertext=176B
          ↓
AES-128-CBC
          ↓
실제 디바이스 정보 평문 복원
```

따라서 다음 구현 테스트의 목표는 **DH 역순 pairing을 적용했을 때 221B 복호화 및 이후 TryRead/Decompress/ProtoBuf 처리까지 진행되는지 확인하는 것**이다.

---

*작성: 2026-10-02, GPT 자문*

## 15. 2026-10-02 런타임 재검증 — DH 역순 Key가 실제 구현에서도 확정됨

사용자가 역순 DH pairing을 적용한 최신 server_udp.py 실행 로그를 제공했다. 이번 결과는 이전 PCAP/오프라인 검증보다 강한 증거다.

### 15.1 현재 런타임 세션
```text
Server public #1 = 0xe248589b3f1056b2
Server public #2 = 0x54c90f0e4e28537b
Client public #1 = 0xb1f254d7dbe4142a
Client public #2 = 0x8d481cb9a96ffcc7
Session ID = 0x280ee792e2a6dd6f
Session key = 73e8dec343f0a2d1de2b17750db6fb03
```

서버가 이 세션키로 즉시 221B AES 복호화를 수행하여 172B 평문을 반복적으로 얻었다. 따라서 현재 구현의 session key가 실제 클라이언트 암호화 키와 일치한다.

### 15.2 221B 구조 런타임 재확인
```text
App Length = 193
Flag       = 0x80
IV         = 139dc0345e5806bae4c202dd7d074eaf
Ciphertext = 176B
```

이전 분석의 `[Session 8][Header 16][Length 4][Flag 1][IV 16][Ciphertext 176]` 구조가 실제 런타임에서도 그대로 성립한다.

### 15.3 AES 복호화 단계는 사실상 종료
복호화 평문에서 `samsung SM-S936N`, `Android OS 17 / API-37`, `CP2A.260605.016/S936NKSUCDZIF`가 확인된다. 이는 단순 padding 통과가 아니라 실제 의미 있는 payload가 복원된 것이다.

현재 상태는 DH pairing → Session Key → IV → AES-CBC → PKCS7 unpadding까지 런타임 검증 완료로 변경한다.

### 15.4 동일 세션에서 221B 반복 수신
동일 Session ID `0x280ee792e2a6dd6f`에 대해 여러 221B가 수신되었고 IV, ciphertext, plaintext는 동일하다. 반면 Header의 일부 값은 `b59468fa`, `7e9568fa`, `0f9768fa`, `a09868fa` 등으로 변한다.

따라서 현재 현상은 동일 application payload의 KCP 재전송/반복 전송일 가능성이 높다. 서버는 이를 각각 새로운 게임 메시지로 처리하기보다 KCP sequence/ACK 상태와 연계해 관리해야 한다. Header 내부 각 값의 정확한 의미는 추가 PCAP 비교 전까지 확정하지 않는다.

### 15.5 현재는 Decompress 단계보다 ProtoBuf가 우선
Flag가 `0x80`뿐이므로 현재 샘플에는 Compress bit `0x40`이 설정되어 있지 않다. 따라서 다음 경로는 `flag 처리 → IV 분리 → AES-CBC decrypt → PKCS7 unpad → ProtoBuf Deserialize`가 우선이다.

### 15.6 다음 분석의 핵심 — ProtoBuf field/type 추적
평문 시작부 `08 9e e4 d0 3c 10 02 22 0b ...`는 protobuf wire-format과 일치하는 형태다. 다음에는 Ghidra에서 `KCPTube$$TryRead` 이후의 Deserialize 호출을 추적해 실제 타입, message/opcode/command ID, field 번호를 대응시키는 것이 핵심이다.

특히 `0x08`은 field #1 varint, `0x10`은 field #2 varint, `0x22`는 field #4 length-delimited로 해석할 수 있지만, 현재 정보만으로 각 field의 의미를 임의 확정하지 않는다.

### 15.7 다음 런타임 로그 권장
```text
[PROTO]
plain_len
plain_hex 전체
flag
compress 여부
protobuf deserialize 성공/실패
deserialize type/class name
message/opcode/command id
```

가능하면 Deserialize 직전의 plaintext byte[] 전체를 파일로 저장한다. 동일 payload가 반복되므로 한 개의 완전한 평문만 확보해도 충분하다.

### 15.8 현재 진행도
```text
HTTP 로그인                         완료
UDP 51B Handshake1                  완료
33B Handshake 응답                  완료
DH public pair wire-order 해석      확정
Cross DH session key                런타임 검증 완료
221B 구조 분석                     확정
AES-128-CBC 복호화                 런타임 검증 완료
PKCS7 unpadding                    검증 완료
디바이스 정보 평문 확인             검증 완료
ProtoBuf 상위 Deserialize          다음 작업
KCP ACK/응답 28B                    다음 작업
게임 데이터 송수신                  이후 작업
```

**결론: 현재 개발의 핵심 병목은 암호화 계층이 아니라 221B 복호화 이후의 ProtoBuf 메시지 해석 및 서버 응답 생성 단계로 이동했다.**

---
*추가 자문: 2026-10-02, GPT*
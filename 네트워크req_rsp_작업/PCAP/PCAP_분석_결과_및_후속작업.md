# PCAP 분석 결과 및 자동 분석 도구

작성일: 2026-09-21  
대상 PCAP: `PCAPdroid_21_9월_13_26_19시작로그인인게임메인메뉴.pcap`

## 1. 목적

이번 작업은 실제 PCAP을 기준으로 지금까지 Ghidra에서 분석한 다음 구조를 검증하고, 이후 반복 분석을 자동화하기 위한 Python 분석기를 만드는 것을 목표로 한다.

- TCP `TCPTube` handshake
- UDP `KCPTube` handshake
- DH64 #1/#2
- TCP/KCP별 session key 생성 구조
- `RijndaelManaged` 기반 암호화
- `[IV 16 bytes][ciphertext]` 구조
- KCP fragmentation/retransmission
- 로그인 → 인게임 → 메인 메뉴 구간의 request/response 후보 추출

---

## 2. 실제 PCAP 기본 결과

이번 PCAP은 약 **81.7 KB**, 총 **211개 패킷**으로 확인되었다.

주요 게임 서버:

```text
182.92.62.79:8000
```

확인된 전송:

```text
TCP 10.215.173.1:39490 <-> 182.92.62.79:8000
UDP 10.215.173.1:33922 <-> 182.92.62.79:8000
```

즉 게임은 TCP와 UDP/KCP를 동시에 사용한다.

---

## 3. TCP TCPTube handshake 검증

### Client → Server

첫 번째 주요 TCP payload는 373 bytes이며 다음 구조와 정확하게 일치한다.

```text
offset  size
0x00    8       zero
0x08    4       length = 0x169 (361)
0x0C    1       marker = 0x01
0x0D    8       client DH public #1
0x15    8       client DH public #2
0x1D    344     param4
```

실제 값:

```text
Client DH #1 raw:
4d 59 1f a4 ab f5 37 36

Client DH #2 raw:
6e 98 e8 28 2a 92 44 fe
```

little-endian 정수 표현:

```text
public #1 = 0x3637f5aba41f594d
public #2 = 0xfe44922a28e8986e
```

크기 검증:

```text
8 + 4 + 1 + 8 + 8 + 344 = 373
0x169 = 361 = 344 + 17
```

### Server → Client

37 bytes 응답:

```text
0x00    8       zero
0x08    4       length = 0x19
0x0C    1       marker = 0x01
0x0D    8       TCPConvID
0x15    8       server DH #1
0x1D    8       server DH #2
```

실제 값:

```text
TCPConvID = 0x632

Server DH #1 = 0xca4d30dba4429f27
Server DH #2 = 0x7164b27b3d91d781
```

따라서 Ghidra에서 분석한 `TCPTube$$Update` / handshake 구조가 실제 PCAP으로 검증되었다.

---

## 4. TCP param4 분석

TCP client handshake의 344-byte `param4`는 ASCII Base64 형태이다.

Base64 decode 결과:

```text
344 Base64 characters
        ↓
256-byte binary
```

decode된 데이터의 entropy는 약 7.21 bit/byte 수준으로 높다.

따라서 단순 문자열 설정값보다는 암호화 또는 난수성 데이터일 가능성이 높다.

256-byte 크기는 RSA-2048 ciphertext와 같은 형태이지만, **현재 단계에서는 RSA 사용을 확정하지 않는다.**

향후 확인 대상:

- `TCPTube$$Update` 호출 전후의 param4 생성 함수
- 인증/로그인 관련 암호화 함수
- Base64 encode/decode xref
- RSA/PKCS 계열 함수 xref
- 서버에서 이 param4가 어떻게 사용하는지

---

## 5. UDP/KCP handshake 검증

UDP에서도 Ghidra에서 찾았던 `KCPTube$$Handshake1` 구조가 확인되었다.

구조:

```text
8 bytes zero
8 bytes KCP DH public #1
8 bytes KCP DH public #2
param4
```

실제 Client KCP DH:

```text
public #1 = 0x3b235655562743fa
public #2 = 0xd4bed6816a9f1c5c
```

Server KCP DH:

```text
public #1 = 0x7637acf954e564b3
public #2 = 0xdd73013d938774b9
```

KCP ConvID:

```text
0x07e669fdd645ee1e
```

### 중요한 결론

TCP와 KCP는 동일한 DH 값을 재사용하지 않는다.

```text
TCP
 ├─ DH #1
 ├─ DH #2
 └─ TCP session key

KCP
 ├─ DH #1
 ├─ DH #2
 └─ KCP session key
```

따라서 TCP와 KCP 각각에 대해 별도의 session key가 생성되는 구조로 보는 것이 현재 데이터와 일치한다.

---

## 6. DH64 분석 결과와 연결

Ghidra에서 확인한 핵심:

### modulus

```text
p = 2^64 - 59
  = 0xFFFFFFFFFFFFFFC5
```

### generator

```text
g = 5
```

### private 생성

```text
private =
    ((uint64)Random1 << 32)
    |
    ((uint32)Random2 + 1)
```

### public

```text
public = 5^private mod p
```

### shared secret

```text
secret = peerPublic^localPrivate mod p
```

### session key

Ghidra의 `KCPTube$$Handshake2`에서 확인한 구조:

```text
key[0:8]  = LE64(secret1)
key[8:16] = LE64(secret2)
```

TCP도 동일한 2회 DH 교환을 사용하는 구조로 분석되어 있다.

PCAP에는 public 값은 존재하지만 private 값은 존재하지 않는다. 따라서 PCAP만으로 DH secret을 계산할 수 없다.

---

## 7. 실제 암호화 payload 검증

KCP application payload에서 다음 형태가 확인되었다.

```text
[16-byte IV]
[16-byte block aligned ciphertext]
```

예를 들어 한 payload는:

```text
16-byte IV
3b 8d 6a 1f f4 43 c3 7b
38 a4 51 38 3a 5b 03 f1

ciphertext
176 bytes
```

176 bytes는:

```text
176 / 16 = 11 blocks
```

따라서 지금까지 Ghidra에서 확인한 암호화 구조와 정확히 부합한다.

다른 KCP 응답에서도:

```text
1-byte application prefix
16-byte IV
192-byte ciphertext
```

후보가 확인되며:

```text
192 / 16 = 12 blocks
```

이다.

---

## 8. Rijndael 설정

Ghidra 분석 및 `DataTool$$DecryptUnSafe` 교차검증 기준:

```text
Algorithm : RijndaelManaged
Mode      : CBC
Padding   : PKCS7
BlockSize : 128 bit
IV        : 16 bytes
Key       : 16 bytes
```

실제 복호화 흐름:

```text
encrypted payload
        │
        ├── first 16 bytes → IV
        │
        └── remaining bytes → ciphertext
                         │
                         ▼
              CreateDecryptor(key, IV)
                         │
                         ▼
                TransformBlock
                         │
                         ▼
             TransformFinalBlock
                         │
                         ▼
                    plaintext
```

주의: RijndaelManaged 내부 field offset 자체는 Mono/IL2CPP decompilation에서 이름과 실제 semantic mapping이 어긋날 수 있으므로, 향후 정확한 field offset을 문서화할 때는 property setter와 실제 동작을 기준으로 재검증한다.

---

## 9. KCP fragmentation

PCAP에서는 대형 서버 응답이 여러 KCP fragment로 분할되어 있다.

확인된 사례:

```text
KCP SN 1 ~ 11
재조립 후 약 14,901 bytes
```

또한 retransmission도 존재한다.

따라서 UDP packet을 단순 시간순으로 연결하면 안 된다.

향후 분석기는 최소한 다음 KCP field를 추적해야 한다.

```text
conv
cmd
frg
wnd
ts
sn
una
len
```

특히:

- `conv` → 세션 식별
- `sn` → 순서
- `frg` → fragmentation
- `una` → acknowledge
- `len` → KCP payload 길이

를 기준으로 application message를 재조립해야 한다.

---

## 10. Python 자동 분석기

추가된 파일:

```text
네트워크req_rsp_작업/PCAP/pcap_analyzer.py
```

목적:

1. classic PCAP 직접 파싱
2. IPv4/TCP/UDP 분류
3. flow별 통계
4. TCP sequence 기반 재조립
5. TCPTube handshake 자동 탐지
6. KCPTube handshake 후보 탐지
7. KCP header 파싱
8. KCP application payload 추출
9. IV/ciphertext 후보 자동 탐지
10. Base64 param4 후보 decode
11. JSON/NDJSON 보고서 생성

외부 패킷 분석 프로그램 없이 Python 표준 라이브러리만으로 동작하도록 작성했다.

### 실행

```powershell
python pcap_analyzer.py "PCAPdroid_21_9월_13_26_19시작로그인인게임메인메뉴.pcap"
```

또는:

```powershell
python pcap_analyzer.py input.pcap --out analysis
```

생성 파일:

```text
analysis/
├─ summary.json
├─ summary.txt
└─ packets.ndjson
```

---

## 11. 현재 Python 분석기의 역할과 한계

현재 Python 분석기는 **암호 해독기가 아니다.**

가능:

- packet/flow 분석
- TCP 재조립
- TCP DH handshake 추출
- KCP header 분석
- KCP application payload 추출
- IV/ciphertext 후보 탐지
- Base64 데이터 분석
- 이후 PCAP 비교를 위한 정형 JSON 생성

불가능:

- PCAP만으로 DH private key 복구
- DH shared secret 계산
- session key 복구
- 암호화 payload plaintext 복원

따라서 다음 단계에서는 runtime hook이 필요하다.

---

## 12. 다음 단계 — 가장 중요한 작업

### 1단계: Python 분석기 실행

실제 PCAP을 대상으로:

```text
pcap_analyzer.py
        ↓
summary.json
packets.ndjson
        ↓
TCP/KCP message 목록
```

을 만든다.

### 2단계: KCP 완전 재조립

현재 분석기는 KCP header와 application payload 후보를 추출한다.

다음 버전에서는:

```text
conv + direction + sn + frg
```

기반으로 실제 application message 단위까지 재조립한다.

### 3단계: runtime key capture

가장 중요한 후킹 후보:

```text
Alioth.S1.Common.DH64$$Secret
```

또는:

```text
System.Security.Cryptography.RijndaelManaged$$CreateDecryptor
```

우선순위는 `CreateDecryptor(key, IV)`가 높다.

여기서:

```text
key = 16 bytes
IV  = 16 bytes
```

를 확보하면 PCAP의 ciphertext와 직접 비교할 수 있다.

### 4단계: 복호화 검증

runtime에서 확보한 key/IV와 PCAP의 ciphertext를 이용:

```text
PCAP ciphertext
       +
runtime key
       +
PCAP IV
       ↓
Rijndael CBC PKCS7
       ↓
plaintext
```

를 수행한다.

### 5단계: protobuf 확인

복호화된 plaintext가 확보되면:

```text
plaintext
   ↓
protobuf / OpInfo
   ↓
opcode / request / response
   ↓
login
dungeon
gacha
shop
reward
etc.
```

구조를 매핑한다.

---

## 13. 최종 목표

현재 작업은 단순히 PCAP을 읽는 것이 목적이 아니다.

최종적으로 다음 파이프라인을 만든다.

```text
PCAP
 │
 ├─ TCP
 │   ├─ TCPTube
 │   ├─ DH
 │   └─ encrypted frame
 │
 └─ UDP
     ├─ KCP
     ├─ DH
     ├─ fragmentation
     └─ encrypted frame
             │
             ▼
       runtime key capture
             │
             ▼
       Rijndael decrypt
             │
             ▼
          plaintext
             │
             ▼
          protobuf
             │
             ▼
       request / response
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
      로그인 던전 뽑기
```

이 구조가 완성되면 이후에는 각각의 실제 요청/응답을 분리해서 게임 서버 프로토콜을 문서화할 수 있다.

---

## 14. 현재 분석 기준 요약

| 항목 | 현재 상태 |
|---|---|
| PCAP 읽기 | 완료 |
| TCP flow 확인 | 완료 |
| UDP flow 확인 | 완료 |
| TCPTube handshake | PCAP 검증 완료 |
| KCPTube handshake | PCAP 검증 완료 |
| TCP DH public 값 | 확보 |
| KCP DH public 값 | 확보 |
| TCPConvID | 확보 |
| KCP ConvID | 확보 |
| param4 Base64 | 확인 |
| param4 256-byte decode | 확인 |
| Rijndael CBC | 확인 |
| PKCS7 | 확인 |
| 16-byte IV | 확인 |
| KCP fragmentation | 확인 |
| KCP retransmission | 확인 |
| Python PCAP analyzer | 추가 |
| DH private key | 미확보 |
| session key | 미확보 |
| plaintext | 미확보 |
| protobuf message | 다음 단계 |
| login request/response | 다음 단계 |
| dungeon request/response | 이후 |
| gacha request/response | 이후 |

---

## 15. 핵심 함수 기준

### DH

```text
Alioth.S1.Common.DH64$$KeyPair
Alioth.S1.Common.DH64$$PublicKey
Alioth.S1.Common.DH64$$Secret
Alioth.S1.Common.DH64$$powmodp
Alioth.S1.Common.DH64$$pow_mod_p
Alioth.S1.Common.DH64$$mul_mod_p
```

### TCP/KCP

```text
Alioth.S1.Net.TCPTube$$Update
Alioth.S1.Net.KCPTube$$Handshake1
Alioth.S1.Net.KCPTube$$Handshake2
```

### Encryption

```text
Alioth.S1.Net.Tools$$DecryptUnSafe
DataTool$$DecryptUnSafe
System.Security.Cryptography.RijndaelManaged$$CreateDecryptor
System.Security.Cryptography.RijndaelManaged$$NewEncryptor
System.Security.Cryptography.RijndaelManagedTransform$$.ctor
```

---

## 16. 결론

이번 실제 PCAP 분석으로 기존 Ghidra 분석의 핵심 가설이 실제 네트워크 데이터와 연결되었다.

특히:

```text
DH64
  ↓
TCP/KCP별 2회 DH
  ↓
16-byte session key
  ↓
Rijndael CBC / PKCS7
  ↓
[IV][ciphertext]
  ↓
protobuf
```

이라는 흐름을 현재 작업의 기준 구조로 사용한다.

이제 가장 중요한 미확인 값은 **runtime에서 생성되는 16-byte session key**다.

따라서 다음 작업은 PCAP 구조를 더 추측하는 것이 아니라, **LDPlayer 실행 환경에서 `DH64.Secret()` 또는 `CreateDecryptor(key, IV)`를 후킹하여 실제 key를 확보하고 PCAP의 암호문을 복호화하는 것**으로 진행한다.

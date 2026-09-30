# TCP DH64 키 생성 및 PCAP 검증 계획

- 분석일: 2026-09-22
- 대상: `Alioth.S1.Net.TCPTube`, `Alioth.S1.Common.DH64`
- 목적: Ghidra에서 확정한 DH64 구조를 실제 PCAP과 대조하고, 이후 런타임 private key를 확보했을 때 세션 Key와 TCP 암호문까지 검증할 수 있는 Python 도구의 기준을 정리한다.

## 1. 현재 결론

현재까지 Ghidra 분석으로 다음 흐름이 확정되었다.

```
DH64::.ctor
  -> new System.Random()

KCPTube::Handshake1
  -> DH64::KeyPair #1
  -> DH64::KeyPair #2
  -> client public #1/#2 전송

TCPTube::TryOutput
  -> TCPConvID 수신
  -> server public #1/#2 수신
  -> DH64::Secret #1/#2
  -> 16-byte TCPTube.Key
  -> State = 3

TCP receive
  -> flag 0x80
  -> Tools.DecryptUnSafe
  -> flag 0x40
  -> DecompressUnSafe
  -> OpInfo protobuf
```

DH 파라미터:

- `p = 0xFFFFFFFFFFFFFFC5 = 2^64 - 59`
- `g = 5`
- `public = pow(5, private, p)`

## 2. Random / private key 생성

`DH64::KeyPair`에서 동일한 `System.Random` 객체의 `Next()`가 두 번 호출된다.

```c
int32_t r1 = rng.Next();
int32_t r2 = rng.Next();

uint64_t privateKey =
    ((uint64_t)(uint32_t)r1 << 32) |
    (uint32_t)(r2 + 1);

uint64_t publicKey = powmodp(5, privateKey);
```

두 번의 KeyPair가 연속 실행되므로 한 DH64 객체에서 총 4회의 `Next()` 결과가 사용된다.

```
Next #1, #2 -> private1 -> public1
Next #3, #4 -> private2 -> public2
```

`System.Random()`은 `GenerateSeed()`를 거쳐 seed를 받으며, GenerateSeed는 static/shared Random을 사용한다. static Random의 초기 seed는 `Interop.GetRandomBytes`에서 만들어지는 경로가 확인되었다.

따라서 **일반적인 PCAP만으로 private1/private2를 역산하는 것은 현재 확인된 코드 구조상 검증 전략으로 사용하지 않는다.**

## 3. Client handshake 검증 대상

`KCPTube::Handshake1`에서 확인된 논리적 payload 구조:

| Offset | Size | 의미 |
|---|---:|---|
| +0x00 | 8 | zero/reserved |
| +0x08 | 8 | client public #1, LE64 |
| +0x10 | 8 | client public #2, LE64 |
| +0x18 | variable | 추가 handshake payload |

실제 송신 길이는:

```
0x18 + additional_payload_length
```

따라서 PCAP에서는 Client -> Server 방향의 TCP payload에서 이 구조를 우선 탐색한다.

## 4. Server handshake 검증 대상

`TCPTube::TryOutput`에서 확인된 구조:

| Offset | Size | 의미 |
|---|---:|---|
| +0x00 | 8 | reserved/zero |
| +0x08 | 4 | length, 정상 handshake는 0x19 |
| +0x0C | 1 | marker = 1 |
| +0x0D | 8 | TCPConvID |
| +0x15 | 8 | server public #1 |
| +0x1D | 8 | server public #2 |

기존 PCAP에서 확인된 값:

- TCPConvID = `0x632`
- server public #1 = `0xca4d30dba4429f27`
- server public #2 = `0x7164b27b3d91d781`

따라서 Python 검증기는 우선 이 값들을 기준으로 Server handshake 후보를 찾아야 한다.

## 5. PCAP만으로 가능한 검증

PCAP만으로 다음 항목은 직접 검증할 수 있다.

- TCP handshake packet 후보 식별
- Client/Server 방향 확인
- Client public #1/#2 추출
- TCPConvID 추출
- Server public #1/#2 추출
- handshake length 및 marker 확인
- 동일 TCP connection에서 client/server DH 값이 대응하는지 확인
- Client public 값에 대해 `pow(5, private, p)`가 맞는지 private가 확보된 경우 검증

반면 다음은 private 값 또는 런타임 관찰값이 필요하다.

- private1/private2 자체 확인
- secret1/secret2 계산
- 16-byte session Key 계산
- 암호문 복호화
- 복호화 후 OpInfo protobuf 해석

## 6. Python 검증 도구 전략

도구 이름:

`네트워크req_rsp_작업/PCAP/pcap_dh_validator.py`

1차 버전의 역할은 **PCAP 구조 검증만 담당**한다.

```
PCAP
  ↓
Ethernet/IPv4/TCP payload 추출
  ↓
Server handshake 후보 탐색
  ↓
TCPConvID / serverPublic1 / serverPublic2 추출
  ↓
Client handshake 후보 탐색
  ↓
clientPublic1 / clientPublic2 추출
  ↓
검증 결과 출력
```

2차 버전에서는 다음 입력을 추가한다.

```
--private1
--private2
```

그러면:

```
private
  ↓
DH Secret
  ↓
LE64(secret1) || LE64(secret2)
  ↓
16-byte session key
```

까지 계산한다.

3차 버전에서는 실제 암호화 TCP payload와 IV를 입력으로 받아 Rijndael/AES-CBC/PKCS7 복호화를 연결한다.

## 7. 최종 검증 순서

```
[1] PCAP 구조 검증
       ↓
[2] Client public #1/#2 확인
       ↓
[3] Server public #1/#2 확인
       ↓
[4] 런타임에서 private1/#2 확보
       ↓
[5] Python에서 public = pow(5, private, p) 재검증
       ↓
[6] secret1/#2 계산
       ↓
[7] 16-byte session key 생성
       ↓
[8] TCP ciphertext 복호화
       ↓
[9] PKCS7 정상 여부 확인
       ↓
[10] OpInfo protobuf 구조 확인
```

## 8. 중요한 검증 기준

### 8.1 Endianness

Ghidra 코드에서 `BitConverter.GetBytes(UInt64)` 후 `Buffer.BlockCopy`를 사용하므로 현재 대상 ARM/Unity 환경에서는 Little Endian을 기준으로 한다.

따라서 PCAP byte:

```
27 9f 42 a4 db 30 4d ca
```

는:

```
0xca4d30dba4429f27
```

으로 읽는다.

### 8.2 Public과 Private의 관계

검증 시 반드시:

```
public1 == pow(5, private1, 0xFFFFFFFFFFFFFFC5)
public2 == pow(5, private2, 0xFFFFFFFFFFFFFFC5)
```

를 먼저 확인한다.

이 검증이 통과한 후에만 server public과 private를 이용해 secret을 계산한다.

### 8.3 Session Key

```
secret1 = pow(serverPublic1, private1, p)
secret2 = pow(serverPublic2, private2, p)

sessionKey =
    secret1.to_bytes(8, "little") +
    secret2.to_bytes(8, "little")
```

## 9. 현재 작업에서 하지 않는 것

- PCAP에서 private key를 무리하게 추측하지 않는다.
- Random seed를 PCAP만으로 복원한다고 가정하지 않는다.
- Client handshake offset을 실제 PCAP 확인 전에 확정하지 않는다.
- 암호문을 복호화했다고 가정하지 않는다.

특히 **PCAP에서 실제 Client handshake를 확인하기 전에는 client public의 실제 위치를 코드에 하드코딩하지 않는다.**

## 10. 다음 작업

1. 실제 PCAP 파일에서 Client -> Server handshake 후보 검색
2. Client public #1/#2 실제 byte 확인
3. Server public 값과 TCPConvID의 실제 byte 확인
4. `pcap_dh_validator.py`로 자동 검증
5. Ghidra에서 `TCPTube::Update`의 KeyPair -> handshake Output 연결 확인
6. 런타임에서 private1/private2 확보
7. Python에서 Session Key 생성 및 복호화 검증

## 11. 검증 성공의 기준

최종적으로 다음 세 단계가 모두 맞아야 한다.

```
A. PCAP 구조
   Client public / Server public / ConvID 일치

B. DH 계산
   public == pow(g, private, p)
   secret1/secret2 생성
   16-byte key 생성

C. 암호화
   PCAP ciphertext 복호화
   PKCS7 정상 제거
   OpInfo protobuf 파싱 성공
```

C까지 성공하면 현재 추정한 DH64 -> TCPTube.Key -> Rijndael CBC 경로가 실제 통신 세션과 일치한다고 판단할 수 있다.

## 12. 상태

- [x] DH64 KeyPair 구조 확인
- [x] System.Random::Next 구조 확인
- [x] private key 조합 방식 확인
- [x] Client handshake 논리 구조 확인
- [x] Server handshake 구조 확인
- [x] Server public #1/#2 확인
- [x] 16-byte session key 조합 방식 확인
- [x] Rijndael CBC 수신 경로 확인
- [ ] 실제 PCAP에서 Client public #1/#2 추출
- [ ] Python PCAP validator 실행
- [ ] 런타임 private1/private2 확보
- [ ] session key 계산
- [ ] 실제 TCP ciphertext 복호화
- [ ] OpInfo protobuf 검증


---

# 2026-09-22 PCAP 실제 검증 결과 및 다음 작업

## 13. 실제 PCAP 파싱 결과

대상 PCAP:

`PCAPdroid_21_9월_13_26_19시작로그인인게임메인메뉴.pcap`

Python validator 실행 결과:

```
[PCAP] linktype=101 (RAW IPv4) size=83,643 bytes
[+] Parsed IPv4/TCP packets: 174
[+] TCP packets with payload: 73
```

따라서 이 PCAP은 Ethernet 캡처가 아니라 **RAW IPv4(linktype 101)** 형식이며, IPv4/TCP 패킷 파싱은 정상적으로 동작한다.

### 확인된 게임 TCP 연결

실제 게임 DH handshake가 확인된 연결:

```
Client
10.215.173.1:39490
        |
        | TCP
        v
Server
182.92.62.79:8000
```

## 14. Server handshake 실제 검증

PCAP packet 172에서 Server handshake 전체 37바이트가 하나의 TCP payload로 확인되었다.

```
packet=172
182.92.62.79:8000 -> 10.215.173.1:39490
payload=37

offset      = 0x0
length      = 0x19
marker      = 1
TCPConvID   = 0x632
serverPub1  = 0xca4d30dba4429f27
serverPub2  = 0x7164b27b3d91d781
```

이 결과는 Ghidra에서 분석한 Server handshake 구조와 정확히 일치한다.

| Offset | 실제 PCAP 값 | 의미 |
|---|---|---|
| +0x00 | 8 bytes zero | reserved |
| +0x08 | 0x19 | handshake length |
| +0x0C | 0x01 | marker |
| +0x0D | 0x632 | TCPConvID |
| +0x15 | ca4d30dba4429f27 | server public #1 |
| +0x1D | 7164b27b3d91d781 | server public #2 |

따라서 다음 두 가지가 실제 PCAP으로 검증되었다.

1. Ghidra에서 확인한 Server handshake offset이 실제 통신과 일치한다.
2. Ghidra에서 확인한 server public #1/#2 값이 실제 PCAP과 일치한다.

## 15. Client 후보 검색 결과

초기 packet 단위 검색에서는 다음 문제가 있었다.

### 15.1 별도 HTTPS 연결에서 발견된 후보

```
packet=88
10.215.173.1:44942 -> 101.33.100.149:443
payload=93

offset      = 0x35
clientPub1  = 0x6c87c88d74b22339
clientPub2  = 0xdf68532b1b06aab8
```

이 연결은 게임 DH 연결과 5-tuple이 다르므로 DH64 검증 대상에서 제외한다.

### 15.2 실제 게임 연결의 packet 단위 후보

packet 170:

```
10.215.173.1:39490 -> 182.92.62.79:8000
payload=373

clientPub1  = 0x1f594d0100000169
clientPub2  = 0xe8986e3637f5aba4
```

이 값은 당시에는 zero-prefix 탐색만으로 잡힌 후보였으므로 실제 handshake라고 확정하지 않았다.

## 16. TCP Stream Reassembly 구현

`pcap_dh_validator.py`에 다음 기능을 추가했다.

- TCP Sequence Number / ACK / Flags 추출
- 실제 게임 연결 5-tuple만 분석
- Client -> Server / Server -> Client 방향 분리
- Sequence 기준 정렬
- retransmission 중복 데이터 제거
- out-of-order segment 결합
- sequence gap은 임의의 0으로 채우지 않고 contiguous chunk로 분리
- 재조립된 Client stream에서 handshake 후보 검색
- `1 < public < p` 범위 검증
- 후보 주변 raw bytes 출력

실제 실행 결과:

```
[TCP STREAM REASSEMBLY]
  target = 10.215.173.1:39490 <-> 182.92.62.79:8000
  client payload segments = 4
  server payload segments = 3
  client contiguous chunks = 1
  server contiguous chunks = 1
  client stream seq=0xb8164724 length=373
  server stream seq=0x77eb77ec length=37
```

중요한 점은 **Client 방향 payload 4개가 하나의 contiguous stream으로 정확히 373바이트가 되었다는 것**이다.

## 17. Client handshake 실제 후보 확인

재조립된 Client stream에서 다음 후보가 확인되었다.

```
stream_seq  = 0xb8164724
offset      = 0x0
clientPub1  = 0x1f594d0100000169
clientPub2  = 0xe8986e3637f5aba4
remaining   = 373
bytes       = 00 00 00 00 00 00 00 00
              69 01 00 00 01 4d 59 1f
              a4 ab f5 37 36 6e 98 e8
              28 2a 92 44 fe 53 2f 4a
              33 4c 31 61 59 44 64 48
              41 46 71 37 38 6f 49 4a
```

### 17.1 현재 판단

이번 결과는 초기 packet 단위 후보와 의미가 다르다.

이제 후보는:

- 실제 게임 TCP 5-tuple
- Client -> Server 방향
- 재조립된 contiguous stream
- stream 시작 offset = `0x0`
- 앞 8바이트 = zero/reserved
- 다음 8바이트 = client public #1
- 다음 8바이트 = client public #2
- 뒤에 추가 handshake payload 존재
- 전체 Client stream 길이 = 373바이트

라는 조건을 **동시에 만족한다.**

따라서 현재 단계에서는 다음 값을 **실제 Client handshake의 강한 후보로 확정하여 기록한다.**

```
clientPublic1 = 0x1f594d0100000169
clientPublic2 = 0xe8986e3637f5aba4
```

단, 아직 private1/private2를 확보하지 않았으므로 DH 계산까지 검증된 것은 아니다.

### 17.2 추가 payload 길이

Ghidra에서 확인한 구조가:

```
+0x00  8 bytes zero
+0x08  client public #1
+0x10  client public #2
+0x18  additional payload
```

이고 전체 stream 길이가 373바이트이므로:

```
373 - 0x18 = 349 bytes
```

즉 현재 PCAP에서 Client handshake 후보의 추가 payload는 **349바이트**다.

앞부분은:

```
28 2a 92 44 fe 53 2f 4a
33 4c 31 61 59 44 41 46
71 37 38 6f 49 4a ...
```

로 시작한다.

이 추가 payload는 현재 단계에서 임의로 protobuf/문자열이라고 단정하지 않는다. 다음 단계에서 Ghidra의 `KCPTube::Handshake1`에서 `+0x18` 이후에 복사되는 실제 객체/버퍼의 생성 경로와 대조해야 한다.

## 18. 현재까지의 DH handshake 검증 상태

현재 실제 PCAP에서 확보된 값은 다음과 같다.

| 항목 | 값 | 상태 |
|---|---|---|
| Client endpoint | `10.215.173.1:39490` | 확인 |
| Server endpoint | `182.92.62.79:8000` | 확인 |
| TCPConvID | `0x632` | 확인 |
| Client public #1 | `0x1f594d0100000169` | 강한 후보 |
| Client public #2 | `0xe8986e3637f5aba4` | 강한 후보 |
| Server public #1 | `0xca4d30dba4429f27` | 확인 |
| Server public #2 | `0x7164b27b3d91d781` | 확인 |
| Client handshake total | 373 bytes | 확인 |
| Additional payload | 349 bytes | 구조상 계산 |
| Client private #1 | 미확보 | 다음 단계 |
| Client private #2 | 미확보 | 다음 단계 |
| Session Key | 미계산 | private 필요 |
| TCP 암호문 복호화 | 미실행 | session key 필요 |

### 검증 레벨

현재는 다음과 같이 분류한다.

- **확정:** Server handshake 구조/값
- **강한 후보:** Client public #1/#2
- **미확정:** Client private #1/#2
- **미검증:** DH secret / 16-byte session key / 암호문 복호화 / OpInfo

따라서 지금은 Client public을 기준으로 private를 역산하려고 하지 않고, **Ghidra의 KeyPair 출력과 실제 runtime 값을 연결하는 단계로 이동한다.**

## 19. 다음 작업: Ghidra와 Client public 연결

다음 분석 목표는 `KCPTube::Handshake1`에서 확인된 KeyPair 호출 직후 값을 실제 PCAP 값과 연결하는 것이다.

### 19.1 필요한 값

```
private1
private2
public1 = 0x1f594d0100000169
public2 = 0xe8986e3637f5aba4
```

### 19.2 가장 직접적인 runtime 관찰 위치

Ghidra 분석에서 `DH64::KeyPair`의 인자는 다음과 같이 동작한다.

```
param_1 -> private output
param_2 -> public output
```

따라서 `DH64::KeyPair` 함수 반환 직후 `param_1`과 `param_2`가 가리키는 8바이트 값을 관찰하면 된다.

두 번의 호출에 대해:

```
KeyPair #1
  private -> ?
  public  -> 0x1f594d0100000169

KeyPair #2
  private -> ?
  public  -> 0xe8986e3637f5aba4
```

가 되는지 확인한다.

### 19.3 runtime에서 private가 확보되면

바로 다음을 검증한다.

```
pow(5, private1, 0xFFFFFFFFFFFFFFC5)
    == 0x1f594d0100000169

pow(5, private2, 0xFFFFFFFFFFFFFFC5)
    == 0xe8986e3637f5aba4
```

그 다음:

```
secret1 = pow(0xca4d30dba4429f27, private1, p)
secret2 = pow(0x7164b27b3d91d781, private2, p)

sessionKey =
    LE64(secret1) || LE64(secret2)
```

순으로 진행한다.

## 20. 다음 PCAP 작업: 추가 payload 구조 확인

Client handshake 자체는 현재 강한 후보가 확보되었으므로, PCAP 쪽에서는 추가 payload 349바이트를 별도로 덤프하여 구조를 확인할 수 있다.

확인할 항목:

1. 349바이트가 단순 opaque payload인지
2. 길이/타입/버전 필드가 존재하는지
3. ASCII/UTF-8 문자열이 반복되는지
4. protobuf처럼 보이는 field tag가 존재하는지
5. Ghidra `Handshake1`의 additional payload 생성 함수와 byte-for-byte 대응하는지

단, 이 단계는 DH public 검증과 별개이므로 **추가 payload의 의미를 먼저 추측하지 않는다.**

## 21. 현재 전체 진행상태

```
[완료] Ghidra DH64 KeyPair 분석
        ↓
[완료] System.Random Next() 분석
        ↓
[완료] Client handshake 구조 분석
        ↓
[완료] Server handshake 구조 분석
        ↓
[완료] PCAP RAW IPv4 파싱
        ↓
[완료] 게임 TCP connection 식별
        ↓
[완료] Server handshake 실제 검증
        ↓
[완료] TCP stream reassembly
        ↓
[완료] Client handshake 강한 후보 추출
        ↓
[현재] Client public ↔ runtime KeyPair 연결
        ↓
[다음] private1/private2 확보
        ↓
[다음] DH secret 계산
        ↓
[다음] 16-byte session key 검증
        ↓
[다음] TCP ciphertext 복호화
        ↓
[다음] OpInfo protobuf 분석
```

### 2026-09-22 현재 핵심 값

```
p         = 0xFFFFFFFFFFFFFFC5
g         = 5

Client:
  10.215.173.1:39490

Server:
  182.92.62.79:8000

TCPConvID:
  0x632

clientPublic1:
  0x1f594d0100000169

clientPublic2:
  0xe8986e3637f5aba4

serverPublic1:
  0xca4d30dba4429f27

serverPublic2:
  0x7164b27b3d91d781

clientHandshakeLength:
  373 bytes

additionalPayload:
  349 bytes
```

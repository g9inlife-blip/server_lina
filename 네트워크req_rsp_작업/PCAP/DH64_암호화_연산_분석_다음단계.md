# 다음 분석 단계 — DH64 검증 완료 → Rijndael / PCAP 복호화

> 기준 문서: 네트워크req_rsp_작업/PCAP/DH64_암호화_연산_분석.md
> 목적: 지금까지 Ghidra에서 확인한 DH64 / TCP·KCP handshake 결과를 다음 분석 단계에서 바로 사용할 수 있도록 정리한다.

## 1. 현재 단계의 핵심 결론

이번 분석에서 가장 중요한 오해가 해소되었다.

기존에는 0x3B를 단순 modulus 59로 해석했지만, 실제 ARM64 연산에서는:

```text
p = 2^64 - 59
  = 0xFFFFFFFFFFFFFFC5
  = 18446744073709551557
```

이다. 따라서 DH64는 작은 mod 59가 아니라 64-bit modulus 2^64 - 59를 사용하는 구조다.

이 결과로 실제 PCAP의 64-bit public 값도 정상적인 DH public 값으로 설명된다.

```text
4d 59 1f a4 ab f5 37 36
6e 98 e8 28 2a 92 44 fe
```

Little Endian 기준:

```text
public #1 = 0x3637F5ABA41F594D
public #2 = 0xFE44922A28E8986E
```

## 2. DH64 전체 수식

### 2.1 Generator
```text
g = 5
```

### 2.2 Modulus
```text
p = 2^64 - 59
  = 0xFFFFFFFFFFFFFFC5
```

### 2.3 Private
DH64.KeyPair()에서 두 개의 Random 정수 반환값을 조합한다.

```text
private = ((uint64)R1 << 32) | ((uint32)R2 + 1)
```

### 2.4 Public
DH64.PublicKey()는 다음을 수행한다.

```text
public = powmodp(5, private)
       = 5^private mod (2^64 - 59)
```

### 2.5 Shared Secret
DH64.Secret()는 peer public을 base, local private를 exponent로 사용한다.

```text
secret = powmodp(peerPublic, localPrivate)
       = peerPublic^localPrivate mod (2^64 - 59)
```

일반적인 DH 관계:

```text
A = 5^a mod p
B = 5^b mod p
S = B^a mod p = A^b mod p
```

게임에서는 이 계산을 두 번 수행한다.

```text
A1 = 5^a1 mod p
B1 = 5^b1 mod p
S1 = B1^a1 mod p

A2 = 5^a2 mod p
B2 = 5^b2 mod p
S2 = B2^a2 mod p
```

## 3. mul_mod_p() 분석 결과

DH64.mul_mod_p()는 일반적인 64-bit 곱셈 후 나머지 연산을 직접 사용하지 않는다. 대신 double-and-add 방식의 modular multiplication을 구현한다.

개념적으로:

```c
uint64_t mul_mod_p(uint64_t a, uint64_t b)
{
    uint64_t result = 0;

    while (b != 0)
    {
        if (b & 1)
            result = mod_add(result, a);

        a = mod_add(a, a);
        b >>= 1;
    }

    return result;
}
```

여기서 mod_add(a,b) = (a+b) mod (2^64 - 59)이다.

핵심 Assembly는 mov x9,#-0x3b이다. ARM64 64-bit 정수에서 -0x3B는 0xFFFFFFFFFFFFFFC5 = 2^64 - 59로 해석된다.

따라서 0x3B가 작은 modulus 자체가 아니라 2^64 - 59를 만들기 위한 값이라는 점이 핵심이다.

## 4. pow_mod_p() 분석 결과

pow_mod_p()는 recursive binary exponentiation / square-and-multiply 구조다.

```c
uint64_t pow_mod_p(uint64_t base, uint64_t exponent)
{
    if (exponent == 1)
        return base;

    uint64_t half = pow_mod_p(base, exponent >> 1);
    uint64_t result = mul_mod_p(half, half);

    if (exponent & 1)
        result = mul_mod_p(result, base);

    return result;
}
```

따라서 pow_mod_p(base, exponent) = base^exponent mod (2^64 - 59)이다.

## 5. PublicKey()와 Secret() 확정

PublicKey() Assembly:

```asm
015aa21c  mov w0,#0x5
015aa220  b   Alioth.S1.Common.DH64$$powmodp
```

즉 PublicKey(private) → powmodp(5, private)이다.

Secret() Assembly:

```asm
015aa224  mov x0,x2
015aa228  b   Alioth.S1.Common.DH64$$powmodp
```

즉 Secret(peerPublic, localPrivate) → powmodp(peerPublic, localPrivate)이다.

## 6. TCP Handshake 구조 확정

TCPTube.Update()에서 두 번의 DH64.KeyPair()를 생성한다.

```text
param_1 + 0x58 → private #1
param_1 + 0x60 → private #2
stack → public #1
stack → public #2
```

그리고 public을 packet buffer에 복사한다.

```text
offset  size  meaning
0x00     8    zero
0x08     4    handshake length
0x0C     1    marker = 1
0x0D     8    public #1
0x15     8    public #2
0x1D     N    param4
```

## 7. 실제 PCAP과 대조

관찰된 TCP payload:

```text
00 00 00 00 00 00 00 00
69 01 00 00
01
4d 59 1f a4 ab f5 37 36
6e 98 e8 28 2a 92 44 fe
...
```

크기는 373 bytes이며 0x169 = 361, 361 = 17 + 344이다. 따라서 0x08 length, 0x0C marker, 0x0D public #1, 0x15 public #2, 0x1D param4 구조와 일치한다.

## 8. KCP Handshake 교차 검증

KCPTube.Handshake1()은 private #1/#2를 각각 +0x58/+0x60에 저장하고 public #1/#2를 local_28/local_30에 받은 뒤 packet의 +0x08/+0x10에 기록한다.

KCPTube.Handshake2()는 상대방 packet의 +0x11/+0x19에서 peer public #1/#2를 읽고 각각 Secret()을 계산한다.

따라서 TCP와 KCP 모두 동일한 DH64 session-key 개념을 사용하며, handshake wire layout만 다르다.

## 9. 16-byte Session Key

두 DH secret은 각각 8 byte로 변환되어 key buffer의 앞/뒤에 기록된다.

```text
key[0:8]  = BitConverter.GetBytes(secret1)
key[8:16] = BitConverter.GetBytes(secret2)
session_key = LE64(secret1) || LE64(secret2)
```

총 16 bytes다.

## 10. 네트워크 암호화 구조

현재 코드에서 확인된 TCP 수신 흐름:

```text
TCP frame
 ↓
length
 ↓
flags
 ↓
payload
 ↓
0x80 Encrypt?
 ↓ yes
Tools.DecryptUnSafe()
 ↓
IV 16 bytes 추출
 ↓
RijndaelManaged.CreateDecryptor(key, IV)
 ↓
plaintext
 ↓
0x40 Compress?
 ↓ yes
decompress
 ↓
protobuf OpInfo
```

암호화 payload는 [16-byte IV][ciphertext] 구조다.

## 11. Flags
```text
0x80 = Encrypt
0x40 = Compress
```

## 12. Rijndael에서 아직 확인해야 하는 것

현재 확인된 것:

```text
key = 16 bytes
IV  = payload 앞 16 bytes
decryptor = RijndaelManaged.CreateDecryptor(key, IV)
```

아직 코드로 확정하지 않은 것:

```text
BlockSize
KeySize
Mode
Padding
```

다음 Ghidra 검색 대상:

```text
Alioth.S1.Net.Tools::.cctor
Alioth.S1.Net.Tools$$DecryptUnSafe
Alioth.S1.Net.Tools$$EncryptUnSafe
```

특히 RijndaelManaged.set_BlockSize / set_KeySize / set_Mode / set_Padding / CreateEncryptor / CreateDecryptor 호출을 찾는다.

추측으로 AES 기본값을 적용하지 않는다.

## 13. 실제 복호화에 필요한 PCAP 데이터

실제 session key를 만들려면 양쪽 DH public 값이 필요하며, 한쪽의 local private가 있으면 peer public으로 secret을 계산할 수 있다.

```text
secret1 = peerPublic1^localPrivate1 mod p
secret2 = peerPublic2^localPrivate2 mod p
session_key = LE64(secret1) || LE64(secret2)
```

PCAP만으로 private을 직접 복구하는 문제는 별도 분석 대상이다. 따라서 실행 중인 프로세스의 DH private/public 값과 PCAP handshake를 연결하는 방법도 고려한다.

## 14. 다음 작업 우선순위

### 1순위 — Rijndael 설정
Tools::.cctor에서 BlockSize, KeySize, Mode, Padding을 확정한다.

### 2순위 — PCAP TCP stream 재조립
4-tuple, TCP sequence number를 이용해 stream을 재조립하고 handshake/frame 경계를 분리한다.

### 3순위 — DH handshake 자동 추출
client/server 방향을 판별하고 public #1/#2를 자동 추출한다.

### 4순위 — Session Key 검증
두 secret을 계산하고 16-byte key를 생성한다.

### 5순위 — Rijndael 복호화
payload 앞 16-byte IV를 분리하고 ciphertext를 복호화한다.

### 6순위 — Compression / protobuf
0x40이면 decompress한 뒤 OpInfo를 복원한다.

### 7순위 — Request / Response 구조화
OperationCode를 기준으로 login, dungeon, draw/gacha, shop, reward 등의 request/response를 연결한다.

## 15. 현재 분석 상태

| 항목 | 상태 |
|---|---|
| DH64 사용 | 확정 |
| Generator g=5 | 확정 |
| Modulus p=2^64-59 | 확정 |
| Private 생성 방식 | 확인 |
| PublicKey 계산 | 확정 |
| Secret 계산 | 확정 |
| DH 2회 수행 | 확정 |
| 16-byte session key | 확정 |
| TCP handshake layout | 확정 |
| KCP handshake layout | 확인 |
| PCAP과 TCP layout 대조 | 일치 |
| Encrypt flag 0x80 | 확정 |
| Compress flag 0x40 | 확정 |
| IV 16 bytes | 확정 |
| Tools.DecryptUnSafe() | 확정 |
| Rijndael 사용 | 확정 |
| BlockSize | 미확정 |
| KeySize | 미확정 |
| Mode | 미확정 |
| Padding | 미확정 |
| PCAP 실제 decrypt | 다음 단계 |
| protobuf OpInfo 복원 | 이후 |
| request/response mapping | 이후 |

## 16. 다음 문서를 읽는 사람을 위한 시작점

이 문서 다음 분석은 DH64를 다시 분석하는 것이 아니라 바로 다음 Ghidra 함수부터 확인한다.

```text
1. Alioth.S1.Net.Tools::.cctor
2. Alioth.S1.Net.Tools$$DecryptUnSafe
3. Alioth.S1.Net.Tools$$EncryptUnSafe
```

목표:

```text
RijndaelManaged
 ├─ BlockSize
 ├─ KeySize
 ├─ Mode
 ├─ Padding
 └─ CreateDecryptor(key, IV)
```

그 다음 PCAP TCP stream을 재조립하고 실제 handshake → session key → ciphertext를 연결한다.

## 17. 최종 구조

```text
DH64
 │
 ├─ g = 5
 ├─ p = 2^64 - 59
 │
 ├─ KeyPair #1 → private1 / public1
 └─ KeyPair #2 → private2 / public2
                  │
                  ▼
            TCP Handshake
                  │
            peer public 수신
                  │
             ┌────┴────┐
             ▼         ▼
          Secret #1  Secret #2
             │         │
             └────┬────┘
                  ▼
           16-byte session key
                  │
                  ▼
              Rijndael
                  │
          IV = payload[0:16]
                  ▼
           decrypted data
                  │
             decompress?
                  │
                  ▼
                OpInfo
                  │
                  ▼
          request / response
                  │
          login/dungeon/draw/etc.
```

## 18. 한 줄 결론

DH64의 실제 modulus는 59가 아니라 2^64-59이며, 이를 통해 Ghidra의 DH64 코드와 실제 TCP PCAP의 64-bit public 값이 일치하는 것으로 정리되었다. 다음 작업은 DH64를 다시 분석하는 것이 아니라 Tools::.cctor에서 Rijndael 설정을 확정하고 실제 PCAP 복호화로 검증하는 것이다.

---

# 19. 2026-09-21 추가 분석 — RijndaelManagedTransform / DecryptUnSafe 확정

이번 단계에서 Ghidra로 `RijndaelManagedTransform::.ctor`, `RijndaelManaged$$NewEncryptor`, `Tools$$DecryptUnSafe`, `DataTool$$DecryptUnSafe`를 추가 분석했다. 이 결과 기존에 미확정이었던 실제 복호화 처리 흐름을 대부분 확정했다.

## 19.1 RijndaelManagedTransform 생성자 인자 순서 확정

`RijndaelManaged$$NewEncryptor()`에서 다음 순서로 `RijndaelManagedTransform::.ctor()`를 호출한다.

```text
ctor(transform, key, mode, IV, blockSize, padding, feedbackSize, encrypt)
```

`RijndaelManagedTransform::.ctor()` 내부 저장 위치:

```text
Transform +0x10 = Mode
Transform +0x14 = Padding
Transform +0x18 = Encrypt/Decrypt flag
Transform +0x1C = BlockSize
```

`NewEncryptor()`는 `RijndaelManaged` 객체에서 다음 값을 가져와 전달한다.

```text
RijndaelManaged +0x10 → BlockSize
RijndaelManaged +0x14 → Padding
RijndaelManaged +0x3C → Mode
RijndaelManaged +0x40 → FeedbackSize
RijndaelManaged +0x38 → KeySize (key가 NULL일 때 random key 길이 계산)
```

## 19.2 Tools::.cctor 설정값 확정

`Tools::.cctor()`에서 RijndaelManaged 생성 후 설정하는 값은 다음과 같다.

```text
1
2
0x80
```

이번 Transform ctor 분석 및 `DataTool$$DecryptUnSafe()`의 동일한 호출 구조와 교차검증하여 실제 설정을 다음과 같이 정리한다.

```text
Mode         = CBC
Padding      = PKCS7
FeedbackSize = 128 bits
```

또한 Transform 내부의 실제 블록 처리 크기가 16 bytes임을 별도로 확인했다.

## 19.3 BlockSize = 128 bits 확정

Transform ctor에서:

```text
BlockSize = param_5
BlockSize / 8 = Transform +0x20
Nb = BlockSize / 32 = Transform +0x44
```

그리고 `NewEncryptor()`에서 `param_5`는 `RijndaelManaged +0x10`에서 가져온다.

실제 `Tools$$DecryptUnSafe()`와 `DataTool$$DecryptUnSafe()` 모두 ICryptoTransform에 대해 `0x10` 바이트 단위의 `TransformBlock()`을 반복 호출한다.

따라서 실제 네트워크 암복호화 블록은:

```text
128 bits = 16 bytes
```

이다.

## 19.4 CreateEncryptor / CreateDecryptor 방향 확정

`RijndaelManaged$$CreateEncryptor()`:

```text
NewEncryptor(..., encrypt = 0)
```

`RijndaelManaged$$CreateDecryptor()`:

```text
NewEncryptor(..., encrypt = 1)
```

따라서 Transform +0x18의 의미는:

```text
0 = Encrypt
1 = Decrypt
```

이다.

## 19.5 Tools.DecryptUnSafe() 실제 처리

함수 인자는 다음 의미다.

```text
param_1 = encrypted input byte[]
param_2 = key byte[]
param_3 = output MemoryStream
```

첫 번째 단계에서 input의 앞 16 bytes를 Tools static byte[16]으로 복사한다.

```text
IV = encrypted[0:16]
ciphertext = encrypted[16:]
```

그 다음 static `RijndaelManaged`에 대해:

```text
CreateDecryptor(key, IV)
```

를 호출한다.

암호문은 16-byte 단위로 `ICryptoTransform.TransformBlock()`을 반복 수행한다.

남은 데이터는 별도의 `ICryptoTransform` final-transform 호출로 처리한다. 이는 `TransformFinalBlock()`에 해당하며 마지막 블록의 PKCS7 padding 처리를 담당한다.

복호화 결과는 `param_3`의 `MemoryStream.Write()` 계열 호출로 기록된다.

마지막으로 `ICryptoTransform`에 대해 `IDisposable.Dispose()`를 호출한다.

전체 흐름:

```text
encrypted input
    ↓
first 16 bytes = IV
    ↓
CreateDecryptor(key, IV)
    ↓
TransformBlock × N
    ↓
TransformFinalBlock
    ↓
MemoryStream
    ↓
plaintext
    ↓
Dispose
```

## 19.6 DataTool.DecryptUnSafe() 독립 교차검증

`DataTool$$DecryptUnSafe()`는 Tools와 달리 매번 `RijndaelManaged` 객체를 새로 생성하지만 동일한 복호화 구조를 사용한다.

확인된 순서:

```text
new RijndaelManaged()
Mode = 1
Padding = 2
input[0:16] → IV
CreateDecryptor(key, IV)
TransformBlock(..., 0x10)
TransformFinalBlock(...)
MemoryStream.Write(...)
Dispose()
```

또한 복호화 결과용 `byte[0x800]` 버퍼를 생성한다.

따라서 Tools의 static Rijndael 사용이 특수한 별도 알고리즘이 아니라 DataTool과 동일한 Rijndael 복호화 규칙을 사용하는 것으로 교차검증된다.

## 19.7 암호화 payload 구조 최종 정리

현재까지의 코드 증거를 모두 합치면 암호화 payload는 다음 구조다.

```text
+----------------+---------------------------+
| IV 16 bytes    | Rijndael CBC ciphertext  |
+----------------+---------------------------+
        0x00              0x10 →
```

암호화:

```text
plaintext
  ↓
RijndaelManaged
  ├─ BlockSize = 128 bits
  ├─ Mode = CBC
  └─ Padding = PKCS7
  ↓
IV + ciphertext
```

복호화:

```text
IV + ciphertext
  ↓
IV = first 16 bytes
  ↓
CreateDecryptor(key, IV)
  ↓
plaintext
```

## 19.8 DH64 → Rijndael 연결

현재 네트워크 암호화 전체 구조는 다음과 같이 정리된다.

```text
DH64
 ├─ g = 5
 ├─ p = 2^64 - 59
 ├─ KeyPair #1
 └─ KeyPair #2
       ↓
peer public 수신
       ↓
Secret #1 / Secret #2
       ↓
LE64(secret1) || LE64(secret2)
       ↓
16-byte session key
       ↓
RijndaelManaged
 ├─ Key = 16 bytes
 ├─ BlockSize = 128 bits
 ├─ Mode = CBC
 ├─ Padding = PKCS7
 └─ IV = payload[0:16]
       ↓
plaintext
       ↓
Compress flag 확인
       ↓
decompress
       ↓
protobuf / OpInfo
```

## 19.9 현재 미확정 사항

암호화 알고리즘 자체는 충분히 정리되었지만 다음은 실제 데이터 검증이 필요하다.

```text
1. 실제 runtime 16-byte session key 확보
2. PCAP encrypted frame과 key/IV 연결
3. 실제 ciphertext 복호화 성공 확인
4. 0x40 Compress flag의 실제 압축 알고리즘 확인
5. plaintext protobuf 구조 확인
6. OpInfo field / OperationCode 분석
7. request / response correlation
```

PCAP에 있는 DH public 값만으로는 session key를 바로 계산할 수 없으므로, 가장 직접적인 검증 지점은 실행 중 `CreateDecryptor(key, IV)` 호출 시점의 key 확보 또는 `KCPTube/TCPTube`의 생성된 16-byte key 확보이다.

## 19.10 다음 작업 순서

```text
[완료]
DH64 수학 구조
TCP/KCP handshake
Rijndael 설정
DecryptUnSafe 흐름
        ↓
[다음]
runtime session key 확보
        ↓
PCAP stream 재조립
        ↓
encrypted frame 자동 분리
        ↓
Rijndael-CBC 복호화
        ↓
압축 여부 확인
        ↓
protobuf / OpInfo 분석
        ↓
REQ/RSP 구조화
```

### 핵심 함수

```text
Alioth.S1.Common.DH64$$KeyPair
Alioth.S1.Common.DH64$$PublicKey
Alioth.S1.Common.DH64$$Secret
Alioth.S1.Common.DH64$$mul_mod_p
Alioth.S1.Common.DH64$$pow_mod_p
Alioth.S1.Net.TCPTube$$Update
Alioth.S1.Net.KCPTube$$Handshake1
Alioth.S1.Net.KCPTube$$Handshake2
Alioth.S1.Net.Tools$$.cctor
Alioth.S1.Net.Tools$$EncryptUnSafe
Alioth.S1.Net.Tools$$DecryptUnSafe
System.Security.Cryptography.RijndaelManaged$$CreateEncryptor
System.Security.Cryptography.RijndaelManaged$$CreateDecryptor
System.Security.Cryptography.RijndaelManaged$$NewEncryptor
System.Security.Cryptography.RijndaelManagedTransform$$.ctor
DataTool$$DecryptUnSafe
```

## 19.11 분석 기준 변경

이전 문서의 "Rijndael 설정 미확정" 부분은 이번 분석 결과로 갱신되었다.

현재부터는 다음 값을 기준값으로 사용한다.

```text
Rijndael
  Key       = 16 bytes
  BlockSize = 128 bits
  Mode      = CBC
  Padding   = PKCS7
  IV        = first 16 bytes of encrypted payload
```

따라서 이후 PCAP 분석에서 AES/Rijndael 설정을 다시 추측하지 않고, 위 설정을 기본 검증 조건으로 사용한다.


# 20. 2026-09-21 추가 — 실제 PCAP 분석 및 암호화 확인

이번 단계에서는 실제 게임 실행 중 수집한 PCAP을 대상으로 TCP/KCP handshake와 암호화 payload 구조를 확인했다.

## 20.1 PCAP 기본 정보

분석 대상 PCAP은 약 81.7 KB, 총 211 packet 규모다.

확인된 주요 통신:

~~~text
TCP
10.215.173.1:39490 ↔ 182.92.62.79:8000

UDP/KCP
10.215.173.1:33922 ↔ 182.92.62.79:8000
~~~

## 20.2 실제 TCP DH handshake 대조

PCAP에서 확인된 client TCP handshake:

~~~text
00 00 00 00 00 00 00 00
69 01 00 00
01
4d 59 1f a4 ab f5 37 36
6e 98 e8 28 2a 92 44 fe
...
~~~

해석:

~~~text
0x00      8 bytes   zero
0x08      4 bytes   length = 0x169 = 361
0x0C      1 byte    marker = 1
0x0D      8 bytes   client DH public #1
0x15      8 bytes   client DH public #2
0x1D      344 bytes param4
~~~

Little Endian 기준:

~~~text
public #1 = 0x3637F5ABA41F594D
public #2 = 0xFE44922A28E8986E
~~~

전체 payload 크기는 373 bytes이며:

~~~text
8 + 4 + 1 + 8 + 8 + 344 = 373
~~~

로 정확히 맞는다.

따라서 Ghidra에서 확인한 TCPTube$$Update()의 handshake layout과 실제 PCAP이 일치한다.

## 20.3 실제 TCP server handshake

서버 방향에서는 다음 구조를 확인했다.

~~~text
length = 0x19
marker = 1
TCPConvID = 0x632
server DH public #1 = 0xCA4D30DBA4429F27
server DH public #2 = 0x7164B27B3D91D781
~~~

따라서 TCP handshake 단계에서 양방향 DH public 값이 실제로 교환되고 있음을 확인했다.

## 20.4 TCP handshake의 추가 데이터

client handshake의 0x1D 이후 344 bytes는 ASCII/Base64 형태로 보이는 데이터다.

분석 결과:

~~~text
Base64 문자 수 = 344
Base64 decode 결과 = 256 bytes
~~~

256-byte binary라는 크기 때문에 RSA-2048 ciphertext와 같은 형태를 연상할 수 있지만, 현재 단계에서는 RSA 사용이라고 확정하지 않는다.

이 데이터는 향후 로그인/인증 관련 handshake parameter인지 확인해야 한다.

## 20.5 KCP handshake도 실제 PCAP에서 확인

UDP/KCP handshake에서도 두 개의 DH public 값이 교환된다.

확인된 값:

~~~text
client KCP public #1 = 0x3B235655562743FA
client KCP public #2 = 0xD4BED6816A9F1C5C

server KCP public #1 = 0x7637ACF954E564B3
server KCP public #2 = 0xDD73013D938774B9

KCP ConvID = 0x07E669FDD645EE1E
~~~

이는 Ghidra에서 확인한 KCPTube$$Handshake1() / Handshake2() 구조와 실제 통신이 대응한다는 추가 증거다.

## 20.6 실제 게임 payload는 암호화되어 있음

가장 중요한 확인 결과다.

PCAP의 application-level KCP payload에서 다음 형태가 반복적으로 관찰되었다.

~~~text
[16-byte IV][ciphertext]
~~~

예:

~~~text
IV =
3b 8d 6a 1f f4 43 c3 7b
38 a4 51 38 3a 5b 03 f1

ciphertext = 176 bytes
~~~

176 bytes는 16-byte block의 11개 블록이다.

다른 후보 payload에서도:

~~~text
[1-byte prefix][16-byte IV][192-byte ciphertext]
~~~

형태가 관찰되었다.

192 bytes 역시 16-byte block 12개다.

따라서 실제 application payload가 단순 평문 protobuf가 아니라 암호화된 ciphertext라는 점을 PCAP 자체에서도 확인할 수 있다.

## 20.7 단, 모든 네트워크 데이터가 암호화되는 것은 아님

다음 데이터는 handshake/framing 단계에서 평문으로 확인된다.

~~~text
TCP/KCP header
length
flags
ConvID
DH public values
handshake parameter
~~~

정확한 표현은 다음과 같다.

~~~text
handshake 및 framing metadata 일부는 평문
게임 application payload는 암호화
~~~

## 20.8 Ghidra 코드와 PCAP의 연결

현재 확보된 증거를 하나로 연결하면:

~~~text
DH64 KeyPair
      ↓
public #1 / public #2
      ↓
TCP/KCP handshake
      ↓
peer public 수신
      ↓
DH64 Secret #1/#2
      ↓
LE64(secret1) || LE64(secret2)
      ↓
16-byte session key
      ↓
RijndaelManaged
      ↓
CBC / PKCS7 / 128-bit block
      ↓
[16-byte IV][ciphertext]
      ↓
DecryptUnSafe()
      ↓
plaintext
      ↓
Compress flag
      ↓
protobuf / OpInfo
~~~

따라서 현재 단계에서는 DH64 → 16-byte session key → Rijndael → encrypted payload 연결을 실제 PCAP과 Ghidra 양쪽에서 확인한 상태다.

## 20.9 PCAP 분석 도구 작성

실제 PCAP 분석을 반복하기 위해 다음 Python 도구를 추가했다.

~~~text
네트워크req_rsp_작업/PCAP/pcap_analyzer.py
~~~

이 도구는 외부 패킷 분석 라이브러리에 의존하지 않고 표준 Python만으로 다음 작업을 수행한다.

~~~text
PCAP 읽기
 ├─ Ethernet / IPv4
 ├─ TCP parsing
 ├─ UDP parsing
 ├─ TCP sequence reassembly
 ├─ TCP handshake candidate 추출
 ├─ KCP packet parsing
 ├─ DH public candidate 추출
 ├─ encrypted payload candidate 탐지
 └─ Base64 탐지
~~~

현재 도구는 PCAP을 복호화하지 않는다.

또한 현재 KCP fragment를 완전한 application message 단위로 재조립하는 기능은 다음 단계 작업으로 남겨두었다.

## 20.10 현재 PCAP 분석 결과

| 항목 | 결과 |
|---|---|
| PCAP 읽기 | 완료 |
| TCP stream 분석 | 완료 |
| TCP DH handshake 탐지 | 완료 |
| TCP public #1/#2 추출 | 완료 |
| TCP server public 값 확인 | 완료 |
| KCP handshake 탐지 | 완료 |
| KCP DH public 값 확인 | 완료 |
| KCP ConvID 확인 | 완료 |
| 암호화 payload 후보 탐지 | 완료 |
| IV 16 bytes 구조 확인 | 완료 |
| ciphertext 16-byte block 정렬 확인 | 완료 |
| 실제 session key 확보 | 미완료 |
| 실제 PCAP 복호화 | 미완료 |
| KCP fragment 완전 재조립 | 다음 단계 |
| compression 해제 | 이후 |
| protobuf / OpInfo 복원 | 이후 |
| REQ/RSP mapping | 이후 |

## 20.11 가장 중요한 현재 결론

현재까지는 다음 문장을 분석 기준으로 사용한다.

> 실제 게임 application payload는 암호화되어 전달되며, Ghidra 분석상 DH64로 생성된 16-byte session key를 사용해 RijndaelManaged CBC/PKCS7 방식으로 암호화되고 payload 앞 16 bytes가 IV로 사용된다.

단, 실제 PCAP의 ciphertext를 평문으로 복원하려면 실행 중 생성된 session key가 필요하다.

따라서 다음 단계의 핵심은 PCAP을 더 분석하는 것만이 아니라 실행 중인 게임 프로세스에서 실제 16-byte key를 확보하고 PCAP의 암호문과 연결하여 복호화 성공 여부를 검증하는 것이다.

## 20.12 다음 작업

우선순위는 다음과 같이 변경한다.

~~~text
1. KCP fragment reassembly
       ↓
2. encrypted application message 목록 정리
       ↓
3. runtime에서 16-byte session key 확보
       ↓
4. key + PCAP IV + ciphertext 연결
       ↓
5. Rijndael CBC/PKCS7 복호화
       ↓
6. plaintext 구조 확인
       ↓
7. 0x40 compression 확인
       ↓
8. protobuf / OpInfo 분석
       ↓
9. OperationCode 추출
       ↓
10. login / dungeon / draw / shop / reward
    REQ ↔ RSP mapping
~~~

이후부터는 단순히 암호화되어 있을 것이라는 가정이 아니라, Ghidra 코드와 실제 PCAP의 양쪽 증거를 기준으로 runtime key를 확보하여 실제 복호화를 검증하는 단계로 진행한다.

# 2026-09-30 KCP DH64 Key Recovery 및 PCAP 실제 복호화

## 1. 목적

기존 분석에서 남아 있던 핵심 미확인 항목:

```text
KCPTube.Handshake2
  -> DH64.Secret #1/#2
  -> 16-byte KCPTube.Key
  -> encrypted KCP application payload
```

을 실제 `research/PCAP/챕터선택_전투승리보상까지.json`과 Ghidra Listing으로 검증한다.

함수명 검색 규칙은 기존 프로젝트 기준을 유지한다.

- 함수명 앞 2글자 기준 디렉터리
- `<`, `>`, `$` 등 파일명 불가 문자는 `_` 치환
- 예: `Alioth.S1.Net.KCPTube$$Handshake2`
  -> `Ghidra_Listing_txt/AL/015b1f68_Alioth.S1.Net.KCPTube__Handshake2.txt`

## 2. 핵심 정정 — modulus는 59가 아님

`DH64$$pow_mod_p @ 015a9fe0`에서:

```asm
015aa014  mov x9,#-0x3b
...
015aa064  mov x9,#-0x3b
```

ARM64 unsigned 64-bit에서 `-0x3B`는:

```text
0xFFFFFFFFFFFFFFC5
= 2^64 - 59
```

이다.

따라서 실제 DH modulus:

```text
p = 0xFFFFFFFFFFFFFFC5
  = 18446744073709551557
```

이며 `59` 자체가 modulus가 아니다.

## 3. Handshake2에서 Key 생성 구조 직접 확정

`KCPTube$$Handshake2 @ 015b1f68`:

```text
015b2024  mov w1,#0x11
015b202c  mov x2,xzr
015b2030  bl  BitConverter.ToUInt64
015b2038  mov x21,x0

015b203c  mov w1,#0x19
015b2044  mov x0,x8
015b2048  bl  BitConverter.ToUInt64
015b2058  mov x20,x0

015b2054  ldr x1,[x19,#0x58]
015b2060  mov x2,x21
015b2068  bl   DH64.Secret

015b2074  ldr x1,[x19,#0x60]
015b2080  mov x21,x0
015b2088  mov x2,x20
015b2090  bl   DH64.Secret
015b2094  mov x20,x0
```

즉:

```text
peer public #1 = UInt64(packet + 0x11)
peer public #2 = UInt64(packet + 0x19)

secret1 = Secret(localPrivate1, peerPublic1)
secret2 = Secret(localPrivate2, peerPublic2)
```

`DH64$$Secret @ 015aa224`는:

```asm
015aa224  mov x0,x2
015aa228  b 0x015aa0a8
```

이므로 실제 수식은:

```text
secret = powmodp(peerPublic, localPrivate)
       = peerPublic^localPrivate mod (2^64 - 59)
```

## 4. 16-byte Key 조합도 직접 확정

Handshake2의 후반:

```text
015b2098  mov x0,x21
015b209c  mov x1,xzr
015b20a0  bl  BitConverter.GetBytes

015b20a8  mov x0,x19
015b20ac  bl  KCPTube.get_Key
015b20b4  mov x2,x0
015b20b8  mov w4,#0x8
015b20c0  mov w3,wzr
015b20c8  bl  Buffer.BlockCopy

015b20cc  mov x0,x20
015b20d0  mov x1,xzr
015b20d4  bl  BitConverter.GetBytes

015b20dc  mov x0,x19
015b20e0  bl  KCPTube.get_Key
015b20e8  mov w3,#0x8
015b20ec  mov w4,#0x8
015b20f8  mov x5,xzr
015b20fc  bl  Buffer.BlockCopy
```

따라서:

```text
Key[0:8]  = LE64(secret1)
Key[8:16] = LE64(secret2)

Key = LE64(secret1) || LE64(secret2)
```

은 이제 **직접 assembly로 확정**한다.

## 5. 중요한 추가 발견 — runtime private 없이 PCAP public에서 private residue 복구 가능

DH modulus:

```text
p - 1 = 2^64 - 60
     = 4 × 11 × 137 × 547 × 5594472617641
```

을 factorization할 수 있다.

또한 generator `g=5`의 실제 order를 확인한 결과:

```text
ord_p(5) = p - 1
```

즉 5는 이 군에서 full-order generator다.

따라서:

```text
public = 5^private mod p
```

에서 discrete logarithm:

```text
private = log_5(public) mod (p-1)
```

을 구하면 된다.

현재 PCAP의 KCP client public 두 값에 대해 discrete log을 계산했다.

```text
KCP client public #1 = 0x3B235655562743FA
private1 mod (p-1) = 0x12499F5C0DDB1AF5

KCP client public #2 = 0xD4BED6816A9F1C5C
private2 mod (p-1) = 0x6D0F828A5EA102C2
```

두 residue 모두 실제 uint64 private 범위에서 `residue + (p-1)` 후보가 uint64 범위를 초과하므로, 이 PCAP 세션에서는 residue 자체가 유일한 uint64 private 값이다.

따라서 runtime hook 없이도 이 PCAP의 KCP session key를 계산할 수 있다.

## 6. KCP session key 실제 계산

PCAP server public:

```text
server public #1 = 0x7637ACF954E564B3
server public #2 = 0xDD73013D938774B9
```

계산:

```text
secret1 = pow(serverPublic1, private1, p)
        = 0xEB751E69D959ADC0

secret2 = pow(serverPublic2, private2, p)
        = 0xAD53F6266C3490EA
```

Little Endian 조합:

```text
LE64(secret1) = c0 ad 59 d9 69 1e 75 eb
LE64(secret2) = ea 90 34 6c 26 f6 53 ad

KCP session key =
c0ad59d9691e75ebea90346c26f653ad
```

## 7. PCAP frame 159 실제 복호화

frame 159:

```text
client -> server
KCP sn = 0x05
application length = 81

application:
  flag = 0x80
  IV   = 5710e3494fa79b32be5d738c23d85593
  ciphertext = 64 bytes
```

위 KCP session key와 Rijndael/AES-128-CBC를 적용하면 PKCS7 복호화가 정상 성공한다.

복호화 plaintext:

```text
08 af ad 87 cf 06
10 17
22 0b
  08 a4 d2 a8 d7 c0 fb cb 3f
  10 05
f2 01 21
08 01
1a 07 08 e8 c4 e2 05 10 01
1a 07 08 88 bb e2 04 10 04
1a 07 08 ab d6 f4 04 10 01
20 02
28 02
```

중요하게 `OpInfo +0x14 = OpCode`가 Ghidra getter로 직접 확인되어 있고:

```text
get_OpCode @ 015aac6c
ldr h/w0,[x0,#0x14]
```

protobuf field #2가 `0x17 = 23`으로 확인된다.

## 8. frame 162 + 163 실제 복호화

KCP:

```text
frame 162
  frg = 1
  sn  = 0x11
  data = 1372

frame 163
  frg = 0
  sn  = 0x12
  data = 453
```

두 fragment의 application data를 재조립하면:

```text
total = 1825 bytes

flag = 0xC4
IV   = f0862cf0271983b553998be415226aee
ciphertext = 1808 bytes
```

여기서 `0xC4`는:

```text
0x80 Encrypt
0x40 Compress
0x04 additional flag/state bit
```

로 볼 수 있으며, 적어도 `0x80`과 `0x40`이 동시에 set되어 있다는 점은 실제 복호화 결과로 확인된다.

Rijndael/AES-128-CBC + PKCS7 복호화 성공:

```text
ciphertext 1808 bytes
        ↓
plaintext 1800 bytes
```

복호화 결과 첫 10 bytes:

```text
1f 8b 08 00 00 00 00 00 00 03
```

즉 gzip stream이다.

## 9. Compress flag 검증

gzip 해제 결과:

```text
1800-byte plaintext
        ↓ gzip
5749-byte decompressed data
```

따라서 이번 실제 응답에서:

```text
0xC4
 ├─ 0x80 Encrypt
 └─ 0x40 Compress
      ↓
Rijndael decrypt
      ↓
gzip decompress
      ↓
5749-byte protobuf-like OpInfo data
```

가 실제 데이터로 검증되었다.

## 10. Decompressed OpInfo 핵심 확인

5749-byte 결과의 protobuf top-level에서:

```text
field 1 = SerialNumber
field 2 = OpCode = 23 (0x17)
field 4 = length-delimited nested data
field 21 = repeated length-delimited entries
...
```

가 확인된다.

따라서 frame 159 → frame 162/163은 **0x14 GetChapterBoxReward response가 아니다.**

이것은 기존 분석의 중요한 정정이다.

현재 확정:

```text
159 request  -> OpCode 0x17
162+163 rsp -> OpCode 0x17
```

따라서 이 구간을 `0x14 → BoxStatus`의 직접 증거로 사용하지 않는다.

## 11. 동일 PCAP의 주요 opcode 복호화 결과

현재 single-fragment application packet도 같은 KCP key로 검증했다.

| Frame | 방향 | flag | plaintext OpCode |
|---:|---|---:|---:|
| 89 | C→S | 0x80 | 0x01 |
| 91 | S→C | 0x84 | 0x01 |
| 93 | C→S | 0x80 | 0x13 |
| 95 | S→C | 0x84 | 0x13 |
| 137 | C→S | 0x80 | 0x19 |
| 139 | S→C | 0x84 | 0x19 |
| 146 | C→S | 0x80 | 0x16 |
| 147 | C→S | 0x80 | 0x16 |
| 149 | S→C | 0x84 | 0x16 |
| 159 | C→S | 0x80 | 0x17 |
| 162+163 | S→C | 0xC4 | 0x17 |

현재 PCAP에는 직접 복호화 가능한 `0x14` request/response가 보이지 않는다.

따라서 이 PCAP은 Chapter Box 클릭 자체보다는 **Chapter 선택 → 전투 → 전투 결과/후속 상태 갱신** 구간의 증거로 보는 것이 맞다.

## 12. BoxStatus 분석에 대한 변경

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

현재 기준:

```text
Chapter selection / battle flow
        ↓
multiple OpInfo operations
        ↓
0x17 response
        ↓
Chapters field 여부를 별도로 확인
```

그리고 Box reward 자체는 별도의:

```text
GetChapterBoxReward @ 00ddeea8
opcode = 0x14
```

request/response capture가 필요하다.

## 13. 다음 분석 우선순위

### 1
`GetChapterBoxReward @ 00ddeea8` 직전/직후 실제 화면 동작을 별도 PCAP으로 수집한다.

필요한 최소 동작:

```text
Chapter map
 → box 수령 가능 상태
 → 특정 box 클릭
 → reward 수령
```

### 2
그 PCAP에서:

```text
client request opcode 0x14
server response opcode 0x14
```

를 찾는다.

### 3
0x14 response를 복호화/압축해제한 뒤:

```text
OpInfo.Chapters (+0xC0)
        ↓
ProtoChapter
        ↓
Id +0x10
Status +0x14
Progress +0x18
BoxStatus +0x1C
```

의 실제 변경을 확인한다.

### 4
동시에 현재 0x17 response의 5749-byte protobuf에서 Chapters field가 존재하는지, 존재한다면 어떤 nested message가 Chapter인지 계속 식별한다.

## 14. 최종 결론

이번 단계에서 다음이 실제 데이터로 확정되었다.

- `p = 2^64 - 59`
- `KCPTube.Handshake2 → Secret1/Secret2`
- `Key = LE64(secret1) || LE64(secret2)`
- KCP public 값에서 discrete log으로 private 복구 가능
- 실제 KCP session key:
  `c0ad59d9691e75ebea90346c26f653ad`
- frame 159 실제 Rijndael/CBC/PKCS7 복호화 성공
- frame 162+163 KCP fragment 재조립 및 복호화 성공
- `0xC4 = Encrypt + Compress + 추가 bit` 형태의 실제 응답 확인
- gzip decompression 성공
- decompressed 5749-byte OpInfo protobuf-like data 확보
- 159/162+163의 실제 OpCode는 `0x17`
- 따라서 `159 → 162/163 = 0x14` 가설은 반증
- `0x14 → BoxStatus`는 여전히 미확정

다음 단계는 DH64 재분석이 아니라 **실제 Box 클릭 PCAP에서 opcode 0x14를 잡는 것**이다.

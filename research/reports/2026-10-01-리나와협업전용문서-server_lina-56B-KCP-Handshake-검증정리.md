# 2026-10-01-리나와협업전용문서-server_lina-56B-KCP-Handshake-검증정리

> **리나와협업전용문서**
>
> 목적: `server_lina` 최신 구현을 참고하여 `arme`의 기존 네트워크 분석과 대조하고, 로컬 서버의 56B KCP Handshake 문제를 별도 관리한다.
>
> 원칙: `server_lina`는 **참고/분석만** 한다. 이 문서는 `arme`의 기존 분석문서를 수정하지 않고 별도 문서로 관리한다.

## 1. 확인한 server_lina 최신 상태

최신 커밋 기준 주요 변경:

- `KCP: 전체 패킷 로깅`
- `작업정리: 핸드셰이크 문제 발견`
- `작업정리: 핸드셰이크 패킷 구조 분석`
- `작업정리: PCAP 핸드셰이크 분석`
- `KCP: Handshake1/2 구분 처리`
- `KCP: 토큰 추출 수정`

현재 `app/kcp/server.py`는 다음 흐름이다.

1. 373B 수신 → Handshake1
2. 37B 응답 전송
3. 다음 56B 수신 → Handshake2
4. `data[0x11:0x19]`을 little-endian UInt64로 읽어 Client public으로 사용
5. DH secret 계산
6. 56B 응답 생성
7. 응답은 기본적으로 입력 packet을 에코하고 `0x11~0x18`만 Server public으로 교체
8. 이후 패킷 대기

현재 56B 응답 핵심 구현:

```python
resp = bytearray(56)
resp[0:0x11] = data[0:0x11]
srv_pub1, _ = dh.get_public_pair()
struct.pack_into("<Q", resp, 0x11, srv_pub1)
resp[0x19:] = data[0x19:]
conn.send(bytes(resp))
```

즉 현재 구현은 **56B 전체를 동일하게 유지하면서 +0x11의 8바이트만 서버 public #1로 교체**한다.

## 2. arme 기존 분석과의 대조

`arme`의 Ghidra 분석에서는 `KCPTube$$Handshake2`가 다음 위치를 읽는 것으로 확인되어 있다.

- packet + `0x11` → Peer public #1
- packet + `0x19` → Peer public #2
- local private #1/#2를 각각 사용
- `DH64.Secret(private1, public1)`
- `DH64.Secret(private2, public2)`
- 두 secret을 연결하여 16바이트 session key 생성

따라서 현재 `server_lina` 구현의

```data[0x11:0x19]
```

만 사용하는 DH 계산은 **Ghidra에서 확인된 2중 DH 구조와 아직 일치하지 않는다.**

관련 기준 문서:
`research/reports/1001-2026-10-01-DH64-KCP2-56바이트-구조-가설-및-검증기록.md`

## 3. 현재 가장 중요한 충돌점

현재 관찰된 56B 입력에서:

- +0x11 값은 DH public #1 후보
- +0x19 값도 Ghidra상 DH public #2 후보
- 그런데 +0x19 영역에서 `0x61636f6c...` 형태가 반복 관찰됨

따라서 다음 세 가지를 아직 열어둔다.

### 가설 A
+0x11과 +0x19가 모두 실제 DH public 값이다.

### 가설 B
+0x19는 DH public #2가 아니라 token/다른 논리 필드이며, Ghidra의 read 위치와 실제 wire 구조를 추가 검증해야 한다.

### 가설 C
56B packet 자체가 여러 handshake 필드의 조합이며 현재 parser의 field boundary가 잘못 잡혀 있다.

**현재 단계에서는 A/B/C 중 하나를 확정하지 않는다.**

## 4. 왜 현재 56B 응답에서 클라이언트가 종료되는가

현재 서버 응답은:

- +0x11 → server public #1
- +0x19 이후 → client packet 그대로 복사

형태다.

그런데 Ghidra 분석이 맞다면 서버 응답도 client가 기대하는 DH pair/handshake 구조와 대응해야 한다.

따라서 현재 클라이언트 종료는 단순히 TCP 연결 문제가 아니라 다음 항목 중 하나일 가능성이 있다.

1. Server public #2가 필요한데 제공하지 않음
2. +0x19 영역이 token/다른 필드인데 잘못 에코함
3. response header/length/marker가 client 기대값과 다름
4. server public byte order가 잘못됨
5. DH secret/session key가 client와 일치하지 않음
6. Handshake2 이후 KCP state transition에 필요한 응답값이 없음

아직 종료 원인을 하나로 확정하지 않는다.

## 5. 다음 검증 순서

서버 코드를 바로 수정하기보다 다음 순서로 검증한다.

### 1단계 — 원본 56B 분해

실제 수신 packet을:

```
00~10
11~18
19~20
...
37
```

형태로 offset별 출력한다.

특히 +0x11과 +0x19를 raw byte와 UInt64 양쪽으로 기록한다.

### 2단계 — Ghidra와 1:1 대응

`KCPTube$$Handshake2`의:

- +0x11 read
- +0x19 read
- private #1
- private #2
- Secret #1
- Secret #2

를 각각 server 로그의 값과 대응시킨다.

### 3단계 — 56B 응답 원본 확보

현재 서버가 생성한 응답 전체 hex를 반드시 기록한다.

비교:

```
Client 56B request
Server 56B response
        ↓
offset별 차이
```

현재 예상되는 차이는 +0x11 하나뿐이다.

### 4단계 — client 종료 직전 확인

56B response 직후:

```
Handshake2
 → response parse
 → DH/key initialization
 → KCP state
 → GAME_CONN
```

중 어디에서 종료되는지 확인한다.

### 5단계 — 그 후 server response 수정

검증 결과에 따라:

- public #1
- public #2
- header
- token
- length/marker

중 필요한 부분만 단계적으로 변경한다.

## 6. 현재 결론

현재 `server_lina` 구현은 **56B를 받고 응답을 보내는 TCP 단계까지는 진행**하고 있다.

하지만 현재 응답은:

> 입력 56B를 거의 그대로 에코 + +0x11의 Server public #1 교체

이므로, `arme`에서 확인된 **DH64 2중 public/session-key 구조를 완전히 반영한 서버 응답이라고 볼 수 없다.**

따라서 다음 핵심 작업은 **56B response format 자체를 추측해서 수정하는 것이 아니라, client가 response를 읽는 위치와 server가 보내야 할 두 public/필드를 1:1로 확정하는 것**이다.

## 7. 작업 경계

- `server_lina`: 실제 서버 구현 및 테스트 대상
- `arme`: Ghidra/PCAP/기존 연구 결과 참고 대상
- 본 문서: 두 저장소의 분석 결과를 연결하는 **리나와협업전용문서**
- `arme`의 기존 분석문서는 변경하지 않는다.


## 8. 2026-10-01 추가 정적분석 — 56B 응답 가설 정정

### 핵심 확정

`KCPTube$$Poll @ 015b0094`의 흐름을 확인한 결과:

```
Socket.Receive
   ↓
수신 데이터 길이/상태 판정
   ↓
Handshake2 @ 015b1f68
```

으로 들어간다.

그리고 `Handshake2 @ 015b1f68` 내부에는:

```
packet + 0x11 → UInt64 → peer public #1
packet + 0x19 → UInt64 → peer public #2

private #1 @ this+0x58
private #2 @ this+0x60

Secret #1
Secret #2

→ Key 16 bytes
→ KCP 생성
→ set_kcp
→ KCP NoDelay
→ WndSize
→ set_State(3)
```

순서가 확인된다.

중요하게도 **Handshake2 내부에는 `KCPTube.Output` 또는 `Socket.Send` 호출이 없다.**

따라서 현재 `server_lina/app/kcp/server.py`의:

```python
# Handshake2 응답 (56B, 에코)
resp = bytearray(56)
...
conn.send(bytes(resp))
```

은 현재까지 확인된 클라이언트 코드 흐름과 직접 충돌한다.

### 9. 현재 56B 문제의 방향 전환

기존에는:

> 56B를 받은 서버가 올바른 56B 응답을 만들어야 한다.

고 가정했지만, 현재 Ghidra 정적분석 결과는:

> **56B는 서버가 응답해야 할 packet이 아니라 클라이언트가 서버로 보내는 Handshake2 입력일 가능성이 매우 높다.**

즉 실제 흐름은 다음에 가깝다.

```
Client
  │
  │ Handshake1
  ▼
Server
  │
  │ Handshake1 response
  ▼
Client
  │
  │ Handshake2 (56B)
  ▼
Server
  │
  ├─ +0x11 public #1
  ├─ +0x19 public #2
  ├─ DH Secret #1
  ├─ DH Secret #2
  ├─ 16B Key 생성
  ├─ KCP 생성
  └─ State = 3
       ↓
    이후 KCP 통신
```

### 10. server_lina에 대한 직접적인 영향

현재 구현의 Handshake2 처리:

```56B 수신
→ public #1만 DH
→ 56B 에코 응답
→ 이후 recv 대기
```

은 다음 두 가지가 동시에 잘못될 가능성이 있다.

1. public #2를 DH 계산에 사용하지 않음
2. 존재하지 않는 56B 서버 응답을 전송함

따라서 **56B 응답 형식을 계속 추측해서 수정하는 작업은 일단 중단하는 것이 맞다.**

### 11. 다음 구현 검증 대상

이제 확인해야 할 것은 56B response가 아니라 **Handshake1 server response**다.

우선 다음을 정확히 비교한다.

- 원본 PCAP의 Client Handshake1
- 원본 PCAP의 Server Handshake1 response
- `KCPTube.Handshake1 @ 015aff18`에서 생성하는 byte 배열
- `KCPTube.Output @ 015b21c4`가 실제 Socket.Send하는 길이
- 그 결과 Client가 보내는 56B Handshake2
- Server가 56B를 받은 뒤 보내야 하는 것이 실제로 없는지

특히 `Handshake1`은 `DH64.KeyPair`를 두 번 호출하고, 두 public 값을 packet에 넣는 구조가 확인된다.

### 12. 현재 결론

**56B 서버 응답 문제라는 기존 가설은 폐기하고, 56B는 Handshake2 client→server 입력으로 취급한다.**

현재 server_lina의 가장 먼저 수정/검증할 대상은:

```
Handshake1 response
      ↓
Client Handshake2 56B
      ↓
Server DH64 #1/#2
      ↓
16B session Key
      ↓
KCP State 3
      ↓
첫 KCP packet
```

이다.

단, 실제 server_lina 코드는 아직 수정하지 않는다. 다음 단계에서 PCAP의 Handshake1 response와 Ghidra의 `Handshake1/Output`을 1:1 비교하여 정확한 서버 응답을 확정한다.


## 13. Handshake1 응답까지 대조한 결과

PCAP 기준 37B 서버 응답은 다음 구조로 정리되어 있다.

| Offset | Size | 의미 |
|---|---:|---|
| 0x00 | 8 | zero |
| 0x08 | 4 | length = 0x19 |
| 0x0C | 1 | marker = 0x01 |
| 0x0D | 8 | TCPConvID |
| 0x15 | 8 | Server DH public #1 |
| 0x1D | 8 | Server DH public #2 |

server_lina의 Handshake1 응답은 이 구조를 상당 부분 따르지만, +0x15에는 현재 생성한 public #1을 넣고 +0x1D에는 PCAP 고정값 f946af9e83fde980을 넣는다.

즉 **Server public #2가 현재 연결의 DH key pair에서 생성된 값인지 보장되지 않는다.**

Ghidra의 KCPTube.Handshake1은 DH64.KeyPair를 두 번 호출하여 private #1/#2와 public #1/#2를 생성한다. 따라서 서버 구현도 고정 PCAP 값을 사용하는 대신 동일 연결에서 생성한 public #1/#2를 37B 응답에 대응시켜야 한다.

## 14. 현재 서버 구현과 Ghidra 흐름

현재 server_lina:

Handshake1 → public #1 실제 생성 + public #2 PCAP 고정값

Handshake2 56B → client public #1만 사용 → 56B 응답 에코

Ghidra 기준:

Handshake1 → DH pair #1/#2 생성 → server public #1/#2 전송

Handshake2 56B → client public #1 @ +0x11 / client public #2 @ +0x19 → Secret #1/#2 → 16B Key → KCP 생성 → State=3

따라서 현재 가장 우선적으로 확인할 것은 56B 응답 생성 코드가 아니라 Handshake1의 두 번째 public과 Handshake2의 두 번째 DH 계산이다.

## 15. 구현 변경은 아직 하지 않음

다음 실제 테스트는 한 번에 하나씩 검증한다.

1. Handshake1의 +0x1D를 현재 생성 public #2로 교체
2. Handshake2에서 +0x19를 두 번째 DH 입력으로 사용
3. 56B 서버 응답 전송 제거
4. 생성된 16B Key 확인
5. State=3 이후 첫 KCP packet 수신 여부 확인

이 작업은 server_lina에서만 수행하며, 이 협업 문서 외의 arme 기존 분석문서는 수정하지 않는다.

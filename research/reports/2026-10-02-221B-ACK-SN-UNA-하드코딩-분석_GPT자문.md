# 2026-10-02 221B ACK SN/UNA 하드코딩 분석_GPT자문

## 1. 현재 수신한 221B의 KCP Header

로그:

```
Header (16B): 5100000146e2affa0100000000000000
```

KCP 표준 구조대로 LE로 해석하면:

| offset | 값 | 의미 |
|---|---|---|
| +0x00 | 51 | CMD = DATA |
| +0x01 | 00 | FRG = 0 |
| +0x02 | 00 01 | Window = 256 |
| +0x04 | 46 e2 af fa | Timestamp |
| +0x08 | 01 00 00 00 | SN = 1 |
| +0x0C | 00 00 00 00 | UNA = 0 |

즉 이 패킷은 CMD=0x51, FRG=0, SN=1, UNA=0이다.

## 2. 서버 코드의 문제

현재 서버 코드는:

```python
struct.pack_into("<I", ack, 0x10, 0)  # SN
struct.pack_into("<I", ack, 0x14, 1)  # UNA
```

로 하드코딩되어 있어 실제 전송되는 ACK는 SN=0, UNA=1이다 (로그에도 그대로 출력됨).

클라이언트가 보낸 것은 DATA SN=1인데 서버가 ACK SN=0, UNA=1로 응답하므로, 방금 받은 SN=1을 ACK하지 않은 상태가 된다. 클라이언트가 같은 Application 데이터를 반복 전송하는 현상과 정확히 연결된다. 각 재전송의 timestamp가 달라지는 것(faab2826 → faab33e6 → faab34ae → faab363f)도 이 상황과 일치한다.

## 3. 수정 방향

ACK를 고정값으로 만들면 안 된다. 수신 KCP Header에서 SN/UNA를 추출해서 ACK를 만들어야 한다:

```python
kcp_sn = struct.unpack_from("<I", header, 0x08)[0]
kcp_una = struct.unpack_from("<I", header, 0x0C)[0]

struct.pack_into("<I", ack, 0x10, kcp_sn)
struct.pack_into("<I", ack, 0x14, kcp_sn + 1)
```

현재 패킷 기준: 수신 SN=1, UNA=0 → ACK SN=1, UNA=2.

다만 UNA를 무조건 SN+1로 결정하는 것은 최종 구현에서는 주의해야 한다. KCP는 누적 확인 개념이 있으므로 세션별 수신 상태를 유지하면서 결정해야 한다.

## 4. 더 중요한 점 — 현재 서버는 아직 "KCP 서버"가 아니다

현재 `server_udp.py`는 `elif pkt_len == 221: self.handle_kcp_data(data, addr)` 로 221B 패킷 자체를 Application 데이터처럼 처리하고 있다. 이 방식은 첫 테스트에서는 우연히 통신이 진행될 수 있지만 실제 KCP 세션에서는 문제가 발생한다.

서버가 유지해야 하는 최소 상태:

```
Session
 ├─ RX next SN
 ├─ received SN
 ├─ duplicate SN
 ├─ ACK state
 ├─ FRG fragments
 └─ reassembled Application message
```

이번 패킷은 FRG=0이므로 단일 KCP 메시지이지만, Bootstrap의 서버→클라이언트 응답은 SN=0 FRG=8 … SN=8 FRG=0 형태의 다중 fragment임이 확인되어 있다.

## 5. 현재 상태 정리

- [OK] AES 복호화
- [OK] Protobuf 파싱
- [OK] KCP Window = 31 (raw 1f 00)
- [OK] 28B ACK 형식 자체
- [NG] ACK SN/UNA 하드코딩
- [NG] KCP 세션별 RX 상태 관리 없음
- [NG] 중복/재전송 판별 없음
- [NG] FRG 기반 reassembly 없음

다음 수정의 1순위는 Window가 아니라 수신 Header → SN/UNA 추출 → 동적 ACK이다. `Header = 5100000146e2affa0100000000000000`이라는 실제 값이 확보됐으므로 추측이 아니라 실제 221B에 대한 KCP ACK 상태를 맞춰갈 수 있는 단계이다.

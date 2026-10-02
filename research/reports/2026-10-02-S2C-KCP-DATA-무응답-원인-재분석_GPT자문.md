# 2026-10-02 S→C KCP DATA 무응답 원인 재분석_GPT자문

## 1. 핵심 판정

비교 결과를 기준으로 보면, 현재의 "multi-tag 때문에 protobuf 파서가 죽었다"는 가설은 가능성은 있지만 1순위 원인으로 보기 어렵다.

핵심은 **ACK가 전혀 없다는 점**이다.

KCP 구조상 정상적인 수신이라면:

```
S→C KCP DATA
    ↓
Client KCP 수신/검증
    ↓
ACK 생성
    ↓
Application decrypt
    ↓
protobuf deserialize
```

순서가 되어야 한다.

따라서 protobuf wire-type 오류가 발생하더라도 KCP 계층에서 이미 ACK를 생성하는 구현이라면 ACK는 먼저 나와야 한다.

지금은:

```
Server → Client
193B KCP DATA
        ↓
ACK 없음
        ↓
221B 재전송 없음
        ↓
화면 Loading 유지
```

이므로 오히려 Client가 해당 S→C KCP DATA 자체를 정상적인 수신 세그먼트로 인정하지 못했을 가능성을 먼저 봐야 한다.

## 2. 전송 형식 확인

현재 send_kcp_message()의 실제 전송 형식:

```
[Session 8B]
[KCP Header 16B]
[ChunkLen 4B]
[Flag 1B]
[IV 16B]
[Ciphertext]
```

multi-tag의 경우:

```
plaintext       168B
AES padded      176B
Flag + IV       17B
KCP chunk       193B
UDP 전체        221B
```

여기서 UDP 전체가 우연히 Client→Server의 정상 요청 221B와 동일해지는 것도 확인해야 한다. 크기가 같다고 같은 packet type이라는 의미는 아니지만, Client의 수신 경로가 packet length에 의존하는지 확인할 가치가 있다.

## 3. PCAP과 비교해야 할 부분

실제 운영 PCAP의 S→C DATA fragment 하나를 잡아서 현재 193B probe와 다음을 byte-level로 비교해야 한다.

- Session
- KCP CMD
- KCP FRG
- KCP WND
- KCP TS
- KCP SN
- KCP UNA
- ChunkLen
- Flag
- IV
- Ciphertext

특히 우선순위는: KCP WND, SN, UNA, ChunkLen, FRG, TS, 실제 UDP 길이.

현재 코드에서 S→C는 WND=32, UNA=self._current_rx_una(session_id), SN=self.kcp_tx["snd_nxt"], FRG=n-1-i 로 만들어진다. 실제 PCAP의 S→C Bootstrap fragment에서 WND가 정말 32인지, UNA가 어떤 값인지를 다시 확인해야 한다.

## 4. 중요한 차이: fragment 개수

실제 PCAP은 SN=0 FRG=8 … SN=8 FRG=0 처럼 9개 fragment 이상의 실제 KCP message다.

반면 현재 테스트는 SN=0, FRG=0, chunk=193B 단일 fragment다.

즉 지금 실험은 단순히 protobuf 크기를 테스트한 것이 아니라, 실제 Client가 기대하는 S→C KCP DATA의 segment/message 형태와 다른 형태를 시험하고 있는 것이기도 하다.

그래서 다음 실험에서는 multi-tag 자체를 더 복잡하게 만들기보다 실제 PCAP의 S→C KCP DATA header와 동일한 조건으로 최소 응답을 보내는 것이 훨씬 정보량이 높다.

## 5. 원인 후보 순서 (수정)

1. S→C KCP DATA header/segment 조건 불일치
   ↓
2. Client KCP가 해당 segment를 수신 거부
   ↓
3. ACK 없음

그 다음이:

4. KCP는 받았지만 application dispatch에서 문제
5. protobuf wire-type/schema 오류
6. OpInfo 내용 부족

특히 "protobuf 예외 → 네트워크 스레드 사망"은 logcat에서 예외가 실제로 확인되기 전에는 확정하면 안 된다.

## 6. 코드 상태 확인

현재 Git의 server_udp.py도 확인했는데, PROBE_MODE="simple"로 이미 되돌아가 있고 multi-tag 부분에 이 가설이 주석으로 들어가 있다. 따라서 지금은 코드를 더 바꾸기보다 simple과 실제 PCAP의 S→C DATA header를 먼저 대조하는 것이 맞다.

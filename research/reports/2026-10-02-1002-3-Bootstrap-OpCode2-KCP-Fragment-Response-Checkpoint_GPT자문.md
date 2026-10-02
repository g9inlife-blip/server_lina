# 1002-3 GPT 자문 — Bootstrap multifrag 이후 Response Checkpoint 추적

## 1. 작업 목적

2026-10-02 Bootstrap multifrag 실험에서 서버가 13개 KCP DATA fragment를 전송했다.

SN=0 FRG=12 1372B
SN=1 FRG=11 1372B
...
SN=11 FRG=1 1372B
SN=12 FRG=0 33B

클라이언트에서는 140B/168B ACK 묶음이 관측되었으나 기존 Frida의 [BOOT_STATE]는 추가 출력되지 않았다.

이번 자문의 목표는 OpInfo field/tag mapping을 바로 진행하지 않고, KCP DATA가 실제 Application response 처리 경로까지 도달했는지를 단계별 checkpoint로 확인하는 것이다.

## 2. 운영용 Frida 파일 확인 결과

Git의 research/frida/gpt전용_justice_hook_운영접속용.js 를 운영 관찰용 기준으로 확인했다.

현재 운영용 파일은 v4.22이며 다음 구조가 이미 포함되어 있다.

- TCPTube.TryRead
- KCPTube.TryRead
- KCPTube.TryOutput
- KCPTube.Update
- KCPTube.Send
- KCPTube.Receive
- NetworkCenter.TryHandleResponse
- DataCenter.ProccessRequestRes
- TryHandleResponse +0x238 status branch
- OpInfo SerialNumber / OpCode / ReturnCode 관찰
- OpInfo 주요 field pointer 관찰
- Chapter Dictionary 관찰

따라서 이 운영용 파일의 transport/response checkpoint 구조를 참고하는 것이 맞다.

단, 운영용 파일 자체는 수정하지 않았다.

운영용 파일에는 로그인/토큰/HTTP/Dictionary 등 훨씬 많은 관찰 코드가 포함되어 있으므로, 이번 실험에서는 필요한 transport → response checkpoint만 justice_hook_opinfo.js에 별도로 반영했다.

## 3. 이번에 수정한 실험용 파일

수정 파일: research/frida/justice_hook_opinfo.js

Git commit:
8e841d7faf06ebc91f9ff53e7f432eab9e9a113f
trace: add KCP response processing checkpoints for multifrag probe

운영용 gpt전용_justice_hook_운영접속용.js 는 변경하지 않았다.

## 4. 추가한 Checkpoint 구조

관찰 순서는 다음과 같다.

KCP DATA 수신
  ↓
KCPTube.TryRead
  ↓
[TRC_KCP_READ_OK] ret=1
  ↓
NetworkCenter.TryHandleResponse
  ↓
[TRC_NET_RESP]
  ↓
[TRC_NET_STATUS]
  ↓
DataCenter.ProccessRequestRes
  ↓
[TRC_PROC_RESP]
  ↓
기존 [BOOT_RESP]
  ↓
기존 [BOOT_STATE]

이제 [BOOT_STATE]가 안 나오더라도 어느 단계에서 끊겼는지를 판단할 수 있다.

## 5. 각 로그의 의미

### 5.1 [TRC_KCP_READ]

[TRC_KCP_READ] enter
[TRC_KCP_READ_OK] ret=1

의미:
- KCPTube.TryRead가 실제 호출되었는지 확인
- ret=1이면 TryRead 성공 경로가 발생했음을 확인

주의: TryRead ret=1 자체를 곧바로 ProccessRequestRes 성공으로 해석하지 않는다.

### 5.2 [TRC_NET_RESP]

[TRC_NET_RESP] TryHandleResponse enter
[TRC_NET_RESP] TryHandleResponse leave ret=...

의미: KCP에서 만들어진 response가 NetworkCenter의 response 처리/dispatch 단계까지 들어왔는지 확인한다.

### 5.3 [TRC_NET_STATUS]

[TRC_NET_STATUS] status=4 route=ProccessRequestRes

운영용 hook에서 사용 중인 정적 분석 기준을 참고했다.

status < 5  -> ProccessRequestRes route
status >= 5 -> 해당 route skip

이번 실험에서 중요한 것은 status 값 자체보다 TryHandleResponse가 어떤 route를 선택했는지다.

주의: 이 checkpoint는 TryHandleResponse +0x238이라는 정적 위치에 의존한다. 현재 APK/libil2cpp 버전과 Listing이 일치한다는 전제에서만 사용한다. 버전이 바뀌면 이 offset은 다시 검증해야 한다.

### 5.4 [TRC_PROC_RESP]

예:
[TRC_PROC_RESP] enter response=OpInfo@... SerialNumber=... OpCode=... ReturnCode=...

이 로그가 나오면 Application response가 DataCenter.ProccessRequestRes까지 도달한 것으로 판단할 수 있다.

여기서도 payload 전체나 protobuf buffer는 출력하지 않는다.

## 6. 이번 실험에서의 판정표

### Case A

[TRC_KCP_READ_OK] 조차 없다.

판정: UDP/KCP DATA → ACK 이후 TryRead 이전 구간을 조사해야 한다. 서버 fragment 전체 수신 여부와 KCP reassembly 조건을 먼저 확인한다.

특히 이번 실험에서는 SN=0~12 / FRG=12~0 전체가 들어갔는지 확인한다.

### Case B

[TRC_KCP_READ_OK]는 나오지만 [TRC_NET_RESP]가 없다.

판정: KCPTube.TryRead → response dispatch 이전에서 멈춘 것이다. deserialize/response queue 생성 또는 TryRead 내부 후속 경로를 조사한다.

### Case C

[TRC_NET_RESP]는 나오지만 [TRC_PROC_RESP]가 없다.

그리고 [TRC_NET_STATUS] status >= 5 route=skip 이면 ProccessRequestRes route가 선택되지 않은 것이다.

이 경우에는 status/response routing을 먼저 분석한다.

### Case D

[TRC_NET_RESP]와 route=ProccessRequestRes까지 나오지만 [TRC_PROC_RESP]가 없다.

이 경우에는 TryHandleResponse 내부 호출 흐름 또는 함수 signature/후크 대상 overload가 현재 runtime과 맞는지 다시 확인한다.

### Case E

[TRC_PROC_RESP]까지 나오지만 [BOOT_STATE]가 없다.

이 경우부터 OpInfo field 자체 또는 기존 BOOT hook의 response 인자/offset 문제를 조사한다.

이 단계에 도달하기 전에는 field/tag mapping을 변경하지 않는다.

### Case F

[TRC_PROC_RESP]가 정상 출력되고 [BOOT_RESP]와 [BOOT_STATE]도 나온다.

이 경우에만 multifrag response가 실제 OpInfo deserialize/dispatch까지 성공했다고 판단하고 field mapping 실험으로 넘어간다.

## 7. 기존 13-fragment 실험과 연결

이번 서버 로그의 최종 fragment는 SN=12 / FRG=0 이다.

따라서 이전 12-fragment 실험의 SN=11을 이번 실험의 최종 SN으로 사용해서는 안 된다.

현재 제공된 ACK 로그만으로는 SN=0~10이 확인되며 SN=11/12 ACK 여부는 미확인이다.

다음 실행에서는 반드시 SN=11 ACK와 SN=12 ACK 여부까지 확인한다.

## 8. 중요한 분석 방향 변경

현재 단계에서는 다음 가정을 하지 않는다.

field 3~64 중 잘못된 field 때문에 BOOT_STATE가 안 나왔다.
protobuf tag mapping이 틀렸다.

현재 더 직접적인 질문은 다음이다.

13-fragment KCP DATA
  ↓
KCP reassembly
  ↓
KCPTube.TryRead
  ↓
NetworkCenter.TryHandleResponse
  ↓
DataCenter.ProccessRequestRes

중 어디까지 도달했는가?

이것을 먼저 확정한다.

## 9. multifrag_tag 실험에 대한 현재 판단

현재 multifrag_tag는 field 3~64에 빈 nested protobuf field를 반복적으로 넣는 방식이다.

이 실험은 parser가 실제로 호출된다는 것이 먼저 확인된 뒤에 의미가 있다.

현재 parser 진입 자체가 확인되지 않았으므로 당장은 multifrag_tag의 field mapping을 더 확장하지 않는다.

우선 multifrag 또는 현재 13-fragment probe를 사용해 transport → response checkpoint를 확인한다.

## 10. 다음 실행 방법

현재 수정된 실험용 hook:
research/frida/justice_hook_opinfo.js

실행:
frida -H 127.0.0.1:27042 -n Gadget -l research/frida/justice_hook_opinfo.js

동일한 13-fragment Bootstrap probe를 실행한다.

로그에서 다음 순서를 찾는다.

[TRC_KCP_READ]
[TRC_KCP_READ_OK]
[TRC_NET_RESP]
[TRC_NET_STATUS]
[TRC_PROC_RESP]
[BOOT_RESP]
[BOOT_STATE]

가능하면 서버 UDP 로그와 Frida 로그를 시간순으로 맞춘다.

## 11. 운영용 hook에 대한 주의

이번 분석에서 gpt전용_justice_hook_운영접속용.js는 매우 유용한 기준 코드지만 운영용 파일 자체를 실험용으로 직접 수정하지 않는다.

운영용 파일은 HTTP/Login, token fingerprint, KCP/TCP transport, response dispatch, OpInfo, Chapter Dictionary 등 많은 runtime 관찰 코드가 함께 들어 있다.

따라서 실험 목적의 checkpoint는 별도 파일 또는 현재 justice_hook_opinfo.js에 최소 범위로 넣어야 한다.

이번 변경도 이 원칙을 따른다.

## 12. 현재 결론

1. 서버가 13개의 KCP DATA fragment를 보냈다.
2. 클라이언트는 적어도 일부 fragment에 대해 ACK를 생성했다.
3. 기존 [BOOT_STATE]만으로는 KCP DATA 이후 어느 단계에서 중단됐는지 알 수 없었다.
4. 운영용 v4.22 hook에는 이미 transport → TryHandleResponse → ProccessRequestRes 관찰 구조가 있었다.
5. 그 구조를 참고해 실험용 justice_hook_opinfo.js에 최소 checkpoint를 추가했다.
6. 운영용 gpt전용_justice_hook_운영접속용.js는 수정하지 않았다.
7. 이제 다음 실행에서는 KCP 수신 → response dispatch → DataCenter 처리 중 실제 마지막 도달 지점을 확인한다.
8. [TRC_PROC_RESP] 이전에는 OpInfo field/tag mapping을 변경하지 않는다.

### 다음 분석 우선순위

1. SN=11 / SN=12 ACK 확인
2. [TRC_KCP_READ_OK] 확인
3. [TRC_NET_RESP] 확인
4. [TRC_NET_STATUS] 확인
5. [TRC_PROC_RESP] 확인
6. [BOOT_RESP] 확인
7. [BOOT_STATE] field mapping
8. 그 다음에만 multifrag_tag 재실험

이 순서로 진행한다.
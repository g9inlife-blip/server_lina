# KCP 핸드셰이크 분석 및 구현 정리 (2026-10-01)

## 개요
JusticeSchool 로컬 서버의 KCP 게임 서버 핸드셰이크 구현 과정 정리.
HTTP 로그인은 완료, KCP 핸드셰이크에서 블로킹 중.

## 1. 프로토콜 발견

### 1.1 실제 서버 (PCAP 분석)
- **전송계층**: UDP 8000번
- **Handshake1**: C→S 368B
  - `0x00-0x07`: zeros (8B)
  - `0x08-0x0C`: 헤더 (5B)
  - `0x0D~`: 바이너리 + Base64 혼합 데이터
- **서버 응답**: S→C 33B
  - `0x00-0x07`: zeros (8B)
  - `0x08`: 0x01 (1B)
  - `0x09-0x10`: session ID (8B)
  - `0x11-0x18`: ??? (8B)
  - `0x19-0x20`: server public? (8B)
- **이후**: C→S 221B (session ID 포함) → S→C 28B → 게임 데이터 (1400B)

### 1.2 로컬 서버 (실제 관측)
- **전송계층**: UDP 8000번 (TCP 아님!)
- **핸드셰이크**: C→S 51B (368B 아님!)
  - `0x00-0x07`: zeros (8B)
  - `0x08-0x0F`: public #1 (8B, 매번 변경)
  - `0x10-0x17`: public #2 (8B, 매번 변경)
  - `0x18~`: token 문자열 ("local-dummy-token-witchwind", 27B)
- **서버 응답**: S→C 33B (PCAP 형식 차용)
- **이후**: C→S 221B 반복 전송 (재시도 루프)

### 1.3 TCP 56B (구 관찰, 현재 미사용)
- 초기 로컬 테스트에서 TCP 56B 패킷 관측됨
- UDP로 전환 후 51B로 변경됨
- 56B는 TCP용, 51B는 UDP용으로 보임

## 2. DH64 파라미터 (Ghidra 분석)

```
P = 0xFFFFFFFFFFFFFFC5 (2^64 - 59)
G = 5
secret = peerPublic ^ localPrivate mod P
```

- 368B 프로토콜 기준으로 분석됨
- 51B 프로토콜에 동일한 파라미터 적용 중 (검증 안 됨)

## 3. 시도한 방법 및 결과

### 3.1 TCP 56B 핸드셰이크 (실패)
**시도:**
1. 2중 DH (public #1 @0x11, public #2 @0x19)
   - 결과: public #2가 토큰 데이터와 겹침 → 실패
2. 단일 DH (public #1만 사용)
   - 결과: 클라이언트 재시도 루프 → 실패
3. 56B 응답 전송 vs 미전송
   - 결과: 모두 재시도 루프 → 실패

**결론**: TCP 56B는 잘못된 접근. 실제는 UDP.

### 3.2 UDP 51B 핸드셰이크 (부분 성공)
**시도:**
1. 51B 파싱 → public #1 (0x08), public #2 (0x10) 추출 ✅
2. 2중 DH 계산 → secret #1, #2 생성 ✅
3. 세션 키: `LE64(secret1) || LE64(secret2)` (16B) ✅
4. 33B 응답 전송 (session ID + server public) ✅
5. 클라이언트가 221B 전송 시작 ✅ (핸드셰이크 형식 인정!)

**실패:**
- 221B 복호화 실패
- 시도한 키 유도 방식:
  - `LE64(s1) || LE64(s2)` → 실패
  - `SHA256(LE64(s1) || LE64(s2))[:16]` → 실패 (테스트 중)
- 시도한 IV:
  - zeros (16B) → 실패
  - session_id + zeros → 실패

**원인 가설:**
1. 51B용 DH 파라미터(P, G)가 368B와 다름
2. 키 유도 방식이 다름 (단순 연결이 아님)
3. 51B의 "public key"가 DH 키가 아님 (nonce일 가능성)
4. 암호화 알고리즘/모드가 다름 (AES-CBC가 아님)
5. 암호문 시작 위치가 0x20이 아님

### 3.3 368B 핸드셰이크 (미구현)
- PCAP에 실제 데이터 있음
- 클라이언트가 로컬 서버에는 368B를 보내지 않음 (51B만 보냄)
- 368B를 보내게 하는 트리거 불명
- AllInOne 응답 비교 필요

## 4. 핵심 발견

### 4.1 UDP vs TCP
- 실제 게임: UDP 8000번 사용
- 초기 로컬 서버: TCP로 잘못 구현
- `adb reverse`는 TCP만 지원, UDP는 지원 안 함
- 해결: 폰 핫스팟 + PC를 핫스팟에 연결 → 같은 네트워크

### 4.2 51B 구조
```
0x00 (8B): zeros
0x08 (8B): public #1 (random)
0x10 (8B): public #2 (random)
0x18 (27B): token
```
- 2중 DH 구조 (Ghidra 분석과 일치)
- 토큰과 겹치지 않음 (TCP 56B와 다름)

### 4.3 33B 응답 효과
- 51B에 33B로 응답하면 클라이언트가 221B 전송 시작
- 핸드셰이크 형식은 인정받음
- 하지만 암호화 키가 안 맞음

### 4.4 Frida 후킹 한계
- `KCPTube.Handshake1/2` 이름 검색 실패
- Ghidra RVA 직접 후킹 시도했으나 `[KCP] Handshake1 ENTER` 미발생
- 원인: RVA가 APK 버전과 다르거나, 호출 시점이 후킹 설치 전
- `CSBehaviour.Connect`, `LoginManager.LoginGameServer`는 후킹 성공

## 5. 현재 상태 (2026-10-01 17:00)

### 동작하는 것
- ✅ HTTP 로그인 (AllInOne, Login)
- ✅ UDP 서버 (0.0.0.0:8000)
- ✅ 51B 핸드셰이크 수신 및 파싱
- ✅ 2중 DH 계산
- ✅ 33B 응답 전송
- ✅ 클라이언트의 221B 전송 유도

### 안 되는 것
- ❌ 221B 복호화 (세션 키 불일치)
- ❌ 게임 데이터 송수신
- ❌ 368B 핸드셰이크 유도

## 6. 다음 단계 옵션

### 옵션 A: 51B 복호화 계속 파기
- 다양한 키 유도 방식 시도
- 다양한 IV 시도
- 암호문 경계 재확인
- 필요: 클라이언트의 실제 세션 키를 알 방법

### 옵션 B: 368B 핸드셰이크 구현
- PCAP의 368B/33B/221B/28B 플로우 구현
- 클라이언트가 368B를 보내도록 유도
- 필요: 368B 트리거 조건 파악 (AllInOne 응답 비교)

### 옵션 C: 고정 키 방식 (사용자 제안)
- DH 대신 고정 세션 키 사용
- 클라이언트가 고정 키를 받아들이는지 테스트
- 필요: 클라이언트가 키를 검증하지 않는다는 가정

### 옵션 D: GPT 추가 분석 대기
- 51B 프로토콜의 정확한 DH 파라미터
- 51B의 키 유도 방식
- 221B의 암호화 상세 (IV, 패딩, 오프셋)

## 7. 파일 참조

- `app/kcp/server_udp.py`: UDP 서버 (51B/33B/221B 처리)
- `app/kcp/dh64.py`: DH64 구현 (P, G)
- `app/kcp/crypto.py`: AES-128-CBC (IV=zeros 가정)
- `app/kcp/server.py`: 구 TCP 서버 (미사용)
- `research/frida/justice_hook.js`: 로컬용 후크 (리다이렉트 ON)
- `research/frida/justice_capture.js`: 운영용 후크 (리다이렉트 OFF)
- `research/PCAP/`: PCAP 원본 파일들
- `research/reports/2026-10-01-리나와협업전용문서-server_lina-56B-KCP-Handshake-검증정리.md`: GPT 분석 문서

## 8. 네트워크 설정 (로컬 테스트)

```
폰 (핫스팟 호스트): 10.87.155.108
PC (핫스팟 클라이언트): 10.87.155.119

HTTP 서버: 0.0.0.0:8888 (LINA_HOST=10.87.155.119)
UDP 서버: 0.0.0.0:8000
방화벽: UDP 8000 인바운드 허용
```

---
*작성: 2026-10-01, 리나*

## 9. 통합 서버 실행 (`app/run_all.py`) — 사용 보류 (2026-10-02)

### 배경
사용자 질문: "나중에 최종적으로 할 때도 2개 다 켜놓아야 하나, 아니면 한 개 프로세스로 2개를 다 켜두는 건가"
→ HTTP(8888) + UDP KCP(8000)를 하나의 프로세스로 실행하는 `app/run_all.py` 신규 생성.
**사용자 결정 (2026-10-02): 당장은 쓰지 않고, 나중에 쓰기로. 지금은 개별 실행(터미널 2개) 유지.**

### 동작
- UDP KCP 서버(`app.kcp.server_udp.KCPServerUDP`)를 데몬 스레드로 시작.
- HTTP 서버(uvicorn `app.main:app`)를 메인 스레드에서 실행 (로그는 `warning` 레벨로 간소화).
- CTRL+C 한 번으로 둘 다 종료. 창 하나만 띄우면 됨.
- 데몬 스레드라 메인(uvicorn) 종료 시 UDP도 함께 종료됨.

### 사용법 (사용자 PC)
```bash
cd C:\Users\USER\Documents\GitHub\server_lina
git pull
set LINA_HOST=10.87.155.119
python -m app.run_all
```
인자로 직접 지정도 가능:
```bash
python -m app.run_all --lina-host 10.87.155.119 --http-port 8888 --udp-port 8000
```
- `--host` (기본 `0.0.0.0`): 바인드 주소
- `--http-port` (기본 `8888`), `--udp-port` (기본 `8000`)
- `--lina-host`가 있으면 `LINA_HOST` 환경변수보다 우선

### 나중에 전환하는 시점
- 디버깅 단계가 끝나고 서버 동작이 안정화된 뒤 (최종 운용 시).
- 개별 실행이 편한 이유 (현재): HTTP 로그와 UDP RAW hex 로그를 분리해서 볼 수 있음.
- 전환 시 확인: `python -m app.run_all` 한 줄로 로그인→게임 진입 전 구간이 개별 실행과 동일하게 동작하는지.

---
*추가: 2026-10-02, 리나*

# 네트워크 Req/Rsp 작업 계획

## 1. 목적

게임의 실제 네트워크 Request/Response를 확보하고, 정적 분석 데이터(Record/Reference)와 연결하여 로그인부터 로비, 던전, 전투, 보상, 뽑기, 상점, 이벤트까지의 데이터 흐름을 확인한다.

> 분석 대상은 합법적으로 접근 가능한 테스트 환경과 본인이 보유/분석 권한을 가진 앱·계정·서버 통신을 기준으로 한다.

## 2. 전체 구조

```
LDPlayer
  ↓
HTTP/HTTPS Proxy
  ↓
Burp Suite
  ↓
Game Server

필요 시
LDPlayer
  ↓
Runtime instrumentation
  ↓
HTTP Client / TLS / Native Layer
  ↓
Req/Rsp 확인
```

## 3. 1차 방법 — Proxy Capture

1. LDPlayer ADB 연결 확인
2. Windows PC의 LAN IP 확인
3. Burp Listener를 `0.0.0.0:8080`으로 설정
4. LDPlayer Wi-Fi Proxy를 PC IP + 8080으로 설정
5. HTTP 통신 확인
6. Burp CA를 LDPlayer에 설치
7. HTTPS 통신 확인
8. 게임 실행
9. 로그인 Req/Rsp부터 저장

## 4. 2차 방법 — Runtime 계측

Proxy에서 HTTPS 내용이 확인되지 않는 경우에만 앱의 HTTP Client/Native 네트워크 계층을 조사한다.

확인 대상 예:
- UnityWebRequest
- DownloadHandler / UploadHandler
- OkHttp 계열
- libcurl
- Unity/IL2CPP native networking
- TLS 계층

목표는 인증 우회가 아니라 실제 URL, Request, Response, 상태 변화의 구조를 확인하는 것이다.

## 5. 기능별 수집 순서

1. 로그인
2. 로그인 직후 초기화
3. 로비
4. 유저 상태
5. 캐릭터
6. 인벤토리
7. 던전 목록
8. 던전 상세
9. 던전 입장
10. 전투 시작
11. 전투 결과
12. 보상
13. 뽑기
14. 상점
15. 퀘스트
16. 업적
17. 출석
18. 일일 보상
19. 우편
20. 이벤트

## 6. 핵심 원칙

한 세션에서 여러 행동을 섞지 않는다.

예:
- Session 001: 실행 → 로그인 → 종료
- Session 002: 실행 → 로그인 → 로비 확인 → 종료
- Session 003: 실행 → 로그인 → 던전 목록 → 종료
- Session 004: 실행 → 로그인 → 던전 입장 → 종료

각 행동의 전후 상태와 Req/Rsp를 비교한다.

## 7. 최종 목표

```
User Action
  ↓
Request
  ↓
Endpoint
  ↓
Response
  ↓
ID / Record
  ↓
기존 Data Graph
  ↓
Game System
  ↓
State Change
```

이 구조를 만들고 이후 `analyze_game_systems.py`와 연결한다.

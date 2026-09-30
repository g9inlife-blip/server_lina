# 후킹/Runtime 계측 조사 계획

## 적용 조건

Burp Proxy만으로 Req/Rsp가 충분히 확인되지 않는 경우에 진행한다.

대표 증상:

- 게임만 HTTPS 연결 실패
- TLS handshake 오류
- 특정 endpoint만 실패
- HTTPS body가 보이지 않음
- 별도의 binary/custom protocol 사용
- 앱이 사용자 CA를 신뢰하지 않음

## 조사 순서

### 1. 앱 구조 확인

정적 분석으로 다음을 확인한다.

- UnityWebRequest
- DownloadHandler
- UploadHandler
- HTTP client 구현
- OkHttp 계열
- libcurl
- IL2CPP native networking
- custom networking
- TLS 관련 native library

### 2. 상위 계층 우선

가능하면 암호화 전 HTTP 요청/응답이 존재하는 계층에서 확인한다.

목표:

```
URL
Method
Headers
Request body
Response status
Response body
```

### 3. Native 계층

상위 계층에서 확인할 수 없을 때 native 네트워크 함수와 호출 흐름을 정적/동적 분석으로 조사한다.

## 주의

후킹의 목적은 정상적인 테스트 환경에서 애플리케이션의 네트워크 데이터 흐름을 분석하는 것이다.

인증정보 탈취, 타인의 계정 접근, 서버 인증 우회, 제3자 서비스의 접근제어 회피를 목적으로 사용하지 않는다.

## 결과물

후킹을 통해 확인한 내용은 반드시 다음과 같이 기존 Req/Rsp 기록과 연결한다.

```
Hook Point
  ↓
Request/Response
  ↓
Endpoint
  ↓
Record ID
  ↓
Game System
```

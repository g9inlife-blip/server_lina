# LDPlayer + Burp 환경 구성

## 1. 준비

- Windows PC
- LDPlayer
- Burp Suite Community/Professional
- ADB
- 분석 대상 APK
- 테스트 계정

## 2. LDPlayer ADB 확인

Windows CMD/PowerShell:

```cmd
adb devices
```

LDPlayer가 표시되는지 확인한다.

여러 인스턴스를 사용하는 경우 각 인스턴스의 ADB 포트를 확인하여 대상 인스턴스를 명확히 한다.

## 3. PC IP 확인

```cmd
ipconfig
```

LDPlayer와 PC가 접근 가능한 네트워크 인터페이스의 IPv4 주소를 사용한다.

예:

```
192.168.0.10
```

## 4. Burp Listener

Burp에서 Proxy Listener를 다음처럼 설정한다.

```
Bind address: 0.0.0.0
Port: 8080
```

Windows 방화벽이 연결을 차단하는 경우 해당 포트에 대한 로컬 네트워크 접근을 허용한다.

## 5. LDPlayer Proxy

LDPlayer Android 설정에서 연결된 Wi-Fi의 Proxy를 수동으로 지정한다.

```
Proxy: Manual
Host: PC의 IPv4 주소
Port: 8080
```

주의:

```
127.0.0.1
```

은 일반적으로 LDPlayer 자신을 가리키므로 PC의 LAN IP와 혼동하지 않는다.

## 6. 1차 연결 테스트

게임보다 먼저 LDPlayer 브라우저에서 HTTP 사이트를 열어 Burp HTTP history에 요청이 나타나는지 확인한다.

성공 기준:

```
LDPlayer
  ↓
PC:8080
  ↓
Burp HTTP history
  ↓
Internet
```

## 7. HTTPS 테스트

Burp CA 인증서를 내보내고 LDPlayer Android 인증서 설정에서 설치한다.

Android 버전에 따라 사용자 CA를 앱이 신뢰하지 않을 수 있다. 따라서 브라우저 HTTPS가 보인다고 해서 게임도 반드시 보이는 것은 아니다.

## 8. 게임 테스트

먼저 게임 실행 → 로그인까지만 수행한다.

저장 대상:

- 요청 URL
- HTTP method
- request headers
- request body
- response status
- response headers
- response body
- timestamp

## 9. 실패 유형 기록

다음과 같은 경우 별도 기록한다.

- TLS handshake 실패
- SSL 오류
- 연결 거부
- 앱 로그인 실패
- 특정 endpoint만 실패
- 브라우저는 정상인데 게임만 실패

이 경우 Certificate Pinning 또는 별도 네트워크 계층 사용 여부를 조사한다.

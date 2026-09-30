# Frida 스크립트

## justice_hook.js (v4.8)
메인 후킹 스크립트. 로그인 플로우 전체 추적.

**캡처 항목:**
- `ProtocolGame_HttpRequest.V4_POST_Login` — 파라미터
- `ProtocolGame_HttpRequest.Sign` — content, dict, sign (BEFORE/AFTER)
- `ProtocolGame_HttpRequest.GetDefaultParams` — 기본 파라미터
- `UnityWebRequest` — URL, 메서드, 헤더, 바디 (`[HTTP_CREATE]`, `[HTTP_HEADER]`)
- `DownloadHandler.get_text` — HTTP 응답 바디 (`[HTTP_RESP]`)
- `UnityWebRequest.get_responseCode` — HTTP 상태 코드
- `ServerConst.GetURL` — 서버 URL (`[SERVER_URL]`, 리다이렉트용)
- `String.Join` / `MD5HashString` — Sign 내부 추적

**실행:**
```bash
frida -H 127.0.0.1:27042 -n Gadget -l research/frida/justice_hook.js
```

**아직 부족한 것:**
- [ ] HTTP 응답 바디 캡처 (DownloadHandler 후킹 필요)
- [ ] `ServerConst.GetURL` 후킹 (URL 리다이렉트용)

## captures/
캡처된 로그 저장소.
- `captures/http/` — HTTP 요청/응답 로그

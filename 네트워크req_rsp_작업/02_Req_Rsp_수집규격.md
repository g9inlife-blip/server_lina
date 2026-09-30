# Req/Rsp 수집 규격

## 1. 원본 보존

원본 데이터는 변경하지 않는다.

권장 구조:

```
네트워크req_rsp_작업/
├─ raw/
│  ├─ login/
│  ├─ lobby/
│  ├─ dungeon/
│  ├─ battle/
│  ├─ gacha/
│  ├─ shop/
│  └─ reward/
├─ normalized/
│  ├─ requests.ndjson
│  ├─ responses.ndjson
│  ├─ sessions.ndjson
│  └─ errors.ndjson
└─ analysis/
```

## 2. Request 표준

```json
{
  "timestamp": "",
  "session_id": "",
  "direction": "request",
  "method": "POST",
  "endpoint": "",
  "headers": {},
  "body": {}
}
```

## 3. Response 표준

```json
{
  "timestamp": "",
  "session_id": "",
  "direction": "response",
  "endpoint": "",
  "status": 200,
  "headers": {},
  "body": {}
}
```

## 4. 보안 데이터

실제 인증 토큰, 세션 토큰, 개인정보 등은 저장소에 평문으로 남기지 않는다.

분석용 데이터에서는 다음처럼 마스킹한다.

```
Authorization: Bearer <REDACTED>
Cookie: <REDACTED>
access_token: <REDACTED>
refresh_token: <REDACTED>
```

## 5. 행동 기록

각 Req/Rsp에는 가능하면 사용자의 게임 행동을 연결한다.

예:

```
action: dungeon_enter
stage_id: 10001
```

## 6. Before / After

게임 상태 변경을 확인하기 위해 행동 전후 상태를 함께 저장한다.

예:

```
Before:
gold=10000
stamina=20

Action:
dungeon_enter

After:
gold=10000
stamina=19
```

이를 통해 Request/Response와 실제 상태 변화를 연결한다.

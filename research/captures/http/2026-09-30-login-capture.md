# 2026-09-30 HTTP 로그인 캡처 (v4.8)

## AllInOne 응답 (API 목록)

```json
{
  "v": "3.1.0",
  "Keys": [
    {"Key": "API_ApplePayVerify", "URL": "https://ac.aliother.com/v3/pay/apple"},
    {"Key": "API_Anon", "URL": "https://ac.aliother.com/v3/account/anon"},
    {"Key": "API_Login", "URL": "https://ac.aliother.com/v5/account/login"},
    {"Key": "API_Allin1", "URL": "https://ac.aliother.com/v3/ain1"},
    {"Key": "API_Mail", "URL": "https://gm.aliother.com/mail"},
    {"Key": "API_GIFT", "URL": "https://ac.aliother.com/v3/gift"},
    {"Key": "API_SaveProps", "URL": "https://ac.aliother.com/v3/data/save/props"}
  ],
  "m": "official",
  "IP": "211.234.196.74",
  "Desc": "成功",
  "Status": 0,
  "Servers": [{"Host": "ac.aliother.com", "Port": 8000}],
  "Assets": [{"CDN": "https://oss01.aliother.com/v310/202608022111/", "Version": "3.1.88"}]
}
```

## 로그인 요청

- URL: `https://ac.aliother.com/v5/account/login?271799` (?뒤 숫자는 매번 변경)
- Method: POST
- Content-Type: `application/x-www-form-urlencoded`
- Body (URL-encoded):
```
n=639263747531220840&d=cbcfdf10d56e57a89f7cb19a491d139e&r=7&v=3.1.0&m=official&t=<base64>&u=witchwind2&p=witchwind2&method=&platform=google&p2=logout&sign=8fdb81dda6d1aab1970e967f0e2dd57e
```

## 로그인 응답

```json
{
  "logout_ex_time": 0,
  "sign": "8fdb81dda6d1aab1970e967f0e2dd57e",
  "t": "<요청과 동일한 t>",
  "platform": "google",
  "UserId": 861197,
  "p2": "logout",
  "FCMStatus": 4,
  "v": "3.1.0",
  "RealName": true,
  "m": "official",
  "u": "witchwind2",
  "Age": 27,
  "Status": 0,
  "Desc": "成功",
  "First": 0,
  "method": "",
  "d": "cbcfdf10d56e57a89f7cb19a491d139e",
  "p": "witchwind2",
  "r": "7",
  "n": "639263747531220840",
  "Token": "<새 토큰, 요청의 t와 다름>"
}
```

## SaveLoginToken

- arg[0]: UserId ("861197")
- arg[1]: 새 Token (응답의 Token)
- arg[2]: 0 (int)
- arg[3]: false (bool)
- arg[4]: 0x0 (SDKLoginType)

## 핵심 발견

1. **응답에 새 Token이 옴** — 요청의 t와 다름. `SaveLoginToken`으로 저장됨.
2. **URL 뒤 `?271799`** — 매 요청마다 바뀌는 숫자 (캐시 방지용 추정)
3. **게임 서버**: `ac.aliother.com:8000` (KCP/TCP용)
4. **CDN**: `https://oss01.aliother.com/v310/202608022111/`

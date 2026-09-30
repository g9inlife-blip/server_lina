# 2026-09-29 GetDefaultParams Helper 정적분석 결과

- 기준: `research/reports/2026-09-29-Ghidra-Listing-정적분석-작업기준.md`
- 대상: `ProtocolGame_HttpRequest$$GetDefaultParams @ 00ddbf58`
- 원본: `research/Ghidra_Listing_txt/PR.txt`, `AL/`, `AP.txt`
- 환경: ARM64 실기기 + hook-patched APK

## 1. 핵심 결론

`GetDefaultParams`의 정적 호출 순서와 runtime 로그인 body를 대조한 결과:

| key | 생성 경로 | runtime 값 | 상태 |
|---|---|---|---|
| `n` | `DateTime.Now.Ticks.ToString()` | `639262781542097130` | 확정 |
| `d` | `Ali.get_deviceUniqueIdentifier()` | `cbcfdf10d56e57a89f7cb19a491d139e` | 확정 |
| `r` | `get_retailID()` | `7` | 확정 |
| `v` | `get_buildVerion()` | `3.1.0` | 확정 |
| `m` | `AppConst.get_Mark()` | `official` | 확정 |
| `t` | `get_Token()` | 긴 Base64 값 | 확정 |
| advertisingIdentifier | `Ali.get_advertisingIdentifier()` | 로그인 body에 없음 | 조건부 |

**중요:** runtime body의 긴 Base64 `t`는 advertising identifier가 아니라 `get_Token()` 반환값이다.

## 2. GetDefaultParams 흐름

```text
GetDefaultParams @ 00ddbf58
  -> DateTime.Now -> Ticks -> ToString -> n
  -> Ali.get_deviceUniqueIdentifier @ 00e0a148 -> d
  -> Ali.get_advertisingIdentifier @ 00e0a494
       -> IsNullOrEmpty
       -> 비어 있지 않을 때만 Dictionary에 추가
  -> get_retailID @ 00dd949c -> r
  -> get_buildVerion @ 00dd90bc -> v
  -> AppConst.get_Mark @ 016dacf8 -> m
  -> get_Token @ 00dd9534 -> t
       -> IsNullOrEmpty 검사 후 Dictionary에 추가
```

## 3. n: timestamp

Listing에서 `DateTime.get_Now @ 02133d48`, `DateTime.get_Ticks @ 02132788`, `Int64.ToString @ 0214ed58`, `Dictionary.set_Item @ 0196e4c0` 순서가 확인된다.

runtime 값 `n=639262781542097130`과 정확히 연결된다.

## 4. d: deviceUniqueIdentifier

`Ali$$get_deviceUniqueIdentifier @ 00e0a148`의 우선 경로는 singleton field `+0x420`에 연결된 delegate다.

fallback에서는 `UnityEngine.SystemInfo.get_deviceUniqueIdentifier @ 024d5ca0`를 사용한다. 값이 유효하지 않은 경우 PlayerPrefs를 확인하고, 없으면 `Guid.NewGuid -> Guid.ToString -> PlayerPrefs.SetString -> PlayerPrefs.Save` 경로로 저장한다.

따라서 현재 `d`는 장치 식별값 계열이며 Token 자체가 아니다.

## 5. r: retailID

`ProtocolGame_HttpRequest$$get_retailID @ 00dd949c`:

```text
singleton field +0xd0
  -> 값이 있으면 반환
  -> 없으면 SDKManager.get_Retail @ 00deb798
  -> Int32.ToString @ 0214dc44
```

runtime `r=7`과 연결된다.

## 6. v: build version

`ProtocolGame_HttpRequest$$get_buildVerion @ 00dd90bc`:

```text
singleton field +0xf0
  -> 값이 있으면 반환
  -> 없으면 AliothEngine.BuildVersionBindings.GetBuildVersion @ 0165561c
```

runtime `v=3.1.0`과 연결된다.

## 7. m: mark

`AppConst$$get_Mark @ 016dacf8`의 우선 경로는 singleton instance field `+0x28`이다.

fallback에서는 `AliothEngine.Android.VasDollyHelper$$GetChannel @ 016a857c`를 호출하고, 반환값이 비어 있는 경우 내부 분기에서 채널 문자열을 선택한다.

runtime 값은 `m=official`로 확정된다. 다만 이번 실행에서 `+0x28` 직접 경로인지 VasDolly fallback인지까지는 아직 확정하지 않는다.

## 8. t: Token

`ProtocolGame_HttpRequest$$get_Token @ 00dd9534`는:

```text
singleton field +0x100
  -> 값이 있으면 delegate 반환
  -> 없으면 global object 확인
       -> object +0x20
       -> field +0x28
```

구조다.

V4 로그인 body에서 `t=` 뒤에 들어간 긴 Base64 문자열은 이 getter 직후 Dictionary에 추가된다. 따라서 `t=Token`으로 확정한다.

이전의 `t=advertisingIdentifier` 추정은 폐기한다.

## 9. 현재 로그인 body 구조

```text
GetDefaultParams
  n = DateTime.Now.Ticks.ToString()
  d = deviceUniqueIdentifier
  advertisingIdentifier = 조건부
  r = retailID
  v = buildVersion
  m = mark
  t = Token
       |
       v
V4_POST_Login 추가
  u
  p
  method
  platform
  p2
       |
       v
Sign
  -> sorted Dictionary keys
  -> values
  -> String.Join(".")
  -> MD5HashString
  -> sign
```

현재 runtime body는 다음 구조다.

```text
n=639262781542097130&d=cbcfdf10d56e57a89f7cb19a491d139e&r=7&v=3.1.0&m=official&t=<Token>&u=witchwind3&p=witchwind3&method=&platform=google&p2=logout&sign=2d4ae03ee9014998502caf2046c002a3
```

## 10. 현재 분석 상태

| 항목 | 상태 |
|---|---|
| n 생성 | 확정 |
| d 생성 | 확정 |
| advertisingIdentifier 호출 | 확정 |
| advertisingIdentifier 로그인 포함 여부 | 미포함 확인 |
| r 생성 | 확정 |
| v 생성 | 확정 |
| m 반환값 | `official` 확정 |
| m의 실제 분기 경로 | 추가 확인 필요 |
| t 생성 getter | 확정 |
| t의 최초 원천 | 추가 분석 필요 |
| Sign 입력 구성 | 확정 |
| HTTP form 결과 | runtime으로 확정 |
| PCAP byte-level 대응 | 다음 단계 |

## 11. 다음 작업

### 1순위: Token 원천 추적

현재 가장 중요한 미해결 지점은 `get_Token`의 singleton field `+0x100` 또는 fallback global object `+0x20/+0x28`에 **언제 값이 기록되는가**이다.

다음에는 해당 field의 write XREF를 추적하여 긴 Base64 Token이 서버 response에서 저장되는지, 로컬 저장값인지, 암호화/인코딩 결과인지 확인한다.

### 2순위: 로그인 PCAP byte-level 대조

대상:

`research/PCAP/PCAPdroid_29_9월_11_12_23_어플시작_로그인_메인까지.pcap`

runtime 기준:

```text
POST /v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
body_len = 551
```

비교 순서:

```text
PCAP TCP stream
 -> HTTP request 탐색
 -> URL / method 확인
 -> body 추출
 -> runtime body와 byte-for-byte 비교
 -> Content-Length / TCP sequence 확인
 -> HTTP response 추출
```

### 3순위: response 처리

request가 PCAP에서 정확히 일치하면 `RequestCoroutine -> UnityWebRequest.Post -> Send -> isDone -> response -> OnDone/OnFail` 순으로 로그인 response까지 연결한다.

## 12. 분석 원칙

함수명만으로 역할을 확정하지 않는다.

```text
Ghidra Listing
+ 호출 관계
+ 인자/반환값
+ runtime 실제 값
+ PCAP 실제 bytes
```

가 일치하는 경우에만 확정한다.

이번 단계에서는 특히 `t`를 `get_Token()`으로 확정한 것이 핵심 진전이다.


## 13. Token 응답 경로 추가 확인

### SDKHandler_None.OnGetLoginToken @ 00de4e68

Listing에서 로그인 토큰 HTTP 응답 처리 흐름이 확인된다.

```text
UnityWebRequest / HttpRequest response
    |
    +-- responseCode == 200
    |
    +-- DownloadHandler.get_text
    |
    +-- JsonUtility.FromJson<Response_GetLoginToken>
    |
    +-- Response_GetLoginToken 객체 생성
    |
    +-- LoginManager.SaveLoginToken @ 00dd64a0
    |
    +-- LoginManager.LoginGameServer @ 00dd6910
```

`OnGetLoginToken`에서 `DownloadHandler.get_text @ 026d7308`, `JsonUtility.FromJson<object> @ 0179cfb4`, `UnityWebRequest.get_responseCode @ 026d61ac`, `LoginManager.SaveLoginToken @ 00dd64a0`가 직접 연결된다.

따라서 현재 분석에서는 `t`를 단순히 로컬에서 새로 생성되는 문자열로 볼 근거가 없다. **로그인 토큰 응답 모델 → 저장 → 이후 GetDefaultParams에서 사용**이라는 흐름을 우선 가설로 둔다.

### Response_GetLoginToken

`Response_GetLoginToken @ 00ddddd0`는 별도의 response model이며 `TASK-006-result.md`에서 다음 필드가 확인되어 있다.

```text
Status
UserId
Desc
First
method
BindFacebook
BindGoogle
BindGameCenter
RealName
FCMStatus
logout_ex_time
...
```

`OnGetLoginToken`에서 `JsonUtility.FromJson<Response_GetLoginToken>` 결과를 여러 field offset으로 읽은 뒤 `SaveLoginToken`에 넘기는 구조가 확인된다.

현재 단계에서 **response JSON의 어느 field가 `get_Token()`의 `+0x100` field와 정확히 동일한지는 아직 확정하지 않는다.** 다음 정적 분석 대상은 `SaveLoginToken`의 인자 대응과 `ProtocolGame_HttpRequest` singleton `+0x100`에 대한 write XREF다.

## 14. PCAP 분석 상태

대상 PCAP은 GitHub repository에 존재하는 것을 확인했다.

```text
research/PCAP/PCAPdroid_29_9월_11_12_23_어플시작_로그인_메인까지.pcap
size = 92,018 bytes
blob = bd493ddd01015b8be144cae4cdea09c29092c48a
```

현재 GitHub connector는 binary blob 자체를 UTF-8 파일로 읽을 수 없기 때문에 이 단계에서는 PCAP 내부 packet bytes를 직접 추출하지 못했다. 따라서 **PCAP request/response byte-level 대조는 아직 미실행** 상태로 유지한다. PCAP 파일이 로컬 분석 환경에 제공되면 기존 `pcap_dh_validator.py`/TCP reassembly 방식으로 바로 이어갈 수 있다.

## 15. 다음 정적 분석 우선순위 변경

```text
1. SaveLoginToken @ 00dd64a0 인자 의미 확정
        |
2. Response_GetLoginToken 각 field와 인자 대응
        |
3. LoginManager에 저장되는 Last_SaveLoginInfo / UserId / token 관계 확인
        |
4. ProtocolGame_HttpRequest.get_Token @ 00dd9534의 singleton +0x100
   write XREF 확인
        |
5. 동일 값인지 runtime hook으로 검증
        |
6. PCAP login request/response byte-level 대조
```

이 순서로 진행하면 `t`의 의미뿐 아니라 **어느 로그인 단계에서 최초로 서버가 token을 반환하고, 어느 객체가 그 값을 보관하여 다음 요청에 재사용하는지**까지 연결할 수 있다.

## 16. 2026-09-29 Runtime Token 흐름 검증 결과

이번 runtime hook에서 로그인 전후의 Token 흐름을 직접 관찰했다.

### 16.1 로그인 요청 직전

```text
V4_POST_Login
  -> GetDefaultParams
       -> ProtocolGame_HttpRequest.get_Token()
       -> t 항목 생성
  -> Sign
  -> UnityWebRequest 생성
  -> POST /v5/account/login
```

로그에서 GetDefaultParams 시점의 get_Token()은 비어 있지 않은 기존 Token을 반환했고, 같은 값이 t에 들어간 뒤 Sign 입력과 HTTP form body에 포함되었다.

즉 **이번 로그인 요청의 t는 이번 요청의 response로 새로 저장되는 Token이 아니다.** 요청보다 먼저 존재하던 Token이다.

### 16.2 로그인 응답 이후

로그인 HTTP 요청 전송 직후 다음 호출이 관찰되었다.

`LoginManager.SaveLoginToken(System.String, System.String, System.Int32, System.Boolean, SDKLoginType)`

runtime 인자 구조:

```text
arg[0] = 사용자 식별 문자열
arg[1] = 새로 저장되는 Token 문자열
arg[2] = logout_ex_time 계열 정수
arg[3] = First 계열 boolean
arg[4] = SDKLoginType
```

arg[1]은 앞서 요청의 GetDefaultParams().t와 **다른 문자열**이었다.

따라서 다음과 같이 구분해야 한다.

```text
[기존 상태]
ProtocolGame_HttpRequest.get_Token()
        |
        +--> GetDefaultParams()['t']
        |
        +--> Sign
        |
        +--> /v5/account/login request

[서버 응답 처리]
login response
        |
        +--> Response_GetLoginToken
        |
        +--> LoginManager.SaveLoginToken(..., arg[1], ...)
                         |
                         +--> 새 Token 저장
```

### 16.3 현재 확정된 것과 미확정인 것

| 항목 | 결과 |
|---|---|
| t가 get_Token() 반환값인가 | 확정 |
| 로그인 request의 t가 request 전에 존재한 값인가 | 이번 runtime에서 확인 |
| SaveLoginToken(arg[1])이 response에서 전달된 새 Token인가 | 매우 강하게 연결됨; response field 매핑 정적 확인 필요 |
| SaveLoginToken(arg[1])과 request의 t가 동일한가 | **아님** |
| 이후 get_Token()이 SaveLoginToken(arg[1])을 반환하는가 | 아직 runtime 미확인 |
| get_Token +0x100과 SaveLoginToken 저장 위치가 동일한가 | 정적 write XREF 필요 |

### 16.4 다음 검증의 의미

이제 단순히 Token = login response Token이라고 가정해서는 안 된다. 정확한 모델은 다음 두 단계일 가능성이 높다.

```text
기존 로그인 상태 Token
        -> login request의 t
        -> 서버 인증
        -> login response의 새 Token
        -> SaveLoginToken
        -> 이후 게임 요청에서 재사용
```

따라서 다음 요청이 발생한 시점에 get_Token()을 다시 관찰하면 가장 중요한 연결고리를 확인할 수 있다.

SaveLoginToken.arg[1] == 이후 get_Token() 반환값

동일하다면 **서버가 반환한 새 Token → LoginManager 저장 → ProtocolGame_HttpRequest.get_Token() → 다음 요청의 t** 흐름을 runtime에서 확정할 수 있다.

## 17. 다음 작업 우선순위

1. LoginManager.SaveLoginToken @ 00dd64a0 Listing에서 실제 field write 확인
2. Response_GetLoginToken의 Token field와 SaveLoginToken.arg[1]의 대응 확인
3. ProtocolGame_HttpRequest.get_Token @ 00dd9534의 singleton +0x100 write XREF 확인
4. 로그인 완료 후 다음 API 호출에서 get_Token() 재호출을 잡아 SaveLoginToken.arg[1]과 동일성 확인
5. 동일성이 확인되면 다음 요청의 t와 Sign 입력까지 연결
6. 마지막으로 PCAP에서 request/response bytes를 대조

**주의:** runtime 로그에 실제 인증 Token이 출력되므로 보고서에는 실제 Token 문자열을 기록하지 않는다. 비교가 필요한 경우 로컬에서만 값의 길이/해시 또는 동일성으로 확인한다.

## 18. SaveLoginToken 정적 Listing 추가 확인

`LoginManager$$SaveLoginToken @ 00dd64a0`의 실제 ARM64 인자 및 field write를 확인했다.

### 18.1 인자 매핑

AArch64 호출 규약 기준으로:

```text
x0 = LoginManager this
x1 = arg[0] System.String
x2 = arg[1] System.String
x3 = arg[2] Int32
w4 = arg[3] Boolean
w5 = arg[4] SDKLoginType
```

Listing 초반에서 다음과 같이 이동한다.

```text
00dd64c8  mov w22,w5      ; arg[4]
00dd64cc  mov w24,w4      ; arg[3]
00dd64d0  mov w20,w3      ; arg[2]
00dd64d4  mov x25,x2      ; arg[1]  <-- Token 후보
00dd64d8  mov x19,x1      ; arg[0]
00dd64dc  mov x21,x0      ; this
```

따라서 runtime에서 관찰한 `SaveLoginToken arg[1]`은 정적으로도 두 번째 String 인자임이 확인된다.

### 18.2 arg[1] 실제 저장 위치

핵심 구간:

```text
00dd65b8  ldr x23,[x21, #0x20]
...
00dd65c4  str x25,[x26, #0x28]!
```

여기서 `x25 = arg[1]`이고 `x26 = x23`이므로:

```text
LoginManager +0x20 -> object
object +0x28 <- arg[1]
```

즉 `SaveLoginToken`은 runtime에서 확인된 새 Token을 `LoginManager` 내부의 `+0x20` 객체가 가진 `+0x28` 필드에 저장한다.

### 18.3 get_Token() fallback과의 구조적 일치

앞서 분석한 `ProtocolGame_HttpRequest$$get_Token @ 00dd9534` fallback은 다음 구조였다.

```text
global/singleton object
    +0x20 -> object
              +0x28 -> Token
```

이번 `SaveLoginToken` Listing은 다음을 직접 확인했다.

```text
LoginManager
    +0x20 -> object
              +0x28 <- SaveLoginToken(arg[1])
```

따라서 **`SaveLoginToken(arg[1])`과 `get_Token()` fallback이 동일한 `+0x20 -> +0x28` Token 저장 구조를 가리킬 가능성이 매우 높다.** 다만 `get_Token()`의 global/singleton 포인터가 이 `LoginManager` 인스턴스와 정확히 동일한 포인터라는 마지막 1단계는 runtime 또는 get_Token Listing의 global field까지 교차 확인하여 확정한다.

### 18.4 Token 흐름 현재 모델

현재까지의 증거를 합치면 다음 구조가 가장 일관된다.

```text
[기존 저장 Token]
LoginManager +0x20 -> object +0x28
              |
              +--> ProtocolGame_HttpRequest.get_Token()
              |
              +--> GetDefaultParams()['t']
              |
              +--> Sign
              |
              +--> /v5/account/login request

[로그인 response]
Response_GetLoginToken.Token
              |
              v
LoginManager.SaveLoginToken(..., arg[1], ...)
              |
              v
LoginManager +0x20 -> object +0x28
              |
              +--> 이후 get_Token()
              +--> 이후 요청의 t
```

여기서 이번 runtime 로그가 보여준 `request t != SaveLoginToken arg[1]`은 오히려 이 모델과 일치한다. **로그인 요청은 기존 Token을 사용하고, 응답 후 새 Token으로 저장값을 갱신하는 형태**다.

### 18.5 다음 runtime 검증 한 번이면 되는 것

로그인 응답 직후 발생하는 다음 API 요청에서:

```text
[TOKEN_SAVE] arg[1]
        |
        +---- compare ----+
                         |
[TOKEN_GET] return       |
                         v
                    동일 여부
```

를 확인하면 된다.

특히 현재 hook에서 로그인 직후 AssetBundle 요청들이 보였으므로, **그 다음 `GetDefaultParams`/`get_Token` 호출이 발생하는 로그를 확보하는 것이 다음 핵심 검증**이다.

실제 Token 문자열은 보고서에 기록하지 않고, 로컬 runtime에서는 동일성만 확인하는 방식이 적절하다.


## 19. 2026-09-30 작업 이어서 — Token 저장/조회 동일성 검증 준비

현재 로그인 분석의 다음 단계는 Token의 저장 원천과 이후 조회값의 동일성을 확정하는 것이다.

정적 분석상 SaveLoginToken @ 00dd64a0은 x2(arg[1])을 LoginManager +0x20이 가리키는 객체의 +0x28에 저장한다. get_Token @ 00dd9534의 fallback도 +0x20 → +0x28 구조를 읽는다. 따라서 동일 저장 슬롯일 가능성이 높지만, 동일 객체라는 사실은 아직 runtime으로 확정하지 않는다.

현재 research/justice_hook.js에는 이미 비교 기능이 있다. SaveLoginToken의 arg[1]을 fingerprint로 저장하고, 이후 get_Token() 반환값을 fingerprint로 비교하여 MATCH/MISMATCH만 출력한다. 실제 인증 Token plaintext는 출력하지 않는다.

### 다음 검증

실기기 + 현재 hook-patched APK에서 로그인 후 다음 일반 API 요청까지 관찰한다.

검증 목표:

SaveLoginToken(arg[1]) fingerprint = 이후 get_Token() fingerprint = 다음 GetDefaultParams()['t']의 Token fingerprint

MATCH가 확인되면 다음 흐름을 runtime에서 연결할 수 있다.

login response → SaveLoginToken(arg[1]) → LoginManager +0x20/+0x28 → get_Token() → GetDefaultParams()['t'] → Sign → 다음 HTTP request

단, MATCH만으로 Response_GetLoginToken의 정확한 JSON field 이름까지 확정하지 않는다. 그 부분은 SDKHandler_None.OnGetLoginToken @ 00de4e68의 field read와 SaveLoginToken 인자 전달을 추가로 대조한다.

### 병행 정적 분석 대상

1. SDKHandler_None.OnGetLoginToken @ 00de4e68
2. Response_GetLoginToken의 실제 field 접근
3. SaveLoginToken 호출 직전 field read
4. get_Token의 global pointer와 LoginManager singleton의 동일성

함수명이나 동일 offset만으로 의미를 확정하지 않고 Listing + argument mapping + field offset + runtime fingerprint + 다음 request를 함께 사용한다. 실제 인증 Token 문자열은 보고서에 기록하지 않는다.


## 20. 2026-09-30 OnGetLoginToken 인자 대응 추가 확정

`SDKHandler_None$$OnGetLoginToken @ 00de4e68` 전체 Listing을 다시 확인했다. 로그인 응답 객체는 `x19`에 유지되며, 성공 경로에서 다음 값들이 직접 읽힌다.

- `x19 + 0x18` → `Int64.ToString()` → `SaveLoginToken` 첫 번째 String 인자
- `x19 + 0x20` → `SaveLoginToken` 두 번째 String 인자
- `x19 + 0x30` → `SaveLoginToken` 세 번째 Int32 인자
- `w20` → `SDKManager.GetSDKLoginType()` 결과 → `SaveLoginToken` 다섯 번째 인자
- 네 번째 Boolean 인자는 `0`

핵심 Listing:

`00de5200 add x0,x19,#0x18`

`00de5204 mov x1,xzr`

`00de5208 bl 0x0214ed58`

`00de5210 ldr w3,[x19,#0x30]`

`00de5214 ldr x2,[x19,#0x20]`

`00de521c mov x0,x21`

`00de5220 mov w4,wzr`

`00de5224 mov w5,w20`

`00de5228 bl 0x00dd64a0`

AArch64 호출 규약을 적용하면:

`SaveLoginToken(x0=this, x1=String(x19+0x18), x2=String(x19+0x20), x3=Int32(x19+0x30), x4=false, x5=SDKLoginType)`

이다.

기존 `TASK-006-result.md`에서 `Response_GetLoginToken`의 모델 필드에 `Token`, `First`, `logout_ex_time` 등이 존재함을 확인했고, 이전 runtime에서 `SaveLoginToken`의 두 번째 String 인자(arg[1])가 서버 응답 후 새 Token으로 관찰되었다. 따라서 현재 가장 강한 정적/런타임 대응은:

`Response_GetLoginToken +0x20 → SaveLoginToken(arg[1]) → LoginManager 저장 슬롯`

이다.

`+0x18`은 `logout_ex_time` 계열 값과 일치하는 후보이며, `+0x30`의 정확한 response field 명칭은 별도 field layout 증거가 추가되기 전까지 확정하지 않는다.

### 현재 Token 증거 사슬

`HTTPS login response`

→ `DownloadHandler.get_text`

→ `JsonUtility.FromJson<Response_GetLoginToken>`

→ `Response_GetLoginToken 객체`

→ `x19 + 0x20`

→ `SaveLoginToken(arg[1])`

→ `LoginManager +0x20 → object +0x28`

→ 이후 `get_Token()` 후보 저장값

→ `GetDefaultParams()['t']`

→ `Sign`

→ 다음 HTTP request

여기서 마지막 `SaveLoginToken(arg[1]) → 이후 get_Token()`만 runtime MATCH로 확정하면 Token의 저장/재사용 경계가 완성된다.

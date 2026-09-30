# Ghidra Listing 자료 구조 및 정적분석 작업 기준

- 작성일: 2026-09-29
- 저장소: `g9inlife-blip/arme`
- 대상: `research/Ghidra_Listing_txt`
- 목적: Ghidra Listing 자료를 runtime hook 및 PCAP 분석과 연결하여 함수 역할을 확정

---

## 1. Listing 자료 구성

`research/Ghidra_Listing_txt`에는 Ghidra에서 추출한 Listing 결과가 함수명 시작 문자열 기준으로 묶여 ZIP으로 저장되어 있다.

예:

```text
AB.zip
AC.zip
AD.zip
...
XL.zip
...
ZH.zip
```

각 ZIP은 함수명/Listing의 시작 문자열을 기준으로 묶은 자료이므로 필요한 함수 후보를 전체 Listing에서 찾을 때 검색 범위를 줄이는 용도로 사용한다.

### FUN_ 자료

```text
FUN_.zip
```

은 자동 명명 스크립트로 실제 함수명이 부여되지 않은 `FUN_*` 함수들을 별도로 모아둔 자료다.

따라서:

- 일반 ZIP: 이미 함수명이 식별된 함수 중심
- `FUN_.zip`: 아직 의미 있는 함수명이 없는 함수 중심

으로 구분한다.

---

## 2. 현재 런타임에서 확보한 로그인 경로

2026-09-29 ARM64 실기기 + hook-patched APK 실행에서 로그인 request가 다음 경로로 확인되었다.

```text
ProtocolGame_HttpRequest.V4_POST_Login
        ↓
GetDefaultParams
        ↓
Sign
        ↓
AliothEngine.Net.HttpRequest
        ↓
UnityWebRequest
        ↓
UploadHandlerRaw(byte[])
        ↓
POST /v5/account/login
```

현재 Sign 알고리즘은 정적 + 런타임으로 확정되어 있다.

```text
Dictionary.Keys
    ↓
OrderBy(x => x)
    ↓
정렬된 key의 value
    ↓
content 추가
    ↓
String.Join(".", values)
    ↓
MD5HashString
    ↓
dict["sign"]
```

---

## 3. 이번 실행에서 확보한 HttpRequest method

`AliothEngine.Net.HttpRequest`에서 다음 메서드가 확인되었다.

```text
get_isError()
get_PingTime()
set_PingTime()
RequestCoroutine()
CheckTimeout()
get_IsDone()
set_Headers()
get_Headers()
set_Timeout()
get_Timeout()
set_OnDone()
set_OnFail()
set_OnDisposed()

.ctor(MonoBehaviour,string)
.ctor(MonoBehaviour,string,string)
.ctor(MonoBehaviour,string,float)
.ctor(MonoBehaviour,string,Dictionary<string,string>)

AddHeader(string,string)
AddData(string,string)
AddRangeData(Dictionary<string,string>)

AddBinaryData(string,byte[])
AddBinaryData(string,byte[],string)
AddBinaryData(string,byte[],string,string)

Request()
Dispose()
CheckConnection(string,Action<bool>)
CreateURL(List<string>,string,Dictionary<string,string>)
ResetCache(string)
```

### 현재 우선 분석 대상

```text
AddData
AddRangeData
Request
CreateURL
.ctor(...)
```

이 다섯 영역을 먼저 분석한다.

---

## 4. 왜 AddData부터 확인하는가

실제 로그인 body는:

```text
n=...&d=...&r=7&v=3.1.0&m=official&...&sign=2d4ae03ee9014998502caf2046c002a3
```

형태의 `application/x-www-form-urlencoded` 데이터다.

따라서 다음 질문을 코드에서 확인해야 한다.

1. dictionary가 어떤 순서로 body에 들어가는가?
2. key/value URL encoding은 어디서 수행하는가?
3. `&`와 `=`는 어디서 생성되는가?
4. 빈 문자열 `method=`는 어떻게 보존되는가?
5. `sign`은 언제 추가되는가?
6. `AddData`와 `AddRangeData` 중 어느 쪽이 로그인 body를 구성하는가?
7. `CreateURL`은 URL query와 body 중 어느 부분을 담당하는가?

---

## 5. 실제 런타임 증거

ARM64 실기기에서 v4.6 hook으로 다음이 확인되었다.

### UploadHandlerRaw

```text
UploadHandlerRaw(byte[])
body_len = 551
```

실제 body:

```text
n=639262781542097130&d=cbcfdf10d56e57a89f7cb19a491d139e&r=7&v=3.1.0&m=official&t=jLDohEUPbopnwARSF4L%2fERqOUc1bvMSJCWDvIQqHkF0Qjn%2fS2xt%2f5CAoaxoYsTQ0oEeS7l1xEy8U2TNzM%2br9wJ8qGD8B%2f3ItbtOa7IDcauHiZnHoKIUnDAQQGbUdLia3D1BNXW70lzjbVmA%2f0%2bRuQUpa1n6Gj881gOEgtovFxkbYptUVUEByYWgkhJcuqW%2fVv25Pm95ikRUXVXKlAGJq9G5Demi43jfStGJBdE3F692g3JaBkfGRoDgH%2f92BIT7s%2fI%2f9Tt7jDH6p0uJdHr9GEVVwMlfnlL%2bWhfthrijayY6GyziOg6Qhn7NjK1NkHYxoOE125o5gV9e1Dr4qsgC60Q%3d%3d&u=witchwind3&p=witchwind3&method=&platform=google&p2=logout&sign=2d4ae03ee9014998502caf2046c002a3
```

HTTP:

```text
POST https://ac.aliother.com/v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
```

이 값은 이후 Ghidra 정적 분석의 검증 기준으로 사용한다.

---

## 6. Ghidra 분석 방법

### 6.1 이름이 있는 함수

먼저 Listing ZIP에서 직접 함수명을 검색한다.

우선순위:

```text
AliothEngine.Net.HttpRequest$$AddData
AliothEngine.Net.HttpRequest$$AddRangeData
AliothEngine.Net.HttpRequest$$Request
AliothEngine.Net.HttpRequest$$CreateURL
AliothEngine.Net.HttpRequest$$.ctor
```

함수명에 `$$` 표기가 없는 경우에도 마지막 메서드명 기준으로 검색한다.

### 6.2 호출 함수 추적

각 함수에서 다음을 기록한다.

```text
- 호출 대상
- 호출 순서
- 문자열 literal
- Dictionary/List 관련 API
- StringBuilder 관련 API
- URL encode 관련 API
- byte[] 생성/복사
- UTF-8/Encoding 변환
- UnityWebRequest 생성
- UploadHandlerRaw 호출
```

### 6.3 FUN_ helper 추적

이름이 없는 helper가 발견되면 `FUN_.zip`에서 해당 주소의 Listing을 찾는다.

단순히 함수명만 보고 역할을 추정하지 않는다.

다음 증거가 있어야 의미를 부여한다.

```text
호출 위치
+
인자 형태
+
반환값
+
문자열/상수
+
호출 대상
+
runtime 결과
```

---

## 7. 함수 역할 확정 기준

함수 역할은 다음 3개 자료가 일치할 때 확정한다.

```text
Ghidra Listing
    ↓
정적 호출 관계 / 데이터 흐름

Runtime Hook
    ↓
실제 인자 / 반환값 / 호출 시점

PCAP
    ↓
실제 네트워크 bytes
```

예를 들어 `AddData`가:

```text
key + "=" + URL-encoded(value)
```

를 생성한다면 실제 로그인 body의 해당 부분과 일치하는지 확인한다.

---

## 8. PCAP과 연결

로그인 PCAP:

```text
research/PCAP/PCAPdroid_29_9월_11_12_23_어플시작_로그인_메인까지.pcap
```

현재 확보한 runtime request:

```text
POST /v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
body_len: 551
sign: 2d4ae03ee9014998502caf2046c002a3
```

다음 단계에서는 PCAP에서 동일 request를 찾아:

```text
URL
HTTP method
Content-Type
Content-Length
body
TCP sequence
response
```

를 비교한다.

PCAP과 runtime body가 정확히 일치하면 로그인 HTTP 경로가 완전히 연결된다.

---

## 9. 현재 작업 우선순위

### 1순위 — HttpRequest

```text
AddData
AddRangeData
CreateURL
Request
.ctor
```

### 2순위 — URL/form serialization helper

```text
Uri.EscapeDataString
WWWForm
StringBuilder
Encoding.UTF8
byte[]
```

등과 유사한 동작을 하는 함수 탐색.

### 3순위 — response

로그인 response를 처리하는:

```text
RequestCoroutine
OnDone
OnFail
get_IsDone
```

경로를 확인한다.

### 4순위 — 로그인 이후 API

로그인 후 메인 화면까지 발생하는 API 요청과 AssetBundle 요청을 구분한다.

### 5순위 — TCP/KCP/DH64

기존:

```text
Alioth.S1.Common.DH64
Alioth.S1.Net.KCPTube
Alioth.S1.Net.TCPTube
```

분석과 연결하여 인게임 데이터 통신 경로를 확정한다.

---

## 10. 실기기 분석 환경 기준

현재 hook 분석 환경은:

```text
ARM64 실기기
+
hook-patched APK
```

이다.

**LDPlayer/x86 에뮬레이터를 현재 hook 실행 환경으로 사용하지 않는다.**

따라서 이후 실행 지시 및 문서에서는 실기기 기준으로 작성한다.

---

## 11. 다음 작업에서 사용자가 제공할 자료

현재 v4.6 로그인 body는 이미 충분히 확보되었으므로 다시 hook을 실행할 필요는 없다.

다음 사용자 작업은 Ghidra에서 우선 다음 함수의 Listing/decompile 내용을 확보하는 것이다.

```text
AliothEngine.Net.HttpRequest$$AddData
AliothEngine.Net.HttpRequest$$AddRangeData
AliothEngine.Net.HttpRequest$$CreateURL
AliothEngine.Net.HttpRequest$$Request
AliothEngine.Net.HttpRequest$$.ctor
```

각 함수의:

- 시작 주소
- 전체 Listing
- decompile
- 호출되는 FUN_ 함수

가 있으면 된다.

이 자료를 현재 `Ghidra_Listing_txt`와 대조하여 로그인 body 생성 과정을 정리한다.

---

## 12. 결론

현재 단계의 핵심은 Sign 알고리즘 재분석이 아니다.

Sign은 다음과 같이 확정되었다.

```text
sort(keys)
→ values
→ content
→ Join(".")
→ MD5
→ sign
```

그리고 실제 HTTP body까지 확보되었다.

따라서 다음 분석 목표는:

```text
Sign 결과
    ↓
HttpRequest.AddData/AddRangeData
    ↓
form-urlencoded serialization
    ↓
HttpRequest.Request
    ↓
UnityWebRequest
    ↓
UploadHandlerRaw
    ↓
PCAP
```

를 Ghidra 코드 수준에서 연결하는 것이다.

`Ghidra_Listing_txt`의 이름 있는 함수 묶음과 `FUN_.zip`을 이 작업의 정적 분석 원본으로 사용한다.


---

## 13. PR.txt 합본 Listing 분석 기준

2026-09-29에 `research/Ghidra_Listing_txt/PR.txt`가 추가되었다. 이 파일은 여러 Ghidra Listing txt를 하나로 합친 합본이며 `### FILE:` 구분자를 기준으로 원본 파일 단위로 분석한다.

예: `### FILE: 00dd5b48_ProtocolGame_HttpRequest__V4_POST_Login.txt` → `ProtocolGame_HttpRequest$$V4_POST_Login @ 00dd5b48`

따라서 이후에는 PR.txt 전체를 다시 분리해 업로드할 필요 없이 `### FILE:` 블록을 함수 단위 Listing으로 취급한다.

## 14. V4_POST_Login 정적 분석 확정

`ProtocolGame_HttpRequest$$V4_POST_Login @ 00dd5b48`에서 다음 호출 관계가 확인되었다.

`V4_POST_Login → ServerConst.GetURL → GetDefaultParams → 로그인 Dictionary 구성 → Sign → HttpRequestManager.PostRequest`

핵심 Listing은 `00dd5c64 bl 0x016dbad8`(GetURL), `00dd5c6c bl 0x00ddbf58`(GetDefaultParams), `00dd5d40 bl 0x00dd95c0`(Sign), `00dd5d8c b 0x01695d9c`(PostRequest)이다.

즉 로그인 함수에서 URL과 기본 파라미터를 준비하고, Sign으로 `sign`을 만든 뒤 PostRequest로 HTTP 전송을 시작한다.

## 15. GetDefaultParams 정적 분석

`ProtocolGame_HttpRequest$$GetDefaultParams @ 00ddbf58`에서 Dictionary 생성 및 다음 helper 호출이 확인되었다.

- `DateTime.get_Now` / `DateTime.get_Ticks` / `Int64.ToString`
- `Ali.get_deviceUniqueIdentifier @ 00e0a148`
- `Ali.get_advertisingIdentifier @ 00e0a494`
- `ProtocolGame_HttpRequest.get_retailID @ 00dd949c`
- `ProtocolGame_HttpRequest.get_buildVerion @ 00dd90bc`
- `AppConst.get_Mark @ 016dacf8`
- `ProtocolGame_HttpRequest.get_Token @ 00dd9534`
- `Dictionary.set_Item`

현재 런타임에서 확보한 `n`, `d`, `r`, `v`, `m`, `t` 등의 값이 이 함수 또는 해당 helper 경로에서 생성된다. 각 값의 정확한 생성 원인은 helper Listing까지 내려가 최종 확정한다.

## 16. Sign 정적 분석 확정

`ProtocolGame_HttpRequest$$Sign @ 00dd95c0`에서 `Dictionary.get_Keys → Enumerable.OrderBy → Dictionary.get_Item → List → String.Join → MD5HashString → Dictionary.set_Item` 흐름이 확인되었다.

핵심 주소는 `00dd97a8`의 Keys, `00dd9848`의 OrderBy, `00dd99a4`의 Dictionary.get_Item, `00dd9b4c`의 String.Join, `00dd9b54`의 MD5HashString, `00dd9b68`의 Dictionary.set_Item이다.

따라서 Sign은 다음으로 확정된다.

`Dictionary.Keys → key 정렬 → 각 key의 value 추출 → content 추가 → String.Join(".") → MD5HashString → dict["sign"]`

key 이름 자체를 MD5 입력에 넣는 것이 아니라 정렬된 key의 value들을 사용한다. 빈 문자열 value도 유지되므로 해당 위치의 구분자 `.`가 보존된다.

## 17. 현재 완성된 로그인 네트워크 경로

`V4_POST_Login → GetDefaultParams → Dictionary 구성 → Sign → PostRequest → AddRangeData → WWWForm.AddField → RequestCoroutine → UnityWebRequest.Post → UploadHandlerRaw`

이 경로는 Ghidra Listing과 ARM64 실기기 runtime hook 양쪽에서 확인되었다.

실기기 runtime에서 실제 요청은 `POST https://ac.aliother.com/v5/account/login?778927`, `Content-Type: application/x-www-form-urlencoded`, body 551 bytes로 확인되었다.

## 18. HttpRequest 정적 분석과의 연결

- `AddData`: `HttpRequest + 0x50`의 WWWForm에 `WWWForm.AddField(key,value)` 호출
- `AddRangeData`: Dictionary를 순회하면서 각 key/value를 WWWForm에 추가
- `PostRequest`: `CreateHttpRequest → AddRangeData → Queue.Enqueue`
- `CreateHttpRequest`: `HttpRequest.ctor → AddHeader → AddHeader`
- `Request`: `RequestCoroutine → UnityWebRequest.Post(url, WWWForm)`

따라서 Dictionary가 form data로 변환되어 UnityWebRequest POST body가 되는 전체 경로가 연결되었다.

Unity WWWForm 자체의 내부 encoding 구현을 게임 Listing만으로 모두 복원한 것은 아니다. 다만 runtime의 UploadHandlerRaw에서 실제 551-byte `application/x-www-form-urlencoded` body가 확인되어 최종 serialization 결과는 검증되었다.

## 19. 현재 검증 상태

| 단계 | 정적 분석 | Runtime | 상태 |
|---|---|---|---|
| V4_POST_Login | 확인 | 확인 | 확정 |
| GetDefaultParams | 확인 | 실제 값 확인 | 확정 |
| Sign | 확인 | MD5 결과 일치 | 확정 |
| PostRequest | 확인 | HTTP 생성 확인 | 확정 |
| AddRangeData | 확인 | body 결과와 연결 | 확정 |
| WWWForm.AddField | 확인 | form-urlencoded body 확인 | 확정 |
| UnityWebRequest.Post | 확인 | POST 확인 | 확정 |
| UploadHandlerRaw | 경로 확인 | 551 bytes 확인 | 확정 |
| PCAP byte-level 대응 | 진행 예정 | runtime 확보 | 다음 단계 |

## 20. 다음 분석 우선순위

Sign 자체는 현재 추가 분석 우선순위가 낮다. 다음은 GetDefaultParams 내부 helper를 추적하여 실제 값 생성 원인을 확정하는 것이다.

1. `get_Token @ 00dd9534`
2. `get_buildVerion @ 00dd90bc`
3. `get_retailID @ 00dd949c`
4. `Ali.get_advertisingIdentifier @ 00e0a494`
5. `Ali.get_deviceUniqueIdentifier @ 00e0a148`
6. `AppConst.get_Mark @ 016dacf8`

특히 긴 `t` 값의 생성 경로를 우선 추적한다. 이후 로그인 request를 PCAP과 byte 수준으로 대조하고 response 처리까지 연결한다.

## 21. 분석 환경 기준

이번 분석도 **ARM64 실기기 + hook-patched APK**를 기준으로 한다. LDPlayer/x86 에뮬레이터를 현재 hook 실행 환경으로 사용하지 않는다.

정적 원본은 `research/Ghidra_Listing_txt`이며, 합본 `PR.txt`는 `### FILE:` 단위로 함수별 Listing을 찾아 AL/AD/CR/RE 등의 개별 Listing과 동일한 방식으로 분석한다.


## 22. Ghidra Listing 합본 파일명 규칙 확정

2026-09-29 기준으로 `research/Ghidra_Listing_txt`의 Listing 합본 파일은 **실제 클래스/함수명의 시작 문자열 2글자**를 기준으로 분류한다.

예:

```text
ProtocolGame_HttpRequest...
    → PR.txt

Ali...
    → AL.txt

AppConst...
    → AP.txt
```

또한 Ghidra에서 실제 함수명에 `$$`, `<`, `>` 등 파일명에 사용할 수 없는 문자가 포함될 수 있으므로, **파일명에서는 해당 문자를 `_`로 치환한다.**

예:

```text
실제 함수명:
ProtocolGame_HttpRequest$$get_Token

Listing 파일명:
00dd9534_ProtocolGame_HttpRequest__get_Token.txt
```

여기서 `$$`가 파일명에서는 `__`로 변환된다.

따라서 합본 파일에서 함수를 찾을 때는 다음 순서를 사용한다.

1. 실제 클래스/함수명의 앞 2글자로 합본 파일을 결정한다.
2. 해당 합본 TXT의 `### FILE:` 구분자를 검색한다.
3. `### FILE:` 뒤의 치환된 파일명으로 원본 Listing 블록을 확인한다.
4. 블록 내부의 함수 시작 주소와 Listing을 확인한다.

**중요:** 특정 주소가 일반 GitHub 검색에서 검색되지 않는다는 이유만으로 함수가 없다고 판단하지 않는다. 합본 TXT 내부의 `### FILE:` 블록을 확인한 뒤 존재 여부를 판단한다.

## 23. GetDefaultParams helper 주소와 검색 위치

현재 `GetDefaultParams @ 00ddbf58`에서 확인된 helper는 다음과 같다.

| 주소 | 실제 함수명 | 검색 대상 |
|---|---|---|
| `00dd9534` | `ProtocolGame_HttpRequest$$get_Token` | `PR.txt` |
| `00dd90bc` | `ProtocolGame_HttpRequest$$get_buildVerion` | `PR.txt` |
| `00dd949c` | `ProtocolGame_HttpRequest$$get_retailID` | `PR.txt` |
| `016dacf8` | `AppConst$$get_Mark` | `AP.txt` |
| `00e0a494` | `Ali$$get_advertisingIdentifier` | `AL.txt` |
| `00e0a148` | `Ali$$get_deviceUniqueIdentifier` | `AL.txt` |

이전 분석에서 일부 주소를 개별 검색 결과만으로 '함수 자체가 없다'고 판단했던 내용은 폐기한다. 합본 파일 구조를 고려하면 **해당 2글자 TXT의 `### FILE:` 블록을 기준으로 존재 여부를 확인해야 한다.**

## 24. GetDefaultParams 값 추적 목표

현재 runtime에서 확인된 기본 파라미터는 다음과 같다.

```text
n=639262781542097130
d=cbcfdf10d56e57a89f7cb19a491d139e
r=7
v=3.1.0
m=official
t=jLDohEUPbopnwARSF4L/ERqOUc1bvMSJCWDvIQqHkF0Qjn/S2xt/5CAoaxoYsTQ0oEeS7l1xEy8U2TNzM+r9wJ8qGD8B/3ItbtOa7IDcauHiZnHoKIUnDAQQGbUdLia3D1BNXW70lzjbVmA/0+RuQUpa1n6Gj881gOEgtovFxkbYptUVUEByYWgkhJcuqW/Vv25Pm95ikRUXVXKlAGJq9G5Demi43jfStGJBdE3F692g3JaBkfGRoDgH/92BIT7s/I/9Tt7jDH6p0uJdHr9GEVVwMlfnlL+WhfthrijayY6GyziOg6Qhn7NjK1NkHYxoOE125o5gV9e1Dr4qsgC60Q==
```

정적 분석상 `GetDefaultParams`는 `DateTime.Now → Ticks → ToString`, deviceUniqueIdentifier, advertisingIdentifier, retailID, buildVersion, AppConst.Mark, Token 등의 helper를 호출한다.

다음 분석에서는 단순히 함수 존재 여부를 확인하는 것이 아니라 **각 helper의 반환값이 GetDefaultParams의 어떤 값으로 연결되는지**를 확정한다.

특히 `t`는 매우 긴 Base64 문자열이므로 단순한 일반적인 광고 ID 문자열로 단정하지 않는다. `get_Token` 및 `get_advertisingIdentifier`의 실제 Listing과 반환 데이터 흐름을 확인한 후 의미를 확정한다.

## 25. 새 분석 세션 시작 기준

새 창에서 작업을 이어갈 때는 이 문서를 기준 문서로 사용한다.

현재 확정된 범위:

```text
V4_POST_Login
    ↓
GetDefaultParams
    ↓
Dictionary 구성
    ↓
Sign
    ↓
HttpRequestManager.PostRequest
    ↓
HttpRequestManager.CreateHttpRequest
    ↓
HttpRequest.AddRangeData
    ↓
WWWForm.AddField
    ↓
HttpRequest.RequestCoroutine
    ↓
UnityWebRequest.Post
    ↓
UploadHandlerRaw
    ↓
실제 POST body
```

다음 정적 분석의 1차 목표:

```text
PR.txt
 ├─ get_Token @ 00dd9534
 ├─ get_buildVerion @ 00dd90bc
 └─ get_retailID @ 00dd949c

AL.txt
 ├─ get_advertisingIdentifier @ 00e0a494
 └─ get_deviceUniqueIdentifier @ 00e0a148

AP.txt
 └─ get_Mark @ 016dacf8
```

이 6개 helper를 확인한 후 `n/d/r/v/m/t`의 생성 원인을 확정하고, 이후 로그인 request의 PCAP byte-level 대응 및 response 처리로 진행한다.

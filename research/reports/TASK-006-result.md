# TASK-006 Result — Login API Contract / Local Server Bootstrap

Status: IN PROGRESS

## 1. Goal

Login flow를 패치로 강제 성공시키기 전에, 원본 Client가 사용하는 로그인 Request/Response 경계와 Main bootstrap 진입 조건을 증거로 정리한다.

현재 결과는 정적 dump와 기존 PCAP의 1차 flow 요약 기반이다. APK/server code 수정은 하지 않았다.

## 2. Environment / Sources

- Git workspace: `C:\Users\USER\Documents\GitHub\arme`
- Tool/data workspace: `C:\Users\USER\Documents\Codex\Arme2`
- Native target: `C:\Users\USER\Documents\Codex\Arme2\libil2cpp.so`
- Static metadata dump: `C:\Users\USER\Documents\Codex\Arme2\Dummy_dll\dump.cs`
- String literal dump: `C:\Users\USER\Documents\Codex\Arme2\Dummy_dll\stringliteral.json`
- PCAP: `C:\Users\USER\Documents\Codex\Arme2\PCAPdroid_11_9월_18_22_06.pcap`

## 3. Confirmed Static Evidence

### 3.1 Server API constants

`ServerConst` defines HTTP/API keys:

| API | Value | Evidence |
|---|---|---|
| All-in-one bootstrap | `API_Allin1` | `ServerConst.API_Allin1` |
| anonymous account | `API_Anon` | `ServerConst.API_account_anon` |
| login | `API_Login` | `ServerConst.API_Login` |
| token param | `token` | `ServerConst.PARAM_TOKEN` |
| device param | `d` | `ServerConst.PARAM_DEVICE` |
| version param | `v` | `ServerConst.PARAM_VERSION` |
| retail param | `r` / `retail` | `ServerConst.PARAM_RETAIL`, `ServerConst.Param_retail` |

RVA evidence:

```text
ServerConst.GetURL         RVA 0x15DBAD8
ServerConst.GetURLByRemote RVA 0x15DBBF4
```

### 3.2 Login manager entry points

`LoginManager` contains the expected high-level login flow methods.

```text
LoginManager.AutoLogin            RVA 0xCD55C8
LoginManager.Login                RVA 0xCD5AAC
LoginManager.RequestLoginToken    RVA 0xCD59D8
LoginManager.OnLoginSucceedAction RVA 0xCD5D94
LoginManager.GuestLogin           RVA 0xCD56B8
LoginManager.GuestLogin_Request   RVA 0xCD5FE4
LoginManager.SaveLoginToken       RVA 0xCD64A0
LoginManager.LoginGameServer      RVA 0xCD6910
LoginManager.HandleLoginSuccess   RVA 0xCD71E0
LoginManager.HandleLoginFailed    RVA 0xCD7254
```

Field evidence:

```text
LoginUserInfo.Uid
LoginUserInfo.UserName
LoginUserInfo.PassWord
LoginUserInfo.Token
LoginUserInfo.isGuest
LoginUserInfo.Logintype
```

### 3.3 HTTP login request builders

`ProtocolGame_HttpRequest` contains HTTP request builders for login/bootstrap.

```text
ProtocolGame_HttpRequest.V4_POST_Login(uid, pwd, type = "") RVA 0xCD5B48
ProtocolGame_HttpRequest.V3_POST_Anon(uniqueId, device)      RVA 0xCD6180
ProtocolGame_HttpRequest.V3_POST_AllInOne(mark)              RVA 0xCDC5D0
ProtocolGame_HttpRequest.GetDefaultParams()                  RVA 0xCDBF58
ProtocolGame_HttpRequest.Sign(signKey, dict)                 RVA 0xCD95C0
ProtocolGame_HttpRequest.get_Token()                         RVA 0xCD9534
ProtocolGame_HttpRequest.get_buildVerion()                   RVA 0xCD90BC
ProtocolGame_HttpRequest.get_assetVerion()                   RVA 0xCDCB18
```

Evidence indicates a signed parameter dictionary is likely used for HTTP API calls. Exact fields and signing algorithm still require decompile/assembly confirmation.

### 3.4 HTTP login response model

`Response_GetLoginToken` is the login-token response model.

```text
Response_GetLoginToken.Status
Response_GetLoginToken.UserId
Response_GetLoginToken.Token
Response_GetLoginToken.Desc
Response_GetLoginToken.First
Response_GetLoginToken.method
Response_GetLoginToken.BindFacebook
Response_GetLoginToken.BindGoogle
Response_GetLoginToken.BindGameCenter
Response_GetLoginToken.RealName
Response_GetLoginToken.FCMStatus
Response_GetLoginToken.logout_ex_time
```

Related guest response:

```text
Response_Account_Anon.RoleId
Response_Account_Anon.UserId
Response_Account_Anon.Token
Response_Account_Anon.Desc
Response_Account_Anon.Retail
Response_Account_Anon.First
Response_Account_Anon.logout_ex_time
```

Base response:

```text
Response_GetBase.Status
Response_GetBase.Desc
```

### 3.5 All-in-one/bootstrap response model

`Response_Allin1` appears to carry API URLs, asset CDN, and game server list.

```text
Response_Allin1.Status
Response_Allin1.NoticeStatus
Response_Allin1.NoticeTime
Response_Allin1.IP
Response_Allin1.IsUpgrade
Response_Allin1.Assets
Response_Allin1.Keys
Response_Allin1.Servers
Response_Allin1.Http_API_URL
Response_Allin1.AssetVersion
Response_Allin1.BestCDN
```

Nested server model:

```text
Response_Allin1.Server.Host
Response_Allin1.Server.Port
```

Default game server constants:

```text
GamePlayerInfomation.DefaultServerIP   = gm.aliother.com
GamePlayerInfomation.DefaultServerPort = 8000
```

### 3.6 Game server protocol

After HTTP login-token/bootstrap, the game appears to use `Alioth.S1.Net` with request/response `OpInfo`.

Important command constants:

```text
Commands.CmdHandshake1 = 1
Commands.CmdHandshake2 = 2
Commands.CmdRequest    = 3
Commands.CmdPush       = 4
Commands.CmdError      = 5
Commands.CmdCompress   = 64
Commands.CmdEncrypt    = 128
```

Operation code:

```text
OperationCode.Login = 2
```

`ProtocolGame_SendRequest.Login()` creates the game-server login request:

```text
ProtocolGame_SendRequest.Login() RVA 0xCDE818
```

`CSBehaviour` sends and receives `OpInfo` through `NetworkCenter`:

```text
CSBehaviour.Connect(ip, port, token, autoLogin = True) RVA 0x15DC350
CSBehaviour.RequestOp(OpInfo)                          RVA 0x15DCAFC
CSBehaviour.SendRequest(Request)                       RVA 0x15DCC68
CSBehaviour.Response(Commands, OpInfo)                 RVA 0x15DCD50
```

`Request` contains:

```text
Request.ID
Request.Req : OpInfo
Request.Res : OpInfo
Request.SetResponse(OpInfo)
Request.IsFinished()
```

`OpInfo` contains state-bearing fields, including:

```text
OpInfo.SerialNumber
OpInfo.OpCode
OpInfo.ReturnCode
OpInfo.Time
OpInfo.User
OpInfo.Heros
OpInfo.Items
OpInfo.Weapons
OpInfo.Equiments
OpInfo.Mails
OpInfo.Chapters
OpInfo.Sections
OpInfo.Teams
OpInfo.Shops
OpInfo.Activities
```

This supports the current Local Server direction: login/main bootstrap likely must provide more than `success=true`; it must populate `OpInfo` state fields used by `DataCenter`.

### 3.7 Runtime bootstrap/TLS evidence

Existing LDPlayer runtime logs establish that the earliest observed failure is before
`API_Login` and before any game-server handshake.

```text
Unity: NET ERROR Code: API_Allin1,responseCode: 0 ,error: SSL CA certificate error
Unity: Curl error 60: Cert verify failed: UNITYTLS_X509VERIFY_FLAG_USER_ERROR1
Unity: Exception: download GameMainfestURL error:SSL CA certificate error
```

The string-literal table contains the all-in-one URL:

```text
https://ac.aliother.com/v3/ain1
```

The saved environment note records that the Windows path presented an
`ac.aliother.com` certificate issued by `Somansa Root CA`, while the emulator did
not trust that issuer. This is evidence of a TLS trust-chain failure on the tested
runtime path; it is not evidence of a game-protocol failure, an `API_Login` failure,
or an application-level encryption failure.

An earlier LDPlayer log also contains `OnInjectionDetectorDetected cause: signatures`.
Its causal relation to packet-capture software or the connection failure is UNKNOWN:
the preserved logs do not contain a controlled comparison with and without the
capture application.

### 3.8 Clean bridge-mode runtime baseline (2026-09-28)

Codex connected to the updated LDPlayer instance at `10.131.47.242:5555` and
started `com.Alioth.JusticeSchool.cn` without launching or configuring any
packet-capture or proxy tool in this run. The installed package reported
`versionName=3.1.0`, `versionCode=70`, and `primaryCpuAbi=arm64-v8a`.

The process remained alive, but its relevant Unity log sequence was:

```text
GameUpdateEnable : True
OnInjectionDetectorDetected cause: signatures
GlobalUIManager:OnInjectionDetectorDetected(String)
```

The detector event occurred approximately 16 ms after `GameUpdateEnable`. No
`API_Allin1`, `API_Login`, `TCPTube`, TLS, or connection-error log appeared in
the following approximately 35 seconds of the filtered Unity log.

This confirms that the `signatures` detector event can occur in the baseline
run without a capture tool being launched by Codex. It does not identify the
detected signature, prove that capture software is irrelevant in every setup,
or justify a bypass. The current runtime evidence is insufficient to observe
the bootstrap request at all before a user login action.

### 3.9 Login-action runtime evidence (2026-09-28)

After the user pressed the login button, Unity emitted a call stack in which an
HTTP request completion callback immediately entered game-server connection
setup:

```text
AliothEngine.AndroidUtils:GetSignatureMD5Hash()
Alioth.S1.Net.NetworkCenter:.ctor(String, Int32, String)
CSBehaviour:Connect(String, Int32, String, Boolean)
Ali:DoHttpCallBack(HttpRequest)
AliothEngine.Net.HttpRequestManager:OnFinished(HttpRequest)
AliothEngine.Net.<RequestCoroutine>d__24:MoveNext()
```

The process socket table then contained a TCP connection attempt to
`4F3E5CB6:1F40`, which decodes to `182.92.62.79:8000`. Its state was `02`
(`SYN_SENT`) at observation time. This matches both the existing PCAP game
server candidate and the static default `gm.aliother.com:8000` port.

Therefore the `signatures` detector event did not prevent this observed login
action from reaching `CSBehaviour.Connect`. The current unresolved boundary is
the TCP connection/handshake to port `8000`, not the UI login tap or the
immediate HTTP completion callback. The exact completed HTTP API and its
response fields remain UNKNOWN because the Unity log does not name them here.

## 4. PCAP 1차 Evidence

PCAP summary:

```text
file: PCAPdroid_11_9월_18_22_06.pcap
linktype: 101
packets: 374
observed IP hosts: 5
observed flows: 32
```

DNS/SNI evidence:

```text
DNS query: ac.aliother.com
DNS query: oss01.aliother.com
SNI: check.unity.cn        -> 101.33.100.149:443
SNI: ac.aliother.com       -> 182.92.62.79:443
SNI: oss01.aliother.com    -> 155.102.23.23:443
```

Game-server traffic candidate:

```text
10.215.173.1 -> 182.92.62.79:8000 TCP
10.215.173.1 -> 182.92.62.79:8000 UDP
182.92.62.79 -> 10.215.173.1 UDP/TCP response traffic
```

Correlation:

```text
Static default server: gm.aliother.com:8000
PCAP observed server candidate: 182.92.62.79:8000
HTTP/API SNI candidate: ac.aliother.com:443
Asset/CDN SNI candidate: oss01.aliother.com:443
```

Plain HTTP strings such as `API_Login` / `API_Allin1` were not visible in raw TCP payloads. This supports TLS for `ac.aliother.com:443` HTTP API traffic, but does not prove the full application protocol.

The PCAP is therefore useful for host/port/flow correlation, but cannot establish
the HTTP request body or signing contract while TLS remains opaque.

## 5. Current Contract Draft

| Item | Result |
|---|---|
| API/Command | HTTP `API_Login` / game-server `OperationCode.Login = 2` |
| Endpoint | HTTP: `ac.aliother.com:443` PROBABLE / Game: `*:8000` PROBABLE |
| Request Type | HTTP: `HttpRequest`; game: `Request` wrapping `OpInfo` |
| Required Request Fields | HTTP: `uid`, `pwd`, `type`, default params, signed fields PROBABLE |
| Response Type | HTTP: `Response_GetLoginToken`; game: `OpInfo` |
| Required Response Fields | `Status`, `UserId`, `Token`, `First`, `logout_ex_time`; game state fields UNKNOWN |
| Result Code | HTTP `Status`; game `OpInfo.ReturnCode` |
| Client Handler | `LoginManager.OnLoginSucceedAction`, `LoginManager.LoginGameServer`, `CSBehaviour.Response`, `DataCenter.ProccessRequestRes` |
| State Effect | Login token saved; game-server login response likely populates `DataCenter.User` and initial dictionaries |
| Persistence Effect | `GamePlayerInfomation.LoginToken`, saved login info PROBABLE; SQLite/local persistence not implemented |
| Next API | Main bootstrap state requests via `OperationCode.GetHeros/GetItems/GetChapters/...` UNKNOWN order |

## 6. Inferred Login Flow

This is an inference from static names and PCAP correlation, not yet fully decompiled.

```text
Login UI / AutoLogin
 → LoginManager.RequestLoginToken
 → ProtocolGame_HttpRequest.V4_POST_Login or V3_POST_Anon
 → HTTPS API endpoint from All-in-one/ServerConst
 → Response_GetLoginToken
 → LoginManager.SaveLoginToken
 → LoginManager.LoginGameServer(logout_ex_time)
 → CSBehaviour.Connect(server host, port 8000, token)
 → TCPTube handshake
 → ProtocolGame_SendRequest.Login()
 → CSBehaviour.RequestOp(OpInfo Login)
 → CSBehaviour.Response(...)
 → DataCenter.ProccessRequestRes(OpInfo)
 → Main/bootstrap state
```

## 7. Unknown / Needs More Evidence

- Exact HTTP URL path for `API_Login`.
- Exact parameter dictionary generated by `V4_POST_Login`.
- `Sign(signKey, dict)` algorithm and key source.
- Whether `Response_GetLoginToken` is JSON via `JsonMapper`/LitJson or another path.
- Exact `ProtocolGame_SendRequest.Login()` OpInfo fields.
- `TCPTube` handshake packet structure.
- Meaning of `Commands.CmdEncrypt` and relation to `Crypto.EncryptUnSafe/DecryptUnSafe`.
- Initial game-server login response fields required for Main.
- Whether port `8000` uses TCP only, UDP only, or both in normal runtime.
- Whether a clean, trusted bridge-mode run reaches `API_Login` after `API_Allin1`.
- Whether the packet-capture application changes the result independently of the
  existing TLS trust-chain condition.
- What condition raises `OnInjectionDetectorDetected cause: signatures` before
  the bootstrap request, and whether it prevents the request from being issued.
- Why the observed game-server TCP attempt remains `SYN_SENT`, and whether the
  failure is routing, endpoint reachability, or a later socket-state transition.

## 8. GPT 판단 대기 후보

Ready for a narrow GPT decision: the runtime has now shown the post-login
transition from an HTTP completion callback to `CSBehaviour.Connect`, followed
by a TCP attempt to the documented port `8000`. Codex should next collect at
least one of:

1. Ghidra/decompile evidence for `ProtocolGame_HttpRequest.V4_POST_Login`.
2. Ghidra/decompile evidence for `ProtocolGame_SendRequest.Login`.
3. A controlled runtime/log comparison of the port `8000` TCP state with capture
   disabled versus enabled, on the same bridge/network path.

Once those are collected, GPT should decide:

- whether TASK-006 continues into deeper `TCPTube` protocol analysis,
- or whether a separate TASK should implement a minimal local `API_Allin1`/`API_Login` HTTPS-compatible endpoint,
- or whether the next task should focus on game-server `OperationCode.Login` handshake/response.

## 9. Current Codex Recommendation

Continue investigation. Do not implement or patch yet.

Next Codex step:

```text
Decompile / disassemble:
1. ProtocolGame_HttpRequest.V4_POST_Login
2. ProtocolGame_HttpRequest.Sign
3. ProtocolGame_SendRequest.Login
4. TCPTube handshake/send/receive
5. DataCenter.ProccessRequestRes
```

Then update this report with concrete caller/callee and field assignments. Before
any packet-capture retry, record the port `8000` TCP state in a clean baseline;
otherwise a capture-related conclusion would not be attributable.

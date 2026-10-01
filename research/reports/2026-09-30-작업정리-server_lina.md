# 2026-09-30 작업 정리 — server_lina 프로젝트

## 1. Git 저장소 설정

### 1.1 server_lina 레포 클론
- **저장소**: `g9inlife-blip/server_lina` (JusticeSchool 오프라인 로컬 서버 전용)
- **문제**: `git clone`/`git fetch`가 프록시에서 멈춤
- **해결**: GitHub API로 파일 직접 다운로드
- **원격 init 커밋**: `9de83987` (Ghidra/PCAP/분석문서 포함)

### 1.2 LFS 문제 해결
- **증상**: `git push` 시 `Git LFS upload failed`, `GH008` 에러
- **원인**: `참고용-another_app/.gitattributes`의 LFS 추적 규칙 + 히스토리에 없는 LFS 오브젝트 참조
- **해결**:
  1. `git filter-branch`로 히스토리에서 LFS 파일 제거 (2개 경로)
  2. `.gitattributes` 삭제
  3. `git push --force origin main`
- **교훈**: 대용량 바이너리는 LFS 없이 관리, 필요시 별도 처리

### 1.3 API 직접 push 환경 구축
- **파일**: `~/workspace/gh_push.py`
- **이유**: git 프로토콜이 프록시에서 불안정
- **사용법**: `python3 ~/workspace/gh_push.py "커밋 메시지"`
- **동작**: GitHub API로 blob → tree → commit → ref 업데이트

## 2. 서버 뼈대 구축

### 2.1 FastAPI 구조
```
server_lina/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 엔트리포인트
│   ├── config.py        # 서버 설정 (HOST, PORT, 버전)
│   ├── crypto.py        # Sign 알고리즘
│   ├── models.py        # 요청/응답 모델
│   └── routes/
│       ├── __init__.py
│       ├── login.py     # V4 로그인 + V3 AllInOne
│       ├── allin1.py    # (login.py에 통합)
│       └── anon.py      # 게스트 (TODO)
├── requirements.txt
├── .gitignore
└── README.md
```

### 2.2 Sign 알고리즘 (2026-09-29 확정)
```python
def compute_sign(content: str, params: dict[str, str]) -> str:
    keys = sorted(params.keys())           # 문자열 오름차순
    values = [params[k] for k in keys]
    values.append(content)                # content는 마지막
    joined = ".".join(values)             # 구분자 "."
    return hashlib.md5(joined.encode()).hexdigest()
```
- **검증**: 2026-09-29 Frida 캡처 데이터로 Python 재현 검증 통과
- **검증**: 2026-09-30 실제 로그인 캡처 데이터로 검증 통과

## 3. Frida 후킹

### 3.1 justice_hook.js v4.8
- **위치**: `research/frida/justice_hook.js`
- **후킹 대상** (18개):
  - `ProtocolGame_HttpRequest.V4_POST_Login` — 로그인 파라미터
  - `ProtocolGame_HttpRequest.Sign` — content, dict (BEFORE/AFTER)
  - `ProtocolGame_HttpRequest.GetDefaultParams` — 기본 파라미터
  - `ProtocolGame_HttpRequest.get_Token` — 토큰 추적
  - `LoginManager.SaveLoginToken` — 토큰 저장
  - `UnityWebRequest` — URL, 메서드, 헤더, 바디
  - `DownloadHandler.get_text` — **HTTP 응답 바디** (v4.8 신규)
  - `UnityWebRequest.get_responseCode` — **HTTP 상태 코드** (v4.8 신규)
  - `ServerConst.GetURL` — **서버 URL** (v4.8 신규, 리다이렉트용)
  - `String.Join` / `MD5HashString` — Sign 내부
  - `System.Convert.ToBase64String` — t 생성 추적

### 3.2 폴더 구조
```
research/
├── frida/
│   ├── justice_hook.js
│   └── README.md
├── captures/
│   └── http/           # HTTP 캡처 로그
├── reports/            # 분석 보고서
└── PCAP/               # 패킷 캡처
```

## 4. HTTP 로그인 캡처 (2026-09-30)

### 4.1 API 목록 (AllInOne 응답)
| Key | URL |
|-----|-----|
| API_Login | https://ac.aliother.com/v5/account/login |
| API_Anon | https://ac.aliother.com/v3/account/anon |
| API_Allin1 | https://ac.aliother.com/v3/ain1 |

- 게임 서버: `ac.aliother.com:8000` (KCP/TCP)
- CDN: `https://oss01.aliother.com/v310/202608022111/`

### 4.2 로그인 요청
- URL: `POST https://ac.aliother.com/v5/account/login?{랜덤숫자}`
- Content-Type: `application/x-www-form-urlencoded`
- 바디: `n=...&d=...&r=7&v=3.1.0&m=official&t=...&u=...&p=...&method=&platform=google&p2=logout&sign=...`

### 4.3 로그인 응답
```json
{
  "Status": 0,
  "Desc": "成功",
  "UserId": 861197,
  "Token": "<새 토큰>",
  "t": "<요청과 동일>",
  "sign": "<서버 계산 sign>"
}
```
- **중요**: 응답에 새 Token이 옴 (요청의 t와 다름)
- `SaveLoginToken(UserId, Token, 0, false, 0x0)`으로 저장

### 4.4 문서
- `research/captures/http/2026-09-30-login-capture.md`

## 5. 확정된 파라미터

| 키 | 의미 | 예시 | 상태 |
|----|------|------|------|
| n | DateTime.Now.Ticks | 639263747531220840 | 확정 |
| d | deviceUniqueIdentifier | cbcfdf10d56e57a89f7cb19a491d139e | 확정 |
| r | retailID | 7 | 확정 |
| v | buildVersion | 3.1.0 | 확정 |
| m | mark | official | 확정 |
| t | get_Token() | base64 344자 | 확정 |
| u | 계정 ID | witchwind2 | 확정 |
| p | 비밀번호 | witchwind2 | 확정 |
| method | (빈 문자열) | "" | 확정 |
| platform | 플랫폼 | google | 확정 |
| p2 | | logout | 확정 |
| sign | MD5 서명 | 8fdb81dda6d1aab1970e967f0e2dd57e | 확정 |
| content | 고정 MD5 | 90f04cb7a1fa5c2f58ca19cde2a2b128 | 확정 |

## 6. 다음 할 일

### Phase 1 — HTTP 로그인 완성
- [x] Sign 검증
- [x] HTTP 요청/응답 캡처
- [x] 로그인 응답 mock 구현
- [x] 서버 로컬 테스트 (sign 검증 버그 수정: `keep_blank_values=True`)
- [x] 실제 클라이언트로 로컬 서버 테스트 성공 (2026-09-30)

### Phase 2 — URL 리다이렉트
- [x] `ServerConst.GetURL` 후킹 코드 추가 (v4.9)
- [x] Frida로 URL 리다이렉트 테스트 성공
- [x] **로컬 서버로 로그인 성공** (2026-09-30)
  - `API_Allin1` → 로컬 서버 (0xc8)
  - `API_Login` → 로컬 서버 (0xc8)
  - `SaveLoginToken` 호출 확인 (더미 토큰 저장)
- [x] CDN 로컬 서빙 추가 (2026-09-30)
  - `app/routes/cdn.py` — 에셋번들 서빙
  - AllInOne 응답에 로컬 CDN URL 포함
  - `app/update_data/` — 업데이트 파일 235MB
- [ ] 게임 서버 (KCP) 연결 테스트

### Phase 3 — KCP 게임 서버
- [x] KCP 서버 뼈대 구현 (2026-09-30)
  - `app/kcp/dh64.py` — DH64 키교환 (P=2^64-59, secret 계산, 16바이트 키 생성)
  - `app/kcp/crypto.py` — AES-128-CBC 암복호화 (테스트 통과)
  - `app/kcp/server.py` — 포트 8000 서버 스켈레톤
  - `requirements.txt`에 pycryptodome 추가
- [ ] DH 핸드셰이크 패킷 구조 확정 (GPT 분석 대기)
- [ ] IV 결정 방식 확인
- [ ] Opcode별 req/rsp 구현

### Phase 4 — 게임 로직
- [ ] 던전/전투/가챠/상점 순서대로

## 7. 서버 테스트 결과 (2026-09-30)

### 테스트 환경
- Python venv (`/tmp/server_test`)
- FastAPI TestClient

### 테스트 항목
- [x] `GET /health` → 200 OK
- [x] `POST /api/v5/account/login` → sign 검증 통과, 로그인 응답 반환
- [x] 실제 캡처 데이터로 검증 (sign: `8fdb81dda6d1aab1970e967f0e2dd57e` 일치)

### 발견된 버그
- **문제**: `urllib.parse.parse_qsl`이 빈 값을 버림
- **영향**: `method=""`가 사라져서 sign 검증 실패
- **수정**: `parse_qsl(..., keep_blank_values=True)`
- **파일**: `app/routes/login.py`

## 8. URL 리다이렉트 현황 (2026-09-30)

### 리다이렉트 중 (로컬 서버)
| 키 | 로컬 경로 |
|----|----------|
| API_Login | `http://127.0.0.1:8888/api/v5/account/login` |
| API_Anon | `http://127.0.0.1:8888/api/v3/account/anon` |
| API_Allin1 | `http://127.0.0.1:8888/api/v3/ain1` |

### 실제 서버 유지
- `NoticeURL` → `https://ac.aliother.com/v3/notice`
- 결제 관련 (`API_Pay`, `API_ApplePayVerify` 등) → 실제 서버
- 이유: 게임 플레이에 불필요, 나중에 목업 예정

### CDN
- **방식**: AllInOne 응답의 `Assets[0].CDN`을 로컬로 변경
- **로컬 경로**: `http://127.0.0.1:8888/cdn/v310/202608022111/`
- **서빙 파일**: `app/update_data/` (235MB, 업데이트분)
- **참고**: APK 기본 1.4GB는 설치 시 포함, 업데이트분만 서빙

### Frida 후킹 (v4.10)
- `ServerConst.GetURL(1 arg)` 후킹
- `il2cpp_string_new`로 새 URL 문자열 생성
- `retval.replace()`로 반환값 교체
- `URL_MAP`에서 매핑된 키만 리다이렉트
- **v4.10 신규**: 게임 서버 연결 후킹
  - `CSBehaviour.Connect` — 게임 서버 연결 시도 로깅 (1-4 args 자동 탐색)
  - `CSBehaviour.RequestOp` — opcode 전송 로깅
  - `NetworkCenter.Send` — raw 전송 로깅 (1-3 args 자동 탐색)
- **v4.10.2**: LoginGameServer/HandleLoginSuccess 후킹 추가
  - `LoginManager.LoginGameServer` — 게임 서버 로그인 시작점 추적
  - `LoginManager.HandleLoginSuccess` — 로그인 성공 핸들러 추적

## 9. 게임 서버 연결 추적 (2026-09-30)

### Frida 후킹 현황 (v4.10.2)
| 후크 | 상태 |
|------|------|
| `CSBehaviour.Connect` (1 args) | ✅ 후킹 성공 |
| `CSBehaviour.RequestOp` | ✅ 후킹 성공 |
| `NetworkCenter.Send` | ❌ 못 찾음 |
| `LoginManager.LoginGameServer` | ✅ 후킹 성공 |
| `LoginManager.HandleLoginSuccess` | 후킹 시도 중 |

### KCP 핸드셰이크 진행 상황 (2026-10-01)
- ✅ 클라이언트 연결 수신
- ✅ Handshake2 패킷 파싱 (56 bytes, public 키 추출)
- ✅ 세션 키 계산 (DH64)
- ✅ 서버 Handshake 응답 전송 구현 (g=5)
- ⏳ 클라이언트 응답 대기 중

### 확인된 흐름
```
HTTP 로그인 성공
  → SaveLoginToken (UserId: 861197)
  → LoginManager.LoginGameServer 호출됨 ✅
  → KCP 연결 시도 ✅
  → Handshake2 교환 ✅
  → (다음: 암호화 통신)
```

### 현재 상태
- 게임이 로딩 화면에서 멈춤
- KCP 핸드셰이크는 진행 중, 응답 후 다음 단계 확인 필요

## 10. 참고 자료

- Sign 알고리즘: `research/reports/2026-09-29-Sign-알고리즘-런타임-검증.md`
- GetDefaultParams: `research/reports/2026-09-29-GetDefaultParams-helper-정적분석.md`
- 인게임 네트워크: `research/reports/2026-09-29-인게임-네트워크-경로-분석.md`
- KCP/DH64: `research/reports/2026-09-30-KCP-DH64-Key-Recovery-PCAP-복호화.md`
- 아키텍처: `research/ARCHITECTURE_DIRECTION.md`
- KBC 참고: `참고용-another_app/` (구조 참고용, 게임 데이터 복사 금지)

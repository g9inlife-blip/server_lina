# server_lina — JusticeSchool 오프라인 로컬 서버

`com.Alioth.JusticeSchool.cn`의 로그인 HTTP 통신을 재현하는 오프라인 로컬 서버.

## 목적

실서버 없이 게임 클라이언트의 로그인 플로우를 로컬에서 처리.
Frida로 역분석한 `Sign` 알고리즘을 서버 측에서 검증/재현.

## 확정된 Sign 알고리즘 (2026-09-29)

```python
keys = sorted(dict.keys())                    # 문자열 오름차순
joined = ".".join([dict[k] for k in keys] + [content])
sign = md5(joined)
dict["sign"] = sign
```

- 구분자: `.`
- key는 해시에 포함하지 않음, 정렬된 key의 value만 사용
- `content`는 마지막에 추가
- 빈 문자열도 유지 (`method=""` → `..`)
- 근거: `research/reports/2026-09-29-Sign-알고리즘-런타임-검증.md` (Arme-lina)

## 로그인 플로우

```
GetDefaultParams()
  → {n, d, r, v, m} (+ t for V4)
  → V4_POST_Login: {u, p, method, platform, p2} 추가
  → Sign(content, dict): dict["sign"] 추가
  → HTTP POST → 서버
```

## 구조

```text
server_lina/
├── README.md
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 엔트리포인트
│   ├── config.py        # 서버 설정
│   ├── crypto.py        # Sign 알고리즘 (서명 생성/검증)
│   ├── models.py        # 요청/응답 모델
│   └── routes/
│       ├── __init__.py
│       ├── login.py     # V4 로그인
│       ├── allin1.py    # V3 AllInOne
│       └── anon.py      # 게스트/익명
└── docs/
    └── analysis/        # GPT 분석 자료 (지속 업데이트)
```

## 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## 분석 자료

`docs/analysis/`에 GPT 분석 문서를 계속 추가.
서버 코드는 확정된 분석 결과만 반영한다.

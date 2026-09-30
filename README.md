# Heroes Offline Research

이 저장소는 `com.Alioth.JusticeSchool.cn` Unity/IL2CPP 게임의 **오프라인 전환 역분석 작업용 경량 연구 저장소**다.

gpt가 git에 저장된 데이터자료를 바탕으로 로컬 서버재구축하는것이 목표이다
research 폴더는 gpt가 분석하는 내용이고 업데이트 될수있다

참고용-another_app 폴더는 이미 다른게임에서 로컬서버를 구축한 코드정보이다(참고용)

참고용-unity-behavior-data 폴더는 unity 데이터를 추출 및 가공한 데이터이다
원본 json은 server-lina\참고용-unity-behavior-data\MonoBehaviour

server-lina\research\Ghidra_Listing_txt 폴더는 ghidra 디컴파일 데이터로 함수명2글자끼리 묶어진 txt파일들이다
함수명에 <> $ 등 특수문자는 _로 치환되어있다

---

## 로컬 서버 (app/)

오프라인 로컬 서버 구현. FastAPI 기반.

### 확정된 Sign 알고리즘 (2026-09-29)

```python
keys = sorted(dict.keys())                    # 문자열 오름차순
joined = ".".join([dict[k] for k in keys] + [content])
sign = md5(joined)
dict["sign"] = sign
```

근거: `research/reports/2026-09-29-Sign-알고리즘-런타임-검증.md`

### 구조

```text
app/
├── main.py          # FastAPI 엔트리포인트
├── config.py        # 서버 설정
├── crypto.py        # Sign 알고리즘 (서명 생성/검증)
├── models.py        # 요청/응답 모델
└── routes/
    ├── login.py     # V4 로그인
    ├── allin1.py    # V3 AllInOne
    └── anon.py      # 게스트/익명
```

### 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

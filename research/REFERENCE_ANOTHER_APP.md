# Reference: another_app / King Bug Castle

## 1. 목적

`참고용-another_app/` 폴더에 있는 **King Bug Castle(KBC) Private Server / Reverse Engineering 프로젝트**를 본 프로젝트의 Local Private Server 구축 참고자료로 사용한다.

이 자료는 **게임 자체를 복제하기 위한 데이터 원본이 아니라, 서버를 구축하고 클라이언트와 연결하는 방법·구조·기술을 참고하기 위한 별도 게임 사례**다.

원본 README에 따르면 KBC는 King God Castle의 백엔드 API를 로컬에서 에뮬레이션하고, FastAPI 기반 서버, SQLite 상태 저장, ARM64 클라이언트 적응, 로컬 CDN, 클라이언트 패치 등의 구조를 사용한다. `참고용-another_app/README.md`의 설명을 기준으로 참고한다.

## 2. 참고할 수 있는 것

본 프로젝트에서 필요할 경우 다음 종류의 **방식 / 구조 / 기술 / 구현 패턴**은 참고하거나 재사용할 수 있다.

- Private Server / API Emulation 구조
- Client ↔ Local Server Request/Response 구조
- FastAPI 기반 HTTP API 서버 구조
- API route를 기능/도메인별 모듈로 분리하는 방식
- JSON 기반 정적 규칙/응답 데이터와 DB 기반 플레이어 상태를 분리하는 방식
- SQLite 기반 Player State / Persistence 구조
- Action → Validate → State Mutation → History/Event → Commit → Response 형태의 서버 처리 흐름
- 서버 응답 템플릿/모델과 실제 플레이어 상태를 분리하는 방식
- 로컬 CDN 또는 로컬 Asset/Data 제공 서버 구조
- 클라이언트와 로컬 서버를 연결하기 위한 클라이언트 적응/패치 파이프라인의 구조적 아이디어
- ARM64 패치 자동화 및 빌드 파이프라인 구성 방식
- 서버/클라이언트/데이터/패치 도구를 디렉터리별로 분리하는 프로젝트 구조
- 운영/관리용 Web UI가 필요한 경우의 구조
- API 미매핑 상태를 추적하고 하나씩 contract를 추가하는 개발 workflow

## 3. 절대 그대로 가져오면 안 되는 것

KBC와 현재 대상 게임은 **서로 다른 게임**이다. 따라서 다음 정보는 현재 게임에서 별도 증거가 없으면 사용하지 않는다.

- KBC의 네트워크 주소 / 도메인 / IP / 포트
- KBC의 API endpoint / route 이름
- KBC의 request/response schema
- KBC의 인증/로그인 토큰 및 계정 식별 규칙
- KBC의 암호화/서명/인코딩 키 또는 프로토콜 값
- KBC의 아이템 ID / 아이템 이름 / 캐릭터 ID / 스테이지 ID
- KBC의 재화 종류 / 수량 / 보상 테이블
- KBC의 몬스터 / 캐릭터 / 장비 / 가챠 / 상점 데이터
- KBC의 확률 / RNG 규칙 / pity / duplicate 규칙
- KBC의 게임 밸런스 수치
- KBC의 서버 상태 필드 및 저장 schema를 현재 게임의 실제 schema라고 가정하는 것
- KBC의 인증서 / TLS / certificate pinning 대상 및 패치 offset
- KBC의 anti-cheat 동작이나 특정 native patch를 현재 게임에 그대로 적용하는 것
- KBC 전용 CDN 주소 및 asset 경로
- KBC 전용 바이너리 offset, 함수 주소, 문자열 주소, hook 대상
- KBC 전용 protocol header, magic, version, checksum 등의 값

## 4. 적용 원칙

### A. 구조는 참고하고 데이터는 검증한다

```text
KBC
  └─ 방식/구조/기술 패턴
          ↓ 참고
현재 게임
  └─ 실제 분석으로 API/데이터/프로토콜 확정
          ↓
Local Private Server 구현
```

즉, **"어떻게 만들었는가"는 KBC에서 배울 수 있지만, "무엇을 넣어야 하는가"는 현재 게임의 분석 결과로 결정한다.**

### B. 게임 고유 정보는 현재 게임 증거가 우선

현재 게임에서 확인된 다음 증거를 우선한다.

1. Ghidra XREF / decompile / assembly
2. IL2CPP dump 및 실제 class/method 구조
3. 런타임 Request/Response
4. Decode/Decrypt/Deserialize 결과
5. 실제 Client Handler 및 State Effect
6. 현재 게임의 반복 실행 결과

KBC 자료와 현재 게임의 정보가 충돌하면 **현재 게임의 증거를 사용하고 KBC 값을 폐기한다.**

### C. 코드 재사용 시에도 게임 의존부를 분리한다

KBC 코드를 가져오거나 참고할 경우 다음을 구분한다.

```text
[재사용/참고 가능]
- 서버 프레임워크 구조
- DB 접근 패턴
- route 분리 방식
- transaction 처리 패턴
- logging/test 구조
- build/deployment automation 구조

[현재 게임에서 다시 구현/검증]
- endpoint
- request/response model
- auth
- encryption
- game state
- item/master data
- reward/RNG
- battle/dungeon rules
- shop/gacha rules
- asset/CDN 주소
```

### D. 출처를 기록한다

KBC에서 가져온 구현 아이디어 또는 코드를 사용한 경우 해당 구현/문서에 다음을 명시한다.

- 참고한 KBC 파일 경로
- 참고한 구조/기술
- 현재 게임에 맞게 변경한 부분
- 현재 게임에서 별도로 검증한 근거

이를 통해 나중에 KBC 고유 데이터가 실수로 현재 프로젝트에 섞이는 것을 방지한다.

## 5. 본 프로젝트에서의 위치

`참고용-another_app/`는 **Reference-only 영역**으로 취급한다.

```text
research/
 ├─ START_HERE.md
 ├─ ARCHITECTURE_DIRECTION.md
 ├─ CURRENT_STATE.md
 ├─ ...
 └─ REFERENCE_ANOTHER_APP.md   ← KBC 참고 규칙

참고용-another_app/
 └─ King Bug Castle 자료        ← 참고 원본
```

Codex는 Local Server를 만들 때 이 폴더를 참고할 수 있지만, **현재 게임의 실제 contract를 확인하기 전에 KBC의 endpoint/data/config를 복사하여 구현하지 않는다.**

## 6. 한 줄 기준

> **KBC는 서버를 만드는 교과서로 사용하고, KBC의 게임 데이터는 현재 게임의 데이터로 사용하지 않는다.**

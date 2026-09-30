# TASK-003 — 로그인 → 메인 메뉴 데이터 흐름 및 온라인 의존성 증명

## 목적
업데이트 우회 이후에도 오프라인에서 메인 메뉴 접근이 실패하는 원인을 데이터 흐름 관점에서 증명한다.

이번 TASK의 목적은 패치가 아니다. **온라인 로그인/초기 데이터가 어떤 요청-응답-파싱-상태 저장-메뉴 진입 흐름으로 연결되는지**를 확정하는 것이다.

## 현재 런타임 전제
- 업데이트 우회: 성공(O)
- 온라인: 등록되어 있는 계정정보로 로그인 성공
- 오프라인: 업데이트 우회 후에도 메인 메뉴 접근 실패
- 따라서 업데이트 서버 외에 로그인 이후/메인 메뉴 진입 과정의 네트워크 데이터 의존성이 남아 있는 것으로 본다.

## 핵심 가설
현재까지의 실행 관찰상 다음 형태를 우선 조사한다.

`Login → Network Response → Data Parse/Deserialize → User/Player Data → Manager/Singleton → Main Menu`

또는

`Main Menu Entry → Network Request → Response → Data Update → Main Menu`

어느 쪽인지 증거로 구분한다.

## 조사 순서

### 1. 로그인 성공 경로
- 로그인 성공 callback/handler를 찾는다.
- 성공 응답의 타입/인자를 확인한다.
- response가 JSON/protobuf/custom binary/기타 구조 중 무엇인지 확인한다.
- deserialize/parser 함수와 caller/callee를 추적한다.
- 결과가 들어가는 실제 managed/native 데이터 객체를 특정한다.

### 2. 계정/플레이어 상태 저장 위치
다음 후보를 우선 검색한다.
- UserData
- PlayerData
- AccountData
- GameData
- CharacterData
- InventoryData
- Manager/Service/Singleton
- static instance

각 후보에 대해:
- 생성 위치
- 필드
- setter/update 함수
- getter
- 참조 caller
- UI에서 읽는 경로
를 기록한다.

### 3. 메인 메뉴 진입 경계
- 로그인 성공 직후부터 Main Scene/Main Menu가 실제 표시될 때까지의 호출 흐름을 추적한다.
- 이 사이의 모든 네트워크 요청을 식별한다.
- 요청별 성공 callback과 실패 callback을 구분한다.
- 어떤 요청이 실패하면 메인 메뉴 접근이 중단되는지 특정한다.
- 기존 TASK-001의 scene transition 증거가 있다면 해당 경로와 연결한다.

### 4. 메뉴 초기 데이터
메인 메뉴 표시 전에 필요한 것으로 보이는 데이터들을 분류한다.
예:
- 계정/플레이어 상태
- 재화
- 캐릭터
- 우편/공지
- 퀘스트
- 출석/이벤트
- 상점/특가상품
- 기타 홈 화면 표시 데이터

각 데이터가 서버 응답에서 오는지, 로컬 데이터에서 오는지 확인한다.

### 5. 기존 로컬 저장/캐시 확인
존재 여부를 증명하기 위해 다음을 조사한다.
- PlayerPrefs
- Application.persistentDataPath 관련 호출
- 파일 I/O
- SQLite/DB
- JSON/Binary serialization
- encrypted/local cache
- AssetBundle/Addressables 캐시

**파일이 없다고 가정하지 않는다.** 실제 참조와 read/write 호출을 근거로 존재 여부를 기록한다.

### 6. 서버 authoritative state 여부
가능하면 하나의 상태 예시를 선택하여 다음 흐름을 증명한다.
예: Gold/재화

`Server Response → Client Data Object → UI 표시 → 행동 요청 → Server Result → Client Data Update`

목표는 로컬 표시값과 서버 결과값이 각각 어디에서 결정되는지 확인하는 것이다.

### 7. 오프라인 실패 지점
온라인/오프라인 실행 로그를 비교하여:
- 마지막으로 성공한 상태
- 최초로 달라지는 callback/state
- 예외 또는 실패 callback
- 메인 메뉴 전환이 발생하지 않는 이유
를 가능한 범위에서 특정한다.

## 반드시 결과에 포함할 것
1. 로그인 성공 데이터 흐름도
2. 메인 메뉴 진입 전 네트워크 요청 목록
3. 각 요청의 response parser/callback
4. 데이터가 저장되는 Manager/Data Object
5. 메인 메뉴 UI가 실제로 읽는 데이터 출처
6. 기존 로컬 저장/캐시 존재 여부
7. 오프라인 실패 지점
8. 현재 증거로 판단 가능한 것과 아직 가설인 것의 구분
9. 향후 Local State Bootstrap에 필요한 최소 데이터 후보

## 중요한 제한
- 수정 금지
- 기존 함수의 이름만 보고 역할을 확정하지 않는다.
- 네트워크 함수 발견만으로 원인을 확정하지 않는다.
- 'Save 파일이 없다'고 추정하지 말고 실제 read/write 경로를 확인한다.
- 서버 응답의 전체 의미를 모르는 상태에서 임의의 성공값/더미값을 만들지 않는다.

## 사용자 런타임 확인
Codex는 ADB/logcat/프로세스/네트워크 상태를 직접 확인한다.
사용자에게 ADB 명령을 요청하지 않는다.
화면 확인이 필요한 경우에는 **화면에서 확인할 항목만** 사용자에게 요청하고, 사용자의 자연어 결과를 기록한다.

## 결과 파일
`research/reports/TASK-003-result.md`

## 종료 기준
다음 중 하나를 충족하면 종료한다.

### 성공
`Login/MainMenu Request → Response → Parser → Data Object/Manager → Scene/UI`의 실제 경로와 오프라인 실패 지점을 증거와 함께 특정한다.

### 부분 성공
일부 데이터 흐름만 특정했지만 다음 조사에 필요한 구체적인 함수/주소/XREF가 확보된다.

### 실패
추적이 막힌 경우 조사한 경로, 마지막으로 확인된 함수, 필요한 추가 자료를 결과에 기록한다.

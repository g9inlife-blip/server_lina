# TASK-004 — Unity Asset / AssetBundle 구조 조사 (후순위)

## 상태
**DEFERRED — 오프라인 동작 기반 확보 이후 실행**

## 목적
Unity/IL2CPP 게임의 `libil2cpp.so` 분석만으로 해결하기 어려운 경우를 대비하여, APK 내부 Unity Asset/AssetBundle/SerializedFile에 어떤 게임 데이터와 리소스가 존재하는지 조사한다.

단, **현재 단계에서 즉시 실행하지 않는다.**

현재는 업데이트 우회는 성공했지만 오프라인 로그인 자체가 성립하지 않는 상태이므로, 먼저 네트워크 우회 및 최소 오프라인 동작 경로를 확보한다. 오프라인 동작 기반이 없는 상태에서 AssetBundle 내부의 상세 데이터를 대규모로 분석하는 것은 우선순위가 낮고 조사 비용 대비 효율이 떨어질 수 있다.

## 실행 조건
다음 조건을 만족한 이후에만 실행한다.

### 필수 조건
- 업데이트 온라인 의존성 우회가 유지된다.
- 오프라인 로그인 또는 최소한 로그인 이후의 로컬 bootstrap 경로가 확보된다.
- 메인 메뉴 진입 또는 그에 준하는 오프라인 실행 지점이 확보된다.
- 최소 1개 이상의 기능에서 `Server Response → Local Data/Result` 치환 방향이 실제 실행으로 검증된다.

### 실행 보류 조건
다음 중 하나라도 해당하면 TASK-004를 보류한다.
- 오프라인 로그인조차 해결되지 않았다.
- 현재 실패 원인이 명확한 네트워크 callback/response 의존성에 남아 있다.
- Asset 데이터가 필요한 구체적인 기능 목표가 아직 정해지지 않았다.
- `libil2cpp.so` 및 기존 데이터 모델 분석만으로 다음 오프라인 단계 진행이 가능한 상태다.

## 조사 원칙
1. 필요한 데이터가 확인된 뒤 해당 Asset만 우선 조사한다.
2. 처음부터 모든 AssetBundle을 상세 분석하지 않는다.
3. `libil2cpp.so`에서 확인된 데이터 타입/클래스/필드/리소스 이름을 검색 단서로 사용한다.
4. AssetBundle 분석 결과만으로 데이터 사용처를 확정하지 않는다.
5. 실제 IL2CPP 로딩 함수/XREF 또는 runtime 관찰과 연결하여 증명한다.
6. 수정은 별도 PATCH TASK에서 결정하며 본 TASK에서는 조사만 수행한다.

## 조사 순서

### 1. APK Unity 데이터 인벤토리
- `assets/` 전체 목록화
- `*.unity3d`, `*.bundle`, `*.assets`, `resources.assets` 등 식별
- 파일 크기/경로/이름 기록
- UnityFS/SerializedFile 등 포맷 식별

### 2. 압축/암호화/커스텀 컨테이너 확인
- UnityFS header 여부
- 압축 방식
- AssetBundle manifest/dependency
- 암호화 또는 커스텀 wrapping 여부
- 일반 Unity AssetBundle 도구로 직접 추출 가능한지 여부

### 3. 데이터 후보 탐색
필요성이 확인된 기능에 한해 우선 조사한다.
- Character / Unit
- Item / Equipment
- Stage / Map
- Skill / Buff
- Gacha / Banner / Rate / Weight
- Reward / Drop
- Shop / Product
- Text / Localization
- 기타 ScriptableObject / MonoBehaviour / TextAsset

### 4. IL2CPP와 연결
기존 `libil2cpp.so` 조사 결과에서 확인된:
- AssetBundle 로딩 함수
- Resources/Addressables 관련 호출
- 파일명/asset name 문자열
- Type/ScriptableObject 이름
- Manager/Provider
- 데이터 필드

와 Asset 파일을 연결한다.

### 5. 필요한 경우에만 추출
실제 다음 오프라인 기능 구현에 필요한 Asset만 추출하여:
- 객체 타입
- 필드
- 기본값
- 참조 관계
- 테이블 구조
- ID 관계
를 기록한다.

## 결과에 반드시 포함할 것
1. Unity 데이터 파일 목록 및 포맷 분류
2. 실제 사용 가능하다고 확인된 AssetBundle/SerializedFile
3. 필요한 기능과 연결되는 데이터 후보
4. IL2CPP 코드와 Asset 데이터의 연결 근거
5. 필요한 Asset을 기존 게임 코드가 어떻게 로드하는지
6. 오프라인화에 실제로 필요한 데이터와 단순 리소스를 구분
7. 추가 Asset 분석이 필요한 후속 TASK 후보
8. 아직 추정에 불과한 부분의 명확한 표시

## 수정 금지
이 TASK에서는 AssetBundle/SerializedFile/Unity 데이터의 원본 수정, APK 재패키징, IL2CPP binary patch를 수행하지 않는다.

## 결과 파일
`research/reports/TASK-004-result.md`

## 종료 기준
### 성공
다음 오프라인 기능 구현에 필요한 Unity Asset 데이터와 그 로딩/사용 경로가 증거와 함께 특정된다.

### 부분 성공
일부 Asset 구조와 유효한 분석 단서가 확보되어 후속 기능별 Asset 조사로 진행할 수 있다.

### 실패
포맷/암호화/커스텀 컨테이너 등으로 추적이 막힌 경우 확인된 사실과 필요한 추가 자료를 기록한다.

## 우선순위 원칙
**오프라인 실행 경로 확보 > 네트워크 의존성 제거 > 최소 데이터 bootstrap > 실제 기능 동작 > 필요한 범위의 Unity Asset 상세 분석**

Asset 분석은 목표가 아니라 수단이다. 실제 오프라인 기능 구현에 필요한 시점에 필요한 범위만 조사한다.

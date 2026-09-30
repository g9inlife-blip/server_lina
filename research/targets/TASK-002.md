# TASK-002 — GameUpdateService 온라인 게이트 구조화

## 목적
업데이트 실패를 일으키는 온라인 의존 지점을 패치하기 전에 각각의 역할과 성공/실패 경로를 증명한다.

## 주요 대상
- `Start.d__68.MoveNext` = `0x1682CA0`
- `StartDownLoadAssetBundleMainfest.d__62.MoveNext` = `0x16834D8`
- `StartGetAssetNeedUpdate.d__58.MoveNext` = `0x168369C`
- `CheckAssets.d__75.MoveNext` = `0x1683230`
- `StartAssetCheck.d__49.MoveNext` = `0x1684514`
- `StartGetAssetNeedUpdate.d__58.MoveNext` = `0x168521C`
- `get_isUseRemoteAsset` = `0x167E380`
- `StartVersionCheckUpdate` factory = `0x167F6EC`
- `<StartVersionCheckUpdate>b__57_0` = `0x1680F68`
- `<StartVersionCheckUpdate>b__57_1` = `0x1681158`
- `<StartVersionCheckUpdate>b__57_2` = `0x16812EC`

## 조사 항목
1. `Start.MoveNext` 상태별 전이와 coroutine 생성/대기를 표로 정리한다.
2. manifest 다운로드 coroutine의 URL 생성, request 함수, 성공 callback, 실패 callback을 추적한다.
3. asset-needs coroutine의 URL 생성, request 함수, 성공 callback, 실패 callback을 추적한다.
4. `CheckAssets`와 `StartAssetCheck`가 로컬 캐시/빌드 검사에서 어떤 결정을 하는지 확인한다.
5. `UpdateTypeResult`가 어느 지점에서 설정되는지 찾는다.
6. `OnUpdateSucess`, `OnPackUpdate`, `OnAssetUpdate`, `OnUpdateFailed`가 어떤 함수로 연결되는지 확인한다.
7. `get_isUseRemoteAsset`의 true/false branch가 실제로 어떤 기능을 건너뛰는지 확인한다. false 패치를 제안하지 말고 branch 의미를 증명한다.
8. 공통 HTTP/request 함수 `0x291A9E8`의 호출 규약과 callback 인자를 확인한다.

## 중요한 원칙
목표는 '네트워크 호출이 있다'를 확인하는 것이 아니라, **오프라인 상태에서도 기존 로컬 데이터로 정상 진행하려면 어떤 결과값을 내부적으로 만들어야 하는지** 알아내는 것이다.

## 수정 금지
조사 단계에서는 수정하지 않는다.

## 결과 파일
`research/reports/TASK-002-result.md`

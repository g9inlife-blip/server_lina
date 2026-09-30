# TASK-001 — 실제 Scene 전환 경로 증명

## 목적
기존 게임 시작 경로에서 실제 Unity scene 전환이 어디서 발생하는지 증명한다.

## 배경
과거 조사에서 다음 함수가 entry/scene 전환 후보로 보였지만, 이름이나 호출 형태만으로 Unity `SceneManager.LoadScene`이라고 확정해서는 안 된다.

- `0x01194F50`
- `0x0118E43C`
- `0x01123194`

## 조사 순서
1. 위 세 함수의 decompile을 각각 확보한다.
2. 각 함수의 모든 direct caller를 조사한다.
3. 각 함수의 callee를 중요한 것부터 추적한다.
4. 문자열 XREF를 조사한다. 특히 scene 이름, scene path, Resources/Addressables/AssetBundle 관련 문자열을 찾는다.
5. Unity scene-loading API와 연결되는 call site를 찾는다.
6. 직접 호출이 아니라면 함수 포인터, virtual/interface dispatch, delegate, static table 등을 추적한다.
7. IL2CPP metadata에서 동일 기능에 대응하는 managed method가 있는지 확인한다.
8. 가능하면 최종적으로 다음 중 하나까지 연결한다.
   - Unity scene-loading native implementation
   - `SceneManager.LoadScene*` 계열 wrapper
   - Async scene load wrapper
   - 명백한 게임 자체 scene manager가 최종적으로 Unity API를 호출하는 지점
9. 단순히 함수 이름에 `Load`, `Scene`, `Entry`가 있다는 이유로 확정하지 않는다.

## 반드시 기록할 증거
각 단계마다:
- 주소
- 함수명
- caller → callee 관계
- 핵심 assembly 5~20줄
- Ghidra decompile 핵심 구간
- 관련 문자열
- XREF 방향
- 판단 근거

## 수정 금지
이 TASK에서는 APK/so/metadata를 수정하지 않는다.

## 결과 파일
`research/reports/TASK-001-result.md`

## 종료 기준
실제 scene 전환 호출 지점이 증거와 함께 특정되면 성공이다. 특정하지 못하더라도 조사한 경로와 막힌 지점을 모두 기록한다.

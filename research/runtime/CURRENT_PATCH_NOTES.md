# 현재 패치 버전 참고사항

## 뽑기 메뉴 진입 시 빈 화면

현재 패치 버전에서 다음 현상이 관찰되었다.

```text
네트워크 연결 상태
    ↓
로그인
    ↓
게임 진입 성공
    ↓
뽑기 메뉴 선택
    ↓
빈 화면만 표시
```

이 현상은 현재 오프라인화 패치의 직접적인 증상으로 단정하지 않는다. **현재 패치 버전 자체에서 관찰된 참고사항**으로 기록한다.

### 현재 판단

로그인 및 게임 진입까지는 정상적으로 진행되지만, 뽑기 메뉴 진입 시 별도의 추가 데이터 또는 리소스가 필요한 것으로 의심된다.

특히 뽑기 메뉴가 단순히 네트워크 Response만 받아 화면을 구성하는 것이 아니라, **추가 데이터 파일/추가 리소스/패치 데이터 등을 읽어 Gacha Static Data 또는 Config를 구성한 뒤 UI를 초기화할 가능성**을 우선 고려한다.

가능한 흐름:

```text
뽑기 메뉴 클릭
    ↓
Gacha Menu Entry
    ↓
추가 데이터 파일 / 리소스 접근
    ↓
File Load / Asset Load
    ↓
Parse / Deserialize
    ↓
Gacha Static Data / Config
    ↓
Gacha UI 초기화
```

또는:

```text
뽑기 메뉴 클릭
    ↓
Gacha Request / Response
    ↓
Response Data
    +
추가 파일 / Static Data
    ↓
Gacha UI 초기화
```

### 후속 조사 우선순위

1. 뽑기 메뉴 버튼의 실제 Click Handler
2. 메뉴 진입 직후 호출되는 함수
3. 파일 I/O 호출
4. AssetBundle / Resources / Addressables / TextAsset 접근
5. JSON / 기타 데이터 파일 Load 및 Parse
6. 로드되는 파일/리소스의 실제 이름과 경로
7. Gacha Static Data / Config 객체 생성 위치
8. 네트워크 Response가 필요한지 여부
9. 파일/리소스 Load 실패 또는 버전 불일치 시 빈 화면으로 끝나는 조건
10. 뽑기 UI 초기화에 필요한 최소 데이터 집합

### 오프라인화와의 관계

이 참고사항은 뽑기 기능을 조사할 때 **Static Data 및 추가 파일 의존성을 다른 기능보다 우선적으로 확인할 근거**로 사용한다.

단, 현재 관찰만으로 특정 파일이나 AssetBundle이 원인이라고 확정하지 않는다. 실제 파일 접근/XREF 및 런타임 흐름으로 확인한다.

### Response 분석과의 연결

뽑기 메뉴의 빈 화면 원인을 조사할 때 Response만 확인하지 않는다.

```text
Network Response
    ↓
Decode / Decrypt
    ↓
Deserialize
    ↓
Gacha Response Object
    +
추가 파일 / Static Data
    ↓
Gacha Manager / Data Object
    ↓
Gacha UI
```

따라서 Response가 정상적으로 도착하고 파싱되더라도 추가 Static Data가 없으면 UI가 초기화되지 않을 수 있는지를 확인한다.

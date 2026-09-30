# Unknown / Server Candidate

이 결과는 로컬 클라이언트 JSON에서 확인된 사실의 정리본이다.

## 원칙

- 원본 JSON에 없는 데이터는 실제 게임에 없다고 판단하지 않는다.
- 서버가 계산하거나 반환할 수 있는 확률, Weight, Quantity, Reward Result는 임의 생성하지 않는다.
- unresolved.ndjson은 로컬 데이터에서 대상을 찾지 못한 참조를 그대로 보존한다.
- system_records.ndjson의 system 값은 파일명 기반 candidate이며 최종 게임 의미가 아니다.
- m_probability, itemWeight 등의 의미는 이 단계에서 확정하지 않는다.
- 이후 구현 단계에서 확인된 데이터만 별도 Confirmed Local Data로 승격한다.

## 현재 규모

- JSON: 74
- Record: 118,015
- 고유 ID: 118,015
- 중복 ID: 0
- 검증 참조: 92,484
- 미해결 참조: 998,811
- 파싱 오류: 0

## 다음 단계

1. 정규화 데이터를 기반으로 필요한 시스템만 선택한다.
2. 실제 구현에 필요한 필드만 별도 GameData schema로 만든다.
3. 구현 중 부족한 데이터가 발견될 때만 원본/코드/네트워크를 추가 조사한다.
4. 추측 데이터와 원본 데이터를 같은 필드에 섞지 않는다.

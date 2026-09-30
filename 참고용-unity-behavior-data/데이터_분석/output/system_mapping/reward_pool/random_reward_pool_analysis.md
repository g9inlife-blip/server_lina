# Random Reward Pool / Package 공통사용 7차 분석

## 실행 결과

- JSON: 74
- 정상 파싱: 74
- 고유 Record ID: 118,015
- Package 계열 필드 발생: 437
- 고유 Package 값: 422
- 정확한 Record 정의가 있는 Package 값: 416
- 정확한 Record 정의가 없는 Package 값: 6
- Pool/Reward 계열 후보 필드 발생: 6,939
- Reward/Pool 후보 Record: 118,015
- Parse errors: 0

## 목적

Package를 Gacha 전용으로 가정하지 않고, Dungeon/Stage/Quest/Daily/Achievement/Event/Shop/Reward 등에서
동일하거나 유사한 랜덤 보상 풀/lookup 구조가 재사용되는지 탐색한다.

## 해석 원칙

- Package ID는 Record FK로 자동 확정하지 않는다.
- 서버에서만 존재하는 보상 풀인지 여부는 JSON만으로 확정하지 않는다.
- m_probability, weight, quantity 등은 field/연결 구조가 검증되기 전까지 의미를 확정하지 않는다.
- 후보군은 evidence를 보존하고 이후 코드/IL2CPP 사용 추적으로 검증한다.

## 다음 단계

1. Package/Pool 후보가 실제 Reward/Dungeon/Quest 등의 입력으로 사용되는지 확인
2. 동일 Package/Pool 값의 다중 시스템 재사용 여부 확인
3. 보상 슬롯별 Package 호출 조합 구조 확인
4. 코드/디컴파일에서 resolver 및 서버 요청 여부 추적

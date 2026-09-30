# Gacha 6.5차 — ItemPackage 구조 복원

## 핵심 모델
Package를 Character/Weapon/Item 같은 고정 타입으로 분류하지 않는다.
Package는 DrawRecord가 참조하는 하나의 관련 데이터 묶음 후보이며, 실제 성격은 내부에 연결된 Record 목록으로 후처리한다.

## 실행 결과
- stage: 6.5
- json_file_count: 0
- parsed_file_count: 0
- unique_record_ids: 118015
- draw_records: 2922
- unique_item_package_ids: 214
- package_ids_with_exact_record_definition: 0
- package_ids_with_member_references: 0
- package_ids_reused_across_multiple_groups: 6
- packages_with_multiple_evidence_types: 0
- incoming_reference_rows: 1463
- member_reference_rows: 0
- parse_errors: 0
- rules: {'package_model': 'generic related-data collection; no fixed Character/Weapon/Item package type', 'package_resolution': 'exact logical Record ID first; all-field reverse search', 'member_resolution': 'exact logical Record ID where possible', 'compound_values': 'ID|ID, comma, semicolon, and CODE*VALUE-left-ID candidates preserved', 'semantic_inference': False}

## 해석 원칙
- Package 상위 객체(Gacha/CharacterPackage/WeaponPackage 등)를 데이터에 없는 상태에서 생성하지 않는다.
- Package 내부 구성은 실제 ID 연결과 파일/Record 구조를 통해서만 확인한다.
- 한 Package 안에 Character, Weapon, Item, Fragment 등이 함께 있어도 배제하지 않는다.
- m_probability는 Package 구성원 각각의 확률이라고 자동 해석하지 않는다.
- 10회 뽑기는 데이터 구조와 코드 호출 관계를 확인하기 전까지 별도 Package로 만들지 않는다.
- 일반/한정 가챠의 차이는 Package 이름이 아니라 실제 연결 후보 목록의 차이로 검증한다.

## 출력
- gacha_package_reverse_refs.ndjson: 214개 Package ID의 전역 역참조
- gacha_package_definitions.ndjson: Package ID와 정확히 일치하는 Record 정의 및 내부 참조
- gacha_package_members.ndjson: Package → 후보 Record 연결 evidence
- gacha_package_usage.ndjson: Package의 Draw/Group 재사용 현황
- gacha_package_summary.ndjson: Package별 구성/타입 evidence 요약

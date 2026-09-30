# Gacha 6차 구조 해석

## 목적
DrawRecord의 m_itemPackageId와 m_group을 실제 Record ID 기준으로 해석하고, DrawPreviewRecord의 역참조를 찾으며, 그룹별 확률 합계를 구조적으로 검증한다.

## 실행 결과
- stage: 6
- json_file_count: 74
- parsed_file_count: 74
- unique_record_ids: 118015
- draw_records: 2922
- draw_previews: 112
- unique_draw_groups: 74
- unique_item_package_ids: 214
- resolved_item_package_ids: 0
- unresolved_item_package_ids: 214
- preview_records_with_incoming_refs: 112
- probability_groups_with_values: 74
- groups_probability_sum_exact_1: 0
- groups_probability_sum_near_1: 0
- parse_errors: 0
- rules: {'id_resolution': 'exact logical Record ID', 'obscured_id': 'hiddenValue XOR currentCryptoKey', 'grouping': 'DrawRecord.m_group', 'probability_validation': 'sum only; semantic meaning not auto-confirmed'}

## 해석 원칙
- ItemPackage는 파일명만으로 확정하지 않고 ID로 역검색한다.
- m_group은 우선 그룹화 키로만 사용하며 Gacha Pool이라는 의미는 구조 검증 후 확정한다.
- m_probability는 그룹 합계 검증만 수행하며 실제 확률/가중치 여부는 추가 증거가 필요하다.
- 원본에 없는 비용/수량/천장 값은 생성하지 않는다.

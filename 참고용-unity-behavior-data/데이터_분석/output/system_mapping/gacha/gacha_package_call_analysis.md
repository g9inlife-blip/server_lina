# Gacha 6.6차 — m_itemPackageId 호출/Lookup 구조 추적

## 목적
- m_itemPackageId를 실제 Record ID 연결이라고 고정하지 않고 호출값/lookup key 후보로 추적한다.
- JSON에서 확인 가능한 구조적 evidence와 실제 네트워크 호출 여부를 분리한다.

## 결과
- stage: 6.6
- json_file_count: 74
- parsed_file_count: 74
- unique_record_ids: 118015
- draw_records: 2922
- unique_item_package_ids: 214
- total_package_id_occurrences: 1463
- package_ids_with_exact_record_definition: 0
- package_ids_seen_in_key_or_id_context: 0
- package_ids_seen_in_package_named_context: 0
- package_ids_reused_across_multiple_groups: 6
- compound_occurrence_rows: 0
- parse_errors: 0
- context_counts: {'DRAW_PACKAGE_CALL_VALUE': 1463}
- rules: {'m_itemPackageId': 'opaque call/lookup candidate, not assumed to be a Record ID', 'network_claim': 'not confirmed by JSON alone', 'lookup_claim': 'structural candidate only', 'id_restore': 'hiddenValue XOR currentCryptoKey', 'semantic_inference': False}

## 해석 규칙
- DrawRecord.m_itemPackageId는 우선 opaque key/value로 보존한다.
- JSON만으로 서버 API 호출이라고 확정하지 않는다.
- 동일 값의 key/id/package/array/compound 문맥을 비교한다.
- Package ID가 Record ID와 일치하지 않아도 정상 후보로 유지한다.
- 실제 호출 여부는 코드/디컴파일 데이터에서 caller → parameter → resolver 흐름이 확인될 때 확정한다.

## 다음 단계
1. 반복되는 field/parent 구조를 확인한다.
2. 코드/디컴파일 산출물에서 m_itemPackageId, ItemPackage, packageId 계열 사용처를 검색한다.
3. 서버 요청 parameter와 연결되면 API/오프라인 resolver 구조를 복원한다.
4. 연결되지 않으면 클라이언트 local table/index 구조를 우선 조사한다.
5. 이후 Package → Item/Weapon/Fragment/Character/Reward 결과 풀을 복원한다.

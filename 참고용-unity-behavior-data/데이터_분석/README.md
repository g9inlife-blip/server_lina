# 데이터 분석

이 폴더는 참고용-unity-behavior-data 내부의 실제 JSON 데이터를 기계적으로 분석하여 ID 참조 그래프와 무결성 결과를 축적하기 위한 영역이다.

## 분석 원칙
- Python이 사실 추출과 검증을 담당한다.
- LLM은 Python이 만든 결과를 바탕으로 의미와 계층을 해석한다.
- 아직 API/Response 구조나 Research MD와 연결하지 않는다.
- 존재하지 않는 ID를 임의로 다른 Record에 연결하지 않는다.
- xxxId, m_xxxId, xxxIds 같은 참조 후보를 자동 탐색하되 최종 의미는 별도로 해석한다.

## 실행
저장소 루트에서:
    python 참고용-unity-behavior-data/데이터_분석/build_data_graph.py

또는 분석 폴더에서:
    python build_data_graph.py

## 생성 결과
- output/01_record_inventory.json : 발견된 JSON/Record/ID inventory
- output/02_reference_graph.json : 실제 대상 ID가 존재하는 검증된 참조
- output/03_unresolved_references.json : 후보지만 대상 ID를 찾지 못한 참조
- output/04_duplicate_ids.json : 서로 다른 위치에서 중복 발견된 ID
- output/05_reference_summary.json : 전체 통계
- output/06_data_graph.md : 사람이 읽는 파일 간 그래프 요약

## 처리 원칙
원본 JSON은 수정하지 않는다. 실행할 때 output을 새로 만든다.
이 결과는 게임 로직의 최종 해석 문서가 아니다. 예를 들어 m_itemPackageId가 어떤 Record를 가리키는지는 검증할 수 있지만, 그것이 어떤 런타임 상황에서 소비되는지는 코드 분석이 필요하다.

흐름:
JSON 원본 → Python 추출 → ID 존재 여부 검증 → Reference Graph → LLM 의미 해석 → 나중에 Research / Response 구조

미해결 참조는 오류라고 단정하지 않는다. 외부 데이터, 런타임 생성 ID 또는 다른 표현 방식일 수 있다.
# Gacha / Draw 4차 분석

DrawRecord와 DrawPreviewRecord의 실제 Reference를 조사하는 단계다.

확률/수량/가격은 필드명만으로 확정하지 않는다. 각 NDJSON에는 원본 파일/Record path/field와 대상 Reference evidence를 보존한다.

다음 단계는 반복 구조를 이용해 실제 Draw → Preview → ItemPackage → Item 체인을 정제하고, 확률/비용/기간/천장 필드의 의미를 교차 검증하는 것이다.

# code_mapping

서버 구축용 코드데이터 2차 가공 영역이다.

## 역할
기존 분석 결과를 변경하지 않고 Unity MonoBehaviour 원본, Word__krRecord,
데이터_분석/output/system_mapping, 향후 Bootstrap/PCAP 실측값,
Ghidra 런타임 관계를 결합한다.

## 구조
code_mapping/
- README.md
- scripts/build_code_catalog.py
- output/ (생성 결과)

## 원칙
- output/system_mapping은 기존 분석 산출물이므로 직접 수정하지 않는다.
- Unity 원본 JSON은 수정하지 않는다.
- Python은 사실 추출과 정규화를 담당한다.
- hiddenValue XOR currentCryptoKey가 가능한 Record는 복호화 ID를 보존한다.
- m_nameId / m_describeId / m_groupNameId / m_subNameId는 별도 필드로 보존한다.
- 게임 의미를 Python 단계에서 임의 확정하지 않는다.
- Bootstrap과 연결되는 결과는 별도 crosswalk에서 검증한다.

## 목표
Network ID -> Unity Record -> 명칭/설명 코드 -> Word__krRecord -> 한국어 명칭
의 재현 가능한 데이터 파이프라인을 만든다.

향후:
- output/code_catalog.json
- output/item_catalog.json
- output/hero_catalog.json
- output/weapon_catalog.json
- output/equipment_catalog.json
- output/bootstrap_crosswalk.json

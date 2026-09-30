# 7.1 Package Record 구조 / 역참조 분석

- JSON: 74
- 정상 파싱: 74
- 고유 Record ID: 118,015
- Package 값: 422
- 정확한 Package Record 정의: 416
- 정의 미확인 Package 값: 6
- 분석 Package Record: 416
- 역참조: 464
- 역참조가 있는 Package: 416
- 다중 시스템 문맥 Package: 33

이 단계는 Package 의미를 미리 확정하지 않는다. 정확한 Record 정의와 실제 역참조를 우선한다. 7차에서 정의가 확인된 Package 값과 Gacha의 214개 m_itemPackageId 미정의 값은 별도 집합으로 유지한다. 확률, weight, quantity, price 및 서버 전용 여부는 추정하지 않는다.

다음: 다중 시스템 재사용 Package의 실제 source Record 조사 → 내부 member 타입 분류 → IL2CPP/decompile에서 caller/resolver 추적 → 서버 요청인지 로컬 lookup인지 검증.

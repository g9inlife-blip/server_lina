# 가챠 시스템 매핑 분석

## 분석 대상
- DrawRecord.json
- DrawpreviewRecord.json
- ItempackageRecord.json
- ShopRecord.json

## 확인된 구조

가챠 관련 데이터는 단일 테이블이 아니라 다음 관계로 구성된다.

`ShopRecord → Draw/DrawPreview → ItemPackage → Item`

### 1. ShopRecord
ShopRecord에는 `m_drawPreviewGroup` 필드가 존재한다. 이는 상점에서 표시할 가챠/상품 미리보기 그룹과 연결되는 핵심 필드다.

예:
- `shop_18200000`
- `m_shopType = 1`
- `m_group = 2000`
- `m_currency = 43000003|43000001|43000002`
- `m_drawPreviewGroup = "1"`

따라서 ShopRecord는 어떤 가챠 UI/상점이 어떤 미리보기 그룹을 사용하는지 연결하는 출발점으로 볼 수 있다.

### 2. DrawRecord
DrawRecord에는 총 2,922개 레코드가 확인되며 다음 핵심 필드를 가진다.

- `m_quality`
- `m_period`
- `m_star`
- `m_type`
- `m_specialShow`
- `m_nameId`
- `m_describeId`
- `m_PumpingCard1`
- `m_PumpingCard2`
- `m_iconshow`
- `m_group`
- `m_probability`
- `m_limit`
- `m_itemPackageId`
- `m_desc`

확인된 예:
- `m_group = 1`
- `m_desc = "5星装备"`
- `m_probability = 1`
- `m_limit = 1`
- `m_itemPackageId = "45200200*100"`

또 다른 레코드:
- `m_desc = "4星装备"`
- `m_itemPackageId = "45200100*100"`
- `m_probability = 1`
- `m_limit = 0`

즉 `452xxxxx` 계열 ItemPackage가 가챠 결과 생성에 사용되는 패키지 계열로 강하게 추정된다.

### 3. DrawpreviewRecord
DrawpreviewRecord는 총 112개 레코드가 확인되며 확률 표시와 실제 대상 아이템을 연결하는 필드를 가진다.

핵심 필드:
- `m_probability`
- `m_articleID`
- `m_group`
- `m_nameId`

확인 예:
`m_probability = 0.0075` (0.75%)

해당 레코드의 `m_articleID`에는 다음과 같이 여러 장비 ID가 묶여 있다.

`40000004|40000104|40000204|40000304|40000404|40000804|40001204|40000904|40001104|40000704|40001404|40000504|40001504|40001604|40001004|40001304|40002006`

따라서 DrawpreviewRecord는 실제 가챠에서 등장 가능한 장비 목록과 표시 확률을 복원하는 데 핵심적인 테이블이다.

## 확률 해석 시 주의점

`DrawRecord.m_probability`와 `DrawpreviewRecord.m_probability`를 동일한 의미의 최종 아이템 확률로 간주하면 안 된다.

현재까지 확인된 구조상:
- DrawRecord: 등급/그룹/패키지 단위의 추첨 정의
- DrawpreviewRecord: 실제 기사/장비 ID와 표시 확률
- ItempackageRecord: 패키지 내부의 실제 보상 구성 및 가중치
- ShopRecord: 상점/가챠 UI와 그룹 연결

따라서 최종 확률은 다음 단계에서 중첩 확률을 풀어야 한다.

`최종 아이템 확률 = Draw 단계 확률 × ItemPackage 내부 확률 × (필요한 경우 Preview/그룹 분배)`

단, 실제 구현 코드 확인 전에는 이 수식을 확정적인 게임 로직이라고 단정하지 않는다.

## ItemPackage
던전 보상에서 `450xxxxx` 계열 패키지가 사용된 것처럼, 가챠에서는 `452xxxxx` 계열 패키지가 확인된다.

예:
- `45200100*100`
- `45200200*100`

따라서 다음 분석이 필요하다.
1. 모든 `452xxxxx` ItemPackage 추출
2. 각 패키지의 내부 Item/ItemBox 및 가중치 파싱
3. ItemRecord와 연결하여 실제 아이템 이름/등급/종류 복원
4. DrawRecord의 group/quality/desc와 연결
5. DrawpreviewRecord의 articleID/probability와 대조

## 현재까지 복원 가능한 가챠 데이터 관계

| 계층 | 파일 | 핵심 키/필드 | 역할 |
|---|---|---|---|
| 상점 | ShopRecord | m_drawPreviewGroup | 가챠 UI/미리보기 그룹 연결 |
| 추첨 정의 | DrawRecord | m_group, m_quality, m_probability, m_limit, m_itemPackageId | 등급/추첨/패키지 정의 |
| 확률/목록 | DrawpreviewRecord | m_group, m_probability, m_articleID | 실제 등장 아이템 및 표시 확률 |
| 결과 패키지 | ItempackageRecord | 452xxxxx | 실제 보상 생성 |
| 아이템 | ItemRecord | Item ID | 실제 아이템 정보 |

## 다음 분석 목표

### A. 실제 가챠 목록
각 ShopRecord의 `m_drawPreviewGroup`을 기준으로:
- 가챠 이름
- Shop ID
- Draw group
- 사용 재화
- 단일/10회 비용
- 대상 등급
- 대상 아이템
- 기간/오픈 조건

을 하나의 표로 통합한다.

### B. 확률표
각 가챠별로:
- 5성
- 4성
- 3성
- 기타 등급

의 확률을 우선 복원하고, 이후 각 등급 내부의 실제 아이템 확률까지 계산한다.

### C. 천장/보장
다음 필드를 우선 조사한다.
- `m_limit`
- `m_PumpingCard1`
- `m_PumpingCard2`
- 관련 DrawRecord 그룹
- 가챠 횟수/10회/보장 관련 코드 및 문자열

특히 `m_limit`은 단순 표시 제한인지 확정 횟수/보장 조건인지 코드 확인이 필요하다.

## 데이터 복호화 참고
Unity ObscuredInt에서 확인된 공통 키:
`currentCryptoKey = 444444`

논리 ID가 필요한 경우 일반적으로:
`logicalID = hiddenValue XOR 444444`

단, 모든 숫자 필드에 이 공식을 기계적으로 적용하지 않고 ObscuredInt 구조가 확인된 필드에만 적용한다.

## 결론
가챠 데이터는 저장되어 있으며, 핵심 연결고리는 확인되었다.

현재 단계에서는 "가챠가 존재한다" 수준을 넘어:
- 어떤 Shop이 어떤 DrawPreview 그룹을 쓰는지
- DrawRecord가 어떤 등급/패키지를 정의하는지
- DrawpreviewRecord가 어떤 실제 장비와 확률을 표시하는지
- ItemPackage가 실제 결과를 어떻게 구성하는지

를 연결할 수 있는 상태다.

다만 실제 가챠별 완전 확률표를 만들기 위해서는 `452xxxxx ItemPackage` 전체를 파싱하고 Draw/Preview/Shop의 group 관계를 전수 매핑해야 한다.

# 2026-10-02 Energy GetXCount 추적

## 결론

`UserInfo.get_Energy @ 00dd2ce4`는 UserInfo 직접 저장값이 아니다.

```text
UserInfo.get_Energy
  → DataCenter.GetXCount @ 016defb0
  → key 0x029020C3
```

Assembly에서 GetXCount 호출 인자는 다음으로 확인된다.

- w1 = 0x029020C3
- w2 = 0
- w3 = 0

기존 GetXCount 분석에서는 DataCenter `+0x78` Dictionary 계열을 조회하는 것으로 확인됐다.

## Bootstrap 연결

```text
OpInfo +0x98 Items
  ↓
DataCenter.MergeItem @ 016e4700
  ↓
Item/category cache (+0x78 계열)
  ↓
GetXCount(0x029020C3)
  ↓
UserInfo.get_Energy
```

따라서 Local Server에서 Energy를 UserInfo 고정 offset으로 모델링하지 않는다.

## EnergyNextTime

`ProccessRequestRes @ 016e203c`는 `DataCenter.set_EnergyNextTime @ 016ded44`를 직접 호출한다.

`DataCenter.get_EnergyNextTime @ 016decdc`는 GUI update 계층에서 사용된다.

즉:

- Energy 수량: `GetXCount(0x029020C3)`
- Energy 회복시각: `EnergyNextTime`

두 상태를 분리한다.

## 다음 작업

1. `GetXCount @ 016defb0` 본문에서 실제 Dictionary 조회와 기본값 확정
2. `0x029020C3`가 실제 ProtoItem/원본 JSON의 어떤 항목인지 Git 데이터 대조
3. `HomePanelMono.Start @ 00f67adc` 직접 getter 목록 확정
4. 결과를 Bootstrap 필수/선택 필드에 반영
## 2. GetXCount 본문 확인

`DataCenter.GetXCount @ 016defb0`는 `this + 0x78`만 단순 조회하는 함수가 아니다. `itemId`와 내부 BaseData의 type을 함께 사용해 재화/아이템 종류별 조회 경로를 분기한다.

핵심 Assembly:

```text
this              = x19
itemId            = w20
mode/flag         = w21
BaseData lookup   = DataManager.TryGetBaseData(itemId)
BaseData.type     = [BaseData + 0x24]
```

확인된 분기 중 일반 Item 경로는 `this + 0x78` Dictionary를 사용한다.

```text
this + 0x78
  → Dictionary<int, object>
  → key별 collection
  → ProtoItem 계열 값
  → Count @ +0x18
```

또한 type에 따라 `+0x40`, `+0x60`, `+0x80` 등의 다른 DataCenter collection을 사용하며, Stigmata/Weapon/Equip 상태도 이 함수에서 별도 처리한다.

따라서 `GetXCount`는 단순 `Items[itemId].Count` 함수가 아니라 BaseData.type을 기준으로 여러 상태 저장소를 통합 조회하는 공통 수량 함수다.

## 3. Energy / Crystals key

기존 Git 분석과 `UserInfo.get_Energy` Assembly를 결합하면:

```text
Energy   = itemId 0x029020C3
Crystals = itemId 0x029020C2
```

따라서 로그인 직후 Main의 재화 표시를 만들 때 UserInfo의 Coins/Energy/Crystals를 모두 직접 필드로 만들면 안 된다. 최소한 Energy/Crystals는 `GetXCount` 공통 경로를 재현해야 한다.

## 4. HomePanelMono.Start 현재 확인 수준

`HomePanelMono.Start @ 00f67adc` 자체의 전체 Listing은 현재 검색 결과에서 직접 확보하지 못했다.

대신 Calls IN/OUT와 별도 함수 Listing에서 다음은 확정됐다.

- `DataCenter.get_CurrentEquipMax @ 016de53c` → HomePanelMono.Start
- `DataCenter.get_NextEquipMax @ 016de648` → HomePanelMono.Start
- `DataCenter.get_EquipMax @ 016de7cc` → HomePanelMono.Start
- `Ali.get_dataCache @ 00e014f4` → HomePanelMono.Start
- `Ali.GetExcelDic<object> @ 01737100` → HomePanelMono.Start 계열

따라서 현재 Main Bootstrap 우선순위는:

```text
Items / 재화 상태
Energy 0x029020C3
Crystals 0x029020C2
UserInfo Id/Name/Level/Exp
EquipMax / CurrentEquipMax / NextEquipMax
Chapters / Sections
Hero / Weapon / Equipment
```

로 유지한다.

## 5. 다음 작업

1. `0x029020C3`의 BaseData.type과 원본 Item/Excel 데이터 직접 대조
2. `GetXCount`의 type별 collection mapping을 표로 완성
3. `HomePanelMono.Start` body를 함수명/주소 기준으로 직접 확보
4. Main에서 실제 표시되는 Coins/Crystals/Energy를 동일 방식으로 묶어 Bootstrap fixture 설계

## 6. 2026-10-02 재화 ID 원본 Record 대조 및 GetXCount 분기

### 6.1 UserInfo 재화 키 전체 확인

Git Listing의 getter 본문에서 3개 ID를 직접 확인했다.

| 재화 getter | 함수 RVA | GetXCount itemId | 10진수 ID |
|---|---:|---:|---:|
| Coins | `00dd2d8c` | `0x029020C1` | `43000001` |
| Crystals | `00dd2e34` | `0x029020C2` | `43000002` |
| Energy | `00dd2ce4` | `0x029020C3` | `43000003` |

세 getter 모두 DataCenter Singleton을 통해 `GetXCount(itemId, 0, 0)`를 호출한다. Coins도 UserInfo 직접 필드가 아니다.

### 6.2 원본 Unity 데이터 대조

Git의 `참고용-unity-behavior-data/데이터_분석/output/data_catalog/09_record_samples.json`에서 다음을 확인했다.

- 43000001 / 43000002 / 43000003 모두 `ItemRecord.json`의 Record
- 각각 `m_icon=item_43000001/2/3`
- `baseDataType=0`
- `item_tables.md`에도 세 ID가 Item Record 목록에 존재
- SysconfRecord의 개인 정보 재화 표시 설정(`个人信息货币显示`) 목록에도 세 ID가 포함

단, 이 샘플의 `baseDataType=0`을 Ghidra의 `BaseData +0x24`에서 읽는 `BaseData.type` enum과 동일하다고 단정하지 않는다. 현재 둘의 직접 매핑은 미확정이다.

### 6.3 GetXCount type별 경로 — Assembly 분기값

`GetXCount @ 016defb0`는 `DataManager.TryGetBaseData(itemId)` 후 `[BaseData +0x24]`를 비교한다.

| BaseData.type | DataCenter 저장소 | 조회 방식 | 반환 계산 |
|---:|---:|---|---|
| `0x22` | `+0x78` | ItemType enum key `0` → 내부 Dictionary에서 itemId | 값 객체 `+0x18` |
| `0x41` | `+0x78` | ItemType enum key `1` → 내부 Dictionary.TryGetValue(itemId) | 값 객체 `+0x18`; mode bit에 따라 추가 Stigmata 처리 |
| `0x1F` | `+0x78` | ItemType enum key `2` → 내부 Dictionary에서 itemId | 값 객체 `+0x18` |
| `0x19` | `+0x60` | itemId ContainsKey | 보유 여부 0/1 |
| `0x04` | `+0x30` | itemId ContainsKey | 보유 여부 0/1 |
| `0x2E` | `+0x40` | itemId → WeaponInfo | IsLocked의 반전값 |
| `0x2B` | `+0x38` | EquipInfo 값 열거 후 EquipmentId 비교 | 일치 개수 |
| `0x43` | `+0x80` | enum key `1` → itemId | 값 객체 `+0x1C != 0` |

위 표의 enum key와 offset은 Assembly의 실제 Dictionary 호출 인자 및 receiver offset을 기준으로 기록했다. 미분석 type은 별도 일반 fallback으로 들어가며, 현재는 로그 출력 외에 의미를 확정하지 않는다.

### 6.4 MergeItem이 GetXCount와 같은 분류를 수행

`DataCenter.MergeItem @ 016e4700`에서도 각 입력 item에 대해 BaseData를 조회하고 `[BaseData +0x24]`를 검사한다.

- type `0x1F` → ItemType enum key `2`
- type `0x22` → ItemType enum key `0`
- type `0x41` → ItemType enum key `1`

해당 enum별 내부 Dictionary를 생성/갱신하고 itemId를 key로 Item 객체를 저장한다.

따라서 재화 수량 경로는 다음으로 정리된다.

```text
OpInfo +0x98 Items
  → DataCenter.MergeItem
  → BaseData.type 분류
  → DataCenter +0x78[ItemType]
  → Dictionary<itemId, ItemInfo>
  → GetXCount(itemId)
  → UserInfo.get_Coins / get_Crystals / get_Energy
  → Main UI
```

### 6.5 현재 확정 / 미확정

**확정**
- Coins/Crystals/Energy ID = 43000001/2/3
- 세 값 모두 ItemRecord에 존재
- 세 getter가 모두 GetXCount를 호출
- MergeItem과 GetXCount가 동일한 BaseData.type 분기 체계를 사용
- type 0x22/0x41/0x1F의 ItemType enum key가 각각 0/1/2

**미확정**
- 43000001/2/3 각각의 실제 `BaseData +0x24` runtime type 값
- 세 재화가 동일 ItemType bucket인지 여부
- 실기기 MergeItem 입력에서 세 ID의 Count 및 bucket key
- Main 초기화 시점에 실제 표시되는 재화 UI 호출 순서

### 6.6 다음 단계

1. `BaseData.get_type @ 00df34dc` 및 BaseData 초기화/생성 경로를 확인해 Record의 `baseDataType`과 runtime type을 연결
2. runtime hook에서 MergeItem 입력의 43000001/2/3별 BaseData.type, ItemType enum key, Count 출력
3. HomePanel Start Listing 확보 여부와 별개로 `UserInfoPanelMono.RefreshTopInfos → ShowCoin`을 통해 Main 재화 UI의 직접 소비 순서 확인
4. 실제 관측 결과를 Bootstrap fixture의 Items 데이터에 반영



## 7. v4.23 runtime 계측 추가

정적 분석만으로는 43000001/2/3 각각의 실제 BaseData.type과 bucket을 분리할 수 없어 `research/justice_hook.js`에 필터링 계측을 추가했다.

새 로그:

- `[CURRENCY_BASEDATA]`: 세 재화 ID에 한해 TryGetBaseData 결과, BaseData 주소, `BaseData +0x24` type 출력
- `[CURRENCY_COUNT]`: 세 재화 ID에 한해 GetXCount의 mode와 반환 수량 출력

대상 ID 외의 BaseData/GetXCount는 출력하지 않으며, 전체 Item dictionary나 인증/네트워크 payload를 덤프하지 않는다.

스크립트:
- `research/justice_hook.js` v4.23
- commit: `b22b5e994d13f5bcbb8ca1dc707c98f4ae4169da`

### 다음 실행

로그인 후 Main 화면까지 진입하고 재화 표시가 갱신되도록 둔다. 아래 로그를 확보한다.

```text
[CURRENCY_BASEDATA] Coins ...
[CURRENCY_BASEDATA] Crystals ...
[CURRENCY_BASEDATA] Energy ...
[CURRENCY_COUNT] Coins ...
[CURRENCY_COUNT] Crystals ...
[CURRENCY_COUNT] Energy ...
```

이 결과로 Record의 `baseDataType`과 runtime `BaseData.type`을 혼동하지 않고, 세 재화의 실제 ItemType bucket과 Count를 확정한다.

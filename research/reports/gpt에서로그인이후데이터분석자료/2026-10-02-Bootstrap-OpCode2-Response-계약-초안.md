# 2026-10-02 Bootstrap OpCode=2 Response 계약 초안

## 1. 목적

Local Private Server 구현을 위해 로그인 직후 메인 화면으로 전달되는 Bootstrap `OpCode=2` Response를 **최소 필드가 아니라 현재 관측된 전체 응답 envelope부터 재현하는 방향**으로 정리한다.

메인 화면은 User/Inventory뿐 아니라 Chapter, Hero, Weapon, Equipment, Quest, Shop, Activity 등의 상태를 여러 UI가 공유할 가능성이 있으므로, 현재 단계에서는 필드를 임의로 제거하지 않는다.

## 2. 현재 확정된 통신 경계

```
Login 완료
  ↓
KCPTube.Send
  ↓
OpInfo
  SerialNumber=<request id>
  OpCode=2
  ReturnCode=0
  ↓
KCP response
  ↓
Deserialize<object>
  ↓
NetworkCenter.TryHandleResponse
  ↓
DataCenter.ProccessRequestRes
  ↓
Main State / UI
```

실제 최신 runtime에서 Bootstrap 요청/응답의 SerialNumber가 동일하게 연결되는 것이 확인됐다.

## 3. 관측된 OpInfo Response envelope

현재 runtime에서 확인된 주요 필드:

| Offset | Field | Type | 현재 관측 |
|---|---|---|---|
| +0x88 | User | ProtoUser | non-null |
| +0x90 | Heros | Dictionary<int, ProtoHero> | non-null |
| +0x98 | Items | Dictionary<int, ProtoItem> | non-null, 98개 |
| +0xA0 | Weapons | Dictionary<int, ProtoWeapon> | non-null |
| +0xA8 | Equiments | Dictionary<string, ProtoEquipment> | non-null |
| +0xB0 | Mails | Dictionary<string, ProtoMail> | null |
| +0xC0 | Chapters | Dictionary<int, ProtoChapter> | non-null, 61개 |
| +0xC8 | Sections | Dictionary<int, ProtoSection> | non-null |
| +0xD0 | Teams | Dictionary<int, ProtoTeam> | non-null |
| +0xD8 | ViewItems | List<ProtoViewItem> | null |
| +0xE0 | Fashions | Dictionary<int, ProtoFashion> | non-null |
| +0xE8 | Quests | Dictionary<int, ProtoQuest> | non-null |
| +0xF0 | Shops | Dictionary<int, ProtoShop> | non-null |
| +0xF8 | Charges | Dictionary<int, ProtoCharge> | non-null |
| +0x100 | Friends | Dictionary<long, ProtoFriend> | null |
| +0x108 | Exam | ProtoRank | null |
| +0x118 | Ranks | Dictionary<long, ProtoRank> | null |
| +0x120 | Activities | Dictionary<int, ProtoActivity> | non-null |
| +0x128 | Msgs | List<ProtoMsg> | null |

추가적으로 +0x70 DictI32, +0x78 BattleReslut, +0x80 FC 등의 필드가 존재하며 Bootstrap에서는 null 또는 non-null 여부를 별도로 확인할 필요가 있다.

## 4. 현재 구현 전략

사용자 판단을 반영해 다음 순서로 진행한다.

### Phase A — Full Bootstrap envelope

현재 실기기에서 관측된 Response 구조를 기준으로 Local Server의 첫 응답 계약을 작성한다.

- ReturnCode=0
- OpCode=2
- SerialNumber request correlation
- User
- Heros
- Items
- Weapons
- Equiments
- Chapters
- Sections
- Teams
- Fashions
- Quests
- Shops
- Charges
- Activities
- 기타 OpInfo 필드는 null/empty를 포함해 envelope 형태를 유지

### Phase B — Client 처리 순서 확인

`DataCenter.ProccessRequestRes`에서 실제로 어떤 필드를 읽고 Merge하는지 정적 분석한다.

목표는 다음과 같다.

```
OpInfo field
 ↓
Merge/State mutation
 ↓
DataCenter cache
 ↓
Main UI
```

필드가 Response에 존재하는 것과 Client가 반드시 사용하는 것은 구분한다.

### Phase C — Local Server 연결

Full envelope를 먼저 반환하고 실제 클라이언트에서:

- 로그인 완료
- Main 진입
- User 정보 표시
- 재화 표시
- Hero/Weapon/Equipment 표시
- Chapter/Section 표시
- Quest/Shop/Activity 초기화
- Warehouse 표시

를 순서대로 확인한다.

### Phase D — 최소화

Full envelope가 정상 동작한 뒤에만 필드를 하나씩 제거하면서 실패 지점을 확인한다.

따라서 '절대 최소 Response'는 구현 전에 추측하지 않는다.

## 5. Items는 이미 효과가 확인됨

최신 runtime:

```
Items Dictionary = 98
  ↓
DataCenter.MergeItem
  ↓
DataCenter category cache
  ↓
WareHousePanelMono.InitData
  ↓
List 76 / 10 / 23 / 11
  ↓
ShowGoods
  ↓
ProtoItem UI
```

따라서 Items는 단순 Response 존재 확인을 넘어 실제 Main 이후 UI 상태에 영향을 주는 것이 확정됐다.

## 6. Chapters도 초기 상태 데이터로 유지

Chapters Dictionary는 61개이며:

```
OpInfo +0xC0
 → Dictionary<int, ProtoChapter>
 → ProtoChapter.BoxStatus
 → Chapter UI
```

가 runtime/static 분석으로 연결되어 있다.

따라서 초기 Bootstrap 구현에서 Chapters를 제외하지 않는다.

## 7. 주의사항

- 'non-null'은 '메인 진입 필수'라는 뜻이 아니다.
- 현재 관측값을 그대로 구현하고 이후 테스트로 필수 여부를 좁힌다.
- null인 필드는 임의의 가짜 데이터를 채우지 않는다.
- Items/Chapters처럼 실제 UI 효과가 확인된 필드는 우선 구현 대상으로 취급한다.
- 아이템 이름/Record 전체 복원은 Bootstrap 계약에 필요한 경우에만 추가한다.

## 8. 다음 작업

1. `DataCenter.ProccessRequestRes` Ghidra Listing에서 Response field 처리 순서를 확정
2. Merge 대상별 Client State cache 위치를 정리
3. Local Server가 반환할 Bootstrap JSON/객체 계약 초안 작성
4. KCP Response serializer에 연결할 최소 데이터 구조 설계
5. 실제 Client 연결 테스트

현재 단계에서는 **Full Bootstrap Response → 실제 Client 진입 검증 → 필요 시 최소화** 순서를 적용한다.


## 9. 2026-10-02 Ghidra Listing 재확인 — ProccessRequestRes 본문 확보

Git의 `research/Ghidra_Listing_txt`를 함수명 기준으로 재검색했다.

### 확인
- `DataCenter.ProccessRequestRes @ 016e203c` 본문은 `research/Ghidra_Listing_txt/DA.txt`의 `### FILE: 016e203c_DataCenter__ProccessRequestRes.txt` 블록에서 확보되어 있다.
- 따라서 Response field → merge 함수의 직접 처리 순서를 Assembly로 확인할 수 있다.
- 별도 개별 함수 파일 부재 여부와 관계없이 DA.txt 원본 Listing을 기준으로 판단한다.

| 대상 | RVA | 현재 근거 |
|---|---:|---|
| ProccessRequestRes | 016e203c | DA.txt 본문 확보, response 진입점 |
| MergeEquip | 016e4348 | Bootstrap Equiments 관련 후보 |
| MergeItem | 016e4700 | Items → DataCenter category cache 확정 |
| UpdateHeroInfo | 016e4ba4 | Hero/User 상태 갱신 후보 |
| MergeSections | 016e55dc | Section 상태 merge 관련 |
| MergeSectionSnapShot | 016e5908 | Section snapshot merge 관련 |
| MergeWeapon | 016e5be4 | Weapons 상태 merge 후보 |

### 현재 확정 수준
```
OpInfo.Items
  → ProccessRequestRes
  → MergeItem
  → DataCenter +0x78 category cache
  → Warehouse UI
```

위 Items 경로는 정적+runtime으로 확정했다.

반면 아래 중 UpdateHeroInfo의 내부 User/Heros 분리 방식은 아직 미확정이다.
```
User       → ?
Heros      → UpdateHeroInfo ?
Weapons    → MergeWeapon ?
Equiments  → MergeEquip ?
Sections   → MergeSections / MergeSectionSnapShot ?
Chapters   → ?
Teams      → ?
Fashions   → ?
Quests     → ?
Charges    → ?
Activities → ?
```

따라서 Local Server 구현을 지금 시작할 때는 위 필드들을 제거하지 않고 Full Bootstrap envelope로 유지한다.

### 다음 조사 방향 변경

원본 `ProccessRequestRes` 본문을 억지로 추정하지 않는다. 다음 순서로 실제 계약을 좁힌다.

1. 각 merge 함수의 Listing/인자 타입/field access 확보
2. OpInfo getter(`get_User`, `get_Heros`, `get_Weapons` 등)와 merge 함수의 연결 확인
3. runtime hook에서 merge 함수 호출 여부를 Bootstrap 한 건으로 대조
4. 실제 Client Main 진입을 기준으로 필수 field를 검증

이 단계에서 **Full Bootstrap → Client 검증 → 필요 시 최소화** 원칙은 유지한다.


## 10. DA.txt 확인 결과 — ProccessRequestRes 본문 확보

사용자가 지적한 `DA.txt`의 `### FILE: 016e203c_DataCenter__ProccessRequestRes.txt` 블록이 실제 원본 Listing이다. 이전의 "본문 미확보" 판단은 잘못이었다.

핵심 merge 구간은 `0x016e29dc~0x016e2aec`이다.

```
response = x26
DataCenter = x20

+0xA0 → 0x016e414c → DataCenter cache +0x40
+0xA8 → 0x016e4348 → MergeEquip       → cache +0x38
+0x98 → 0x016e4700 → MergeItem        → cache/Item
        ↓
        0x016e4ba4 → UpdateHeroInfo   (response 전체 x26 전달)
+0xC0 → 0x017704a0 → cache +0x48     (Chapters)
+0xC8 → 0x016e55dc → MergeSections    → cache +0x50
+0xD0 → 0x017704a0 → cache +0x58     (Teams)
+0xE8 → 0x017704a0 → cache +0x80     (Quests)
+0xB0 → 0x01770ce4 → cache +0x88     (Mails)
+0xF0 → 0x017704a0 → cache +0x68     (Shops)
+0xF8 → 0x017704a0 → cache +0x70     (Charges)
```

또한:
- `+0x130`은 non-null일 때 DataCenter `+0x100`에 직접 저장
- `+0x80`은 non-null일 때 DataCenter `+0x108`에 직접 저장
- response opcode/type(`[x26,#0x14]`)가 `0x3c/0x41`가 아닐 경우 response `+0x100`을 별도 `Merge<long,object>` 계열로 처리
- response `+0x148`은 DataCenter `+0xA0`의 Merge 대상

### 중요

따라서 Bootstrap Response는 단순히 "필드가 존재하는가"가 아니라 실제로 다음과 같이 **DataCenter 상태를 직접 채우는 구조**임이 정적 분석으로 확정됐다.

```
OpInfo
 ├─ +0x98 Items      → MergeItem
 ├─ +0xA0 Weapons    → Merge<int,object> 계열
 ├─ +0xA8 Equiments  → MergeEquip
 ├─ +0xC0 Chapters   → Merge<int,object> 계열
 ├─ +0xC8 Sections   → MergeSections
 ├─ +0xD0 Teams      → Merge<int,object> 계열
 ├─ +0xE8 Quests     → Merge<int,object> 계열
 ├─ +0xB0 Mails      → Merge<long,object> 계열
 ├─ +0xF0 Shops      → Merge<int,object> 계열
 └─ +0xF8 Charges    → Merge<int,object> 계열
```

이는 사용자가 말한 "메인 화면에서 여러 정보가 한 번에 필요하다"는 가설과도 구조적으로 일치한다. 단, 각 UI가 실제로 어느 시점에 각 cache를 사용하는지는 runtime 검증을 계속한다.


## 11. 2026-10-02 ProccessRequestRes 직접 호출 순서 재확인

DA.txt의 실제 Listing과 Calls OUT를 다시 대조했다. 정확히 +0xA0는 DataCenter.MergeWeapon @ 016e414c이다.

| Response offset | 처리 함수 | DataCenter 대상 | 상태 |
|---|---|---|---|
| +0xA0 | MergeWeapon @ 016e414c | cache +0x40 | 확정 |
| +0xA8 | MergeEquip @ 016e4348 | cache +0x38 | 확정 |
| +0x98 | MergeItem @ 016e4700 | Item cache/category | 확정 |
| response 전체 | UpdateHeroInfo @ 016e4ba4 | Hero/User 상태 | 확정 |
| +0xC0 | Merge<int,object> @ 017704a0 | cache +0x48 | 확정 |
| +0xC8 | MergeSections @ 016e55dc | cache +0x50 | 확정 |
| +0xD0 | Merge<int,object> @ 017704a0 | cache +0x58 | 확정 |
| +0xE8 | Merge<int,object> @ 017704a0 | cache +0x80 | 확정 |
| +0xB0 | Merge<long,object> @ 017708c4 | cache +0x88 | 확정 |
| +0xF0 | Merge<int,object> @ 017704a0 | cache +0x68 | 확정 |
| +0xF8 | Merge<int,object> @ 017704a0 | cache +0x70 | 확정 |
| +0x130 | 직접 DataCenter +0x100 저장 | 별도 상태 | 조건부 |
| +0x80 | 직접 DataCenter +0x108 저장 | 별도 상태 | 조건부 |
| +0x138 | 조건부 후속 처리 | set_AIStrategy 관련 | 조건부 |
| +0x148 | Merge 계열 | DataCenter +0xA0 | 확정 |

### Weapon 구분

OpInfo.Weapons (+0xA0) → MergeWeapon(상위) @ 016e414c → 개별 Weapon 처리 → MergeWeapon(하위) @ 016e5be4 로 구분한다. 두 주소를 동일 함수로 취급하지 않는다.

### ProccessRequestRes의 역할

Calls OUT에 Ali.Notify, Ali.Refresh_SysBtnConfig, DataCenter.set_EnergyNextTime, set_AIStrategy, set_ChatChannel, set_SupportCVTimes, UpdateHeroInfo, MergeItem, MergeEquip, MergeSections, MergeSectionSnapShot, MergeWeapon, Merge<int,object>, Merge<long,object>, Merge<object,object>가 함께 확인된다.

따라서 ProccessRequestRes는 단순 응답 전달이 아니라 Bootstrap response의 여러 state group을 DataCenter에 분배/병합하고 일부 파생 상태 및 Notify/UI 설정까지 갱신하는 중앙 처리 함수로 정적으로 확인된다.

### 다음 추적 목표

1. DataCenter +0x38/+0x40/+0x48/+0x50/+0x58/+0x68/+0x70/+0x80/+0x88/+0xA0의 getter/사용처 검색
2. 각 cache를 읽는 Main UI 호출자 연결
3. UpdateHeroInfo가 User/Heros를 어떻게 분리 처리하는지 확인
4. Merge<int,object> 각각이 Chapters/Teams/Quests/Shops/Charges 중 어느 cache를 받는지 함수 인자와 대조
5. MergeSectionSnapShot의 입력과 DataCenter +0x90 Section state 연결 확인

이후 Local Server Bootstrap 계약을 response field → merge 함수 → DataCenter property → Main UI 소비처 형태로 확정한다.

## 12. 2026-10-02 Cache → UI 소비처 재추적

### 12.1 Chapters cache는 +0x48로 연결

기존 Ghidra 기록에서 `DataCenter +0x48`은 다음 구조로 확인된다.

```text
DataCenter +0x48
  ↓
Dictionary<int, ProtoChapter>
  ↓
BattleMapMono.LayChapterItem @ 00e4f918
  ↓
ProtoChapter
  ↓
IsBoxReceived / Chapter UI
```

따라서 `ProccessRequestRes`의:

```text
OpInfo +0xC0 Chapters
  → Merge<int,object> @ 017704a0
  → DataCenter +0x48
  → Chapter UI
```

연결은 현재 정적 분석 기준으로 확정 수준을 높일 수 있다.

### 12.2 Section snapshot은 Chapter와 분리

`DataCenter.MergeSectionSnapShot @ 016e5908`은 `DataCenter +0x90`의 `Dictionary<int,int>` 상태를 갱신하고, 해당 상태는 `IsSectionClear`에서 사용된다.

따라서 현재 모델은:

```text
OpInfo +0xC8 Sections
  → MergeSections @ 016e55dc
  → Section collection cache (+0x50)

별도 Section snapshot
  → MergeSectionSnapShot @ 016e5908
  → DataCenter +0x90
  → IsSectionClear
```

로 분리한다.

`DataCenter +0x90`을 `ProtoChapter.BoxStatus`로 연결하지 않는다.

### 12.3 현재 cache 의미 확정 수준

| Response | Merge | DataCenter | UI/사용처 | 상태 |
|---|---|---|---|---|
| Items +0x98 | MergeItem | +0x78 category cache | WarehousePanelMono | **runtime+static 확정** |
| Weapons +0xA0 | MergeWeapon @ 016e414c | +0x40 | Weapon 계열 사용처 추가 확인 필요 | static 확정 |
| Equiments +0xA8 | MergeEquip @ 016e4348 | +0x38 | Equip 계열 사용처 추가 확인 필요 | static 확정 |
| Chapters +0xC0 | Merge<int,object> | +0x48 | BattleMap/Chapter UI | **static 연결 확정** |
| Sections +0xC8 | MergeSections | +0x50 | Section UI 추가 확인 필요 | static |
| Teams +0xD0 | Merge<int,object> | +0x58 | 사용처 추가 확인 필요 | static |
| Shops +0xF0 | Merge<int,object> | +0x68 | Shop UI 추가 확인 필요 | static |
| Charges +0xF8 | Merge<int,object> | +0x70 | 재화/Charge UI 추가 확인 필요 | static |
| Quests +0xE8 | Merge<int,object> | +0x80 | Quest UI 추가 확인 필요 | static |
| Mails +0xB0 | Merge<long,object> | +0x88 | Mail UI 추가 확인 필요 | static |
| Section snapshot | MergeSectionSnapShot | +0x90 | IsSectionClear | **static 연결 확정** |

### 12.4 다음 분석은 cache 이름 맞추기보다 Main 소비처 확인

현재 Local Server 목적상 모든 DataCenter property 이름을 복원할 필요는 없다.

다음 우선순위를 적용한다.

1. `+0x48` Chapters → Main/Chapter 진입까지 확인
2. `+0x40` Weapons / `+0x38` Equiments → 메인 Hero/Equip UI 소비 여부 확인
3. `+0x68/+0x70/+0x80/+0x88` → Shop/Charge/Quest/Mail의 실제 Main 초기화 여부 확인
4. `UpdateHeroInfo @ 016e4ba4`에서 User/Heros 분리 처리 확인
5. 그 결과를 Bootstrap Full Response 계약에 반영

현재까지는 **Items와 Chapters만 실제 UI 효과가 runtime에서 확인됐고**, 나머지는 Response→DataCenter 병합까지가 정적 확정이며 Main 필수 여부는 미확정으로 유지한다.
## 13. 2026-10-02 Main UI 소비처 추가 확인

### 13.1 Equipment 계열은 Main 진입과 직접 연결된 증거 확보

`HomePanelMono.Start @ 00f67adc`가 `DataCenter.get_EquipMax @ 016de7cc`, `get_NextEquipMax @ 016de648`, `get_CurrentEquipMax @ 016de53c` 계열과 연결된 Listing이 확인된다.

따라서 Bootstrap의 `Equiments (+0xA8) → MergeEquip → DataCenter +0x38` 상태는 단순 후속 메뉴용 데이터로만 볼 수 없다. Main 초기화 경로에서 Equipment 관련 DataCenter 상태가 참조된다.

다만 getter 내부에서 정확히 `+0x38`을 읽는 Assembly는 현재 별도 Listing 검색에서 확보되지 않았으므로, `+0x38` 자체와 각 getter의 1:1 대응은 다음 단계에서 직접 확인한다.

### 13.2 EquipMax는 Warehouse와도 연결

`WareHousePanelMono` 계열에서 `DataCenter.get_EquipMax @ 016de7cc` 호출이 확인된다.

즉 Equipment 상태는:

```text
Bootstrap Equiments
  → MergeEquip
  → DataCenter Equipment state
  ├─ HomePanelMono.Start
  └─ WareHousePanelMono 계열
```

로 소비되는 경로가 존재한다.

### 13.3 DataCenter singleton 접근 계층 확인

`Ali.get_dataManager @ 00e0277c`의 Calls IN에 `ProccessRequestRes`, `UpdateHeroInfo`, `MergeItem`, `MergeEquip`, `MergeWeapon`, `MergeSectionSnapShot`, `ShopNewPanelMono.ConfigShopContents` 등이 함께 존재한다.

이는 이 함수들이 동일 DataCenter singleton을 공유한다는 것을 뒷받침한다. 단, Calls IN 목록만으로 각 함수가 동일 cache offset을 직접 읽는다고 해석하지 않는다.

### 13.4 현재 우선순위 조정

현재까지 Main/UI 소비 근거가 가장 명확한 것은:

```text
Items      → Warehouse      [runtime + static]
Chapters   → Chapter UI     [static]
Equiments  → Home/Warehouse [static 소비자 존재]
```

다음은 `Weapons (+0x40)`와 `UpdateHeroInfo(User/Heros)`를 먼저 추적하고, 이후 Shop/Charge/Quest/Mail을 확인한다.

## 14. 2026-10-02 Weapons 소비처 추적 결과

### 14.1 Bootstrap → Weapon cache

DA.txt의 `ProccessRequestRes @ 016e203c`에서:

```text
OpInfo +0xA0 Weapons
  → MergeWeapon @ 016e414c
  → DataCenter cache +0x40
```

가 직접 확인된다.

`016e414c`는 `ProccessRequestRes`가 직접 호출하는 상위 병합 함수이며, 내부 개별 Weapon 처리 함수 `MergeWeapon @ 016e5be4`와 구분한다.

### 14.2 실제 UI 소비처

정적 Listing 검색에서 다음 Weapon 소비 경로가 확인됐다.

- `WeaponPanelMono$$Init @ 00f58380`
- `WeaponPanelMono$$RefreshWeaponInfoBoard @ 00f59c90`
- `HeroPartEquipMono$$RefreshWeapon @ 00f4214c`
- `HeroInfo$$get_Weapon @ 016ee62c`
- `HeroInfo$$get_WeaponInfomation @ 016ef3b0`
- `DataCenter$$WeaponSkillLevel @ 016e7d2c`

특히 `HomePanelMono$$Start @ 00f67adc`와 Weapon 관련 UI 함수들이 동일 UI/초기화 Listing 계층에서 확인되며, `WeaponPanelMono`는 실제 무기 표시/갱신 소비자다.

다만 현재 확보된 검색 결과만으로 `WeaponPanelMono`가 `DataCenter +0x40`을 직접 읽는 Assembly까지는 확인하지 못했다. 따라서 다음 수준으로 구분한다.

| 경로 | 상태 |
|---|---|
| OpInfo +0xA0 → MergeWeapon @ 016e414c | 확정 |
| MergeWeapon → DataCenter +0x40 | 확정 |
| WeaponPanelMono / HeroPartEquipMono / HeroInfo 계열이 Weapon 상태 소비 | 확정 |
| Weapon UI → DataCenter +0x40 직접 1:1 연결 | 추가 검증 필요 |

### 14.3 UpdateHeroInfo 추적 결과

`UpdateHeroInfo @ 016e4ba4`는 `ProccessRequestRes`에서 response 전체 객체를 전달받는 것이 Assembly로 확인된다.

현재 검색에서:
- `HeroInfo$$get_Weapon` / `get_WeaponInfomation`은 HeroInfo 객체의 무기 상태 소비를 보여준다.
- 그러나 `UpdateHeroInfo` 내부에서 `OpInfo +0x88 User`와 `+0x90 Heros`를 각각 어떤 offset으로 분리 저장하는지 직접 보여주는 개별 Listing은 아직 확보하지 못했다.

따라서 현재 계약에서는:

```text
OpInfo +0x88 User
OpInfo +0x90 Heros
        ↓
UpdateHeroInfo(response 전체)
        ↓
Hero/User state
```

까지만 확정하고 내부 분리 offset은 미확정으로 유지한다.

### 14.4 다음 추적

다음은 `UpdateHeroInfo` 내부를 직접 좁히기보다 실제 소비처 기준으로:

1. `HeroInfo$$get_WeaponInfomation` 호출자
2. `HeroInfo$$get_Weapon` 호출자
3. `HomePanelMono$$Start`에서 Hero/User 관련 getter
4. Runtime Bootstrap에서 `UpdateHeroInfo` 직후 실제 UI 변화

순으로 확인한다.

현재 Local Server 계약 우선순위는:

```text
Items       → runtime 확정
Chapters    → static UI 연결 확정
Equiments   → Home/Warehouse 소비자 확인
Weapons     → Weapon/Hero UI 소비자 확인
User/Heros  → UpdateHeroInfo 내부 분리 추적 중
```


## 15. 2026-10-02 UserInfo$$MergeVaryData 직접 추적

### 15.1 핵심 수정 — +0x70이 MergeVaryData 입력

DataCenter$$ProccessRequestRes @ 016e203c의 실제 Assembly를 재확인했다.

```text
016e2eb8  mov x28,x26
016e2ebc  ldr x0,[x28,#0x70]!
...
016e2f38  ldr x0,[x20,#0x28]
016e2f40  ldr x1,[x28]
016e2f44  mov x2,xzr
016e2f48  bl 0x00dd3030
```

따라서 정확한 호출은:

```text
OpInfo +0x70 DictI32
  ↓
UserInfo$$MergeVaryData @ 00dd3030
```

x1 = [x28]이고 x28 = OpInfo +0x70이므로 MergeVaryData의 두 번째 인자는 Dictionary<int,int> 계열이다.

즉 이전의 `OpInfo +0x88 User → MergeVaryData` 해석은 잘못이며 폐기한다.

### 15.2 MergeVaryData가 실제로 처리하는 key

UserInfo$$MergeVaryData @ 00dd3030 내부에서 다음 key를 검사하고, 없으면 기존 getter 값을 유지하고 있으면 setter로 반영한다.

| Key | UserInfo 상태 | 처리 |
|---:|---|---|
| -0xF7 (-247) | StigmataTimes | get → set |
| -0xF6 (-246) | MetaphysicsTimes | get → set |
| -0xF5 (-245) | Exp | get → set |
| -0xF4 (-244) | Level | get → set |
| -0xF1 (-241) | FCTimes | get → set |
| -0xF3 (-243) | SignInDays | get → set |
| -0xF2 (-242) | SignInRewardDay | get → set |
| -0xF0 (-240) | StepId | get → set |
| -0xEE (-238) | ExamTimes | get → set |
| -0xE2 (-226) | EquipMax | get → set |
| -0xE1 (-225) | ChargeTotalPerMonth | get → set |
| -0xE0 (-224) | Age | get → set |
| -0xDE (-222) | ChatChannel | get → set |

처음 -0xF8 (-248)도 별도 분기로 StigmataTimes 조회/처리를 시작하는 구조가 확인된다. 이 부분은 후속 Assembly 구간까지 추가 대조한다.

### 15.3 Main UI 연결도 확인

UserInfoPanelMono$$Start @ 00f7e92c는 직접 다음 UserInfo 값을 읽는다.

```text
UserInfo$$get_Id
UserInfo$$get_Name
UserInfo$$get_Level
UserInfo$$get_Exp
```

Level/Exp는 UI 텍스트 및 경험치 바 표시용으로 사용된다.

따라서 Bootstrap의 +0x70 DictI32는 단순 부가 dictionary가 아니라:

```text
OpInfo +0x70 DictI32
  ↓
UserInfo$$MergeVaryData
  ├─ Level
  ├─ Exp
  ├─ FCTimes
  ├─ SignInDays
  ├─ SignInRewardDay
  ├─ StepId
  ├─ EquipMax
  ├─ ChargeTotalPerMonth
  ├─ Age
  └─ ChatChannel ...
        ↓
UserInfo state
        ↓
UserInfoPanelMono / Main UI 소비
```

로 연결된다.

### 15.4 Local Server 계약에 반영할 점

+0x70 DictI32를 null/empty로 취급하면 UserInfo의 Level/Exp 등 초기 상태가 유지되지 않을 수 있다.

따라서 현재 Bootstrap 계약에서는:

- +0x70 DictI32의 key/value를 실제 응답 기준으로 수집
- +0x88 User / +0x90 Heros는 별도 UpdateHeroInfo 경로로 계속 추적
- UserInfo 값은 ProtoUser 필드와 DictI32 vary data를 섞어서 추정하지 않음

으로 분리한다.

### 15.5 다음 추적

1. +0x70 runtime hook에서 실제 key/value 목록 확보
2. ProtoUser → UpdateHeroInfo @ 016e4ba4 직접 field access 확인
3. HomePanelMono.Start에서 UserInfo/Charge/FCTimes 등 추가 소비처 확인
4. 실제 Bootstrap Response를 기준으로 Local Server DictI32 계약 작성


## 16. 2026-10-02 User / Heros 분리 경로 확정

### 16.1 +0x88 User는 UpdateHeroInfo가 아니라 UserInfo.ctor로 처리

ProccessRequestRes @ 016e203c의 실제 Listing에서 다음이 확인됐다.

```text
016e2580  ldr x21,[x26,#0x88]
016e2584  cbz x21,...
016e259c  mov x1,x21
016e25a0  mov x2,xzr
016e25a4  mov x22,x0
016e25a8  bl 0x00dd2f44
016e25ac  mov x0,x20
016e25b0  str x22,[x0,#0x28]!
```

여기서:

```text
OpInfo +0x88 User (ProtoUser)
  ↓
UserInfo$$.ctor @ 00dd2f44
  ↓
DataCenter +0x28
```

즉 User는 UpdateHeroInfo 경로가 아니라 ProccessRequestRes에서 직접 UserInfo 객체로 생성되어 DataCenter `+0x28`에 저장된다.

### 16.2 +0x70 DictI32는 같은 UserInfo 상태를 보정

앞서 확인한:

```text
OpInfo +0x70 DictI32
  ↓
UserInfo$$MergeVaryData @ 00dd3030
```

와 합치면 실제 구조는:

```text
OpInfo +0x88 User
  → UserInfo.ctor
  → DataCenter +0x28

OpInfo +0x70 DictI32
  → UserInfo.MergeVaryData
  → 기존 UserInfo 값 갱신
```

즉 `ProtoUser` 기본 정보와 `DictI32 vary data`가 **같은 UserInfo 객체를 서로 다른 단계에서 구성**한다.

### 16.3 +0x90 Heros는 UpdateHeroInfo에서 별도 처리

UpdateHeroInfo @ 016e4ba4에서는:

```text
016e5170  ldr x0,[x27,#0x90]
...
016e5198  ldr x0,[sp,#0x48]
016e519c  cbz x0,...
016e51a0  ldr x1,[sp,#0x40]
016e51a4  bl 0x016e5fd4
```

가 확인된다.

Calls OUT에도:

```text
HeroInfo$$InitHero @ 016e5fd4
HeroInfo$$FinalUpgradeHero @ 016e07d4
```

가 존재한다.

따라서:

```text
OpInfo +0x90 Heros
  ↓
DataCenter.UpdateHeroInfo
  ↓
Dictionary<int, ProtoHero> 순회
  ↓
HeroInfo$$InitHero
  ↓
HeroInfo state
```

로 User와 완전히 분리된 경로임이 정적 분석으로 확인됐다.

### 16.4 Bootstrap User/Hero 계약 현재 확정

```text
             Bootstrap OpInfo
                    │
          ┌─────────┴─────────┐
          │                   │
     +0x88 User          +0x90 Heros
          │                   │
   UserInfo$$.ctor       UpdateHeroInfo
          │                   │
   DataCenter +0x28      HeroInfo$$InitHero
          │                   │
   +0x70 DictI32          HeroInfo state
          │
   MergeVaryData
          │
   Level / Exp / EquipMax /
   FCTimes / SignIn / ...
```

이제 `User/Heros → UpdateHeroInfo`라는 이전의 묶음 표현은 폐기하고, 두 경로를 별도로 기록한다.

### 16.5 다음 추적

1. UserInfo.ctor @ 00dd2f44에서 ProtoUser field → UserInfo field 매핑 확인
2. 실제 runtime에서 +0x70 DictI32 key/value 확보
3. HeroInfo.InitHero @ 016e5fd4에서 ProtoHero → HeroInfo field 매핑 확인
4. 이후 HomePanelMain이 실제로 읽는 UserInfo/HeroInfo 필드만 계약에 우선 반영


## 17. 2026-10-02 HeroInfo.InitHero 호출 인자 및 후속 처리

현재 Git Listing에서 InitHero 자체의 별도 함수 블록은 분리되어 있지 않아, 호출부를 기준으로 확정 가능한 범위만 기록한다.

### 17.1 InitHero 호출 인자

FUN_00e5c00c에서 Dictionary 값을 꺼낸 뒤 다음 호출이 확인된다.

```text
00e5bda0  mov x20,x0              ; Dictionary<int,object>.get_Item 결과
...
00e5bdd0  bl 0x00e0277c          ; DataManager 획득
00e5bddf  ...
00e5bdf0  bl 0x0177142c          ; DataManager.TryGet<object>
...
00e5be18  mov x19,x0
00e5be1c  bl 0x016e0400          ; HeroInfo$$.ctor
00e5be20  mov x0,x19
00e5be24  mov x1,x20
00e5be28  mov x2,xzr
00e5be2c  bl 0x016e5fd4          ; HeroInfo$$InitHero
```

호출 규약상 x0=생성된 HeroInfo, x1=x20(앞에서 Dictionary에서 얻은 원본 객체), x2=null이다. 원본을 ProtoHero 계열로 추정할 수 있지만 현재 Listing만으로 타입명을 직접 확정하지 않고 원본 Hero 데이터 객체로 기록한다.

### 17.2 InitHero 이후 Hero 상태 가공

같은 처리 흐름에서 다음이 연속으로 존재한다.

```text
HeroInfo$$InitHero @ 016e5fd4
        ↓
HeroInfo$$FinalUpgradeHero @ 016e07d4
        ↓
HeroInfo$$UpdateAIStrategy @ 016f0b28
```

또 다른 흐름에서는 WeaponInfo$$.ctor, WeaponInfo$$Refresh, WeaponInfo$$get_Id가 함께 사용된다.

따라서 Bootstrap Hero 데이터는 단순 dictionary 보관이 아니라 원본 Hero 데이터 → HeroInfo 생성 → InitHero → FinalUpgradeHero → UpdateAIStrategy 후처리 흐름으로 기록한다.

### 17.3 현재 확정 / 미확정

확정:
- OpInfo +0x90 Heros → DataCenter.UpdateHeroInfo
- UpdateHeroInfo → HeroInfo.InitHero
- InitHero 호출 시 x0=HeroInfo, x2=null
- InitHero 후 FinalUpgradeHero, UpdateAIStrategy 처리 존재
- Hero 흐름에 WeaponInfo 생성/갱신 경로 존재

미확정:
- InitHero 내부의 ProtoHero 각 필드 → HeroInfo 필드 정확한 offset
- HeroInfo의 Level/Star/State/Fashion 직접 매핑
- Bootstrap에서 실제 Main 화면에 필요한 Hero 필드 최소 집합

### 17.4 다음 작업

다음은 HeroInfo getter/setter와 WeaponInfo 소비처를 기준으로 실제 Main/Hero UI가 읽는 Hero 필드를 역추적한다. InitHero 내부가 Git Listing에 직접 존재하지 않는 경우 runtime hook으로 InitHero 인자를 잡아 실제 객체 타입/필드 접근을 보완한다.


## 18. 2026-10-02 HeroInfo getter → Hero/HeroEquip UI 소비처 추적

### 18.1 Weapon 상태 소비 경로

Git Listing에서 다음 호출 관계를 확인했다.

```text
HeroInfo$$get_Weapon @ 016ee62c
  ← ReadyMono$$CheckHeroCurrentBreakType @ 00e62bc4
  ← ReadyMono$$RefreshMyNameStyle @ 00e615a4

HeroInfo$$get_WeaponInfomation @ 016ef3b0
  ← AliothExtensions$$Skill @ 00e12978
  ← HeroPartEquipMono$$RefreshWeapon @ 00f4214c
  ← ReadyMono / LineUp / Tips / Battle 계열
```

특히 `HeroPartEquipMono$$RefreshWeapon`은 `AliothExtensions$$Skill`을 통해 WeaponInformation을 사용하므로 Hero 장비 표시/스킬 계산에 직접 연결된다.

따라서:

```text
OpInfo +0xA0 Weapons
  → MergeWeapon @ 016e414c
  → DataCenter Weapon state (+0x40)
  → HeroInfo / Weapon UI 계열
       ├─ get_Weapon
       └─ get_WeaponInfomation
```

까지 연결된다.

단, `HeroInfo getter → DataCenter +0x40`의 직접 offset 연결은 아직 확정하지 않는다.

### 18.2 HeroInfo Level / Star / State 소비

다음 getter 호출자가 확인됐다.

| HeroInfo getter | 확인된 소비처 | 의미 |
|---|---|---|
| get_Level @ 016ea018 | ReadyMono, OrderHeroList 등 | Hero Level |
| get_Star @ 016dfad4 | ReadyMono 계열 / Hero 정렬 | Hero Star |
| get_State @ 016df754 | ReadyMono.GetTeamBack 계열 | 팀/영웅 상태 판정 |
| get_FashionId @ 016ee9d4 | AliothExtensions.GetFashionData | Hero 외형/Fashion 선택 |

`ReadyMono$$RefreshMyNameStyle`에서도 Level과 Star가 사용되며, `ReadyMono$$SetTeamMembers` → `CheckHeroCurrentBreakType` → `HeroInfo.get_Weapon` 경로가 확인된다.

### 18.3 Fashion 경로

`AliothExtensions$$GetFashionData @ 00e12714`는 `HeroInfo.get_FashionId @ 016ee9d4`를 호출한다.

호출자는:

- HomePanelMono.ChangePicture
- HeroDetailPanelMono.ShowDetail
- CallPanelMono.ShowActor
- HeroBreakMono.TransHeroStarUp
- RoleLvUpPanelMono.Init
- BattleCenter.CheckRoleSkillRes

등으로 확인된다.

따라서 HeroInfo의 FashionId는 단순 데이터 보관이 아니라 Hero 표시/상세/호출/성장 UI에서 소비된다.

### 18.4 현재 Hero 계약 우선 필드

현재 정적 근거로 Bootstrap Hero 상태와 연결해 우선 추적할 getter는:

```text
HeroInfo
 ├─ Level
 ├─ Star
 ├─ State
 ├─ FashionId
 ├─ Weapon
 └─ WeaponInfomation
```

이다.

주의: 위 getter가 `ProtoHero`의 어느 원본 field/offset에서 직접 만들어지는지는 `HeroInfo.InitHero @ 016e5fd4` 본문이 Git Listing에 별도 블록으로 제공되지 않아 아직 미확정이다.

### 18.5 Local Server 계약 반영

현재 Hero 관련 응답은 최소화하지 않고:

```text
OpInfo +0x90 Heros
  → UpdateHeroInfo
  → HeroInfo.InitHero
  → HeroInfo state
      ├─ Level
      ├─ Star
      ├─ State
      ├─ FashionId
      └─ Weapon 관련 상태
  → Hero/HeroEquip/Ready UI
```

형태로 유지한다.

다음은 `HeroInfo.InitHero` 호출 직후 runtime에서 getter 값을 잡아 실제 Bootstrap Hero 필드와 대응시키고, 그 결과를 Local Server 계약에 반영한다.


## 19. 2026-10-02 Runtime Hero 필드 대응 추적 준비

`justice_hook.js v4.22`에 다음 runtime 관찰점을 추가했다.

HeroInfo.InitHero
  ├─ source 객체 class/field/offset/type
  └─ InitHero 후 HeroInfo field/offset/type

HeroInfo getter
  ├─ Level
  ├─ Star
  ├─ State
  ├─ FashionId
  ├─ Weapon
  └─ WeaponInfomation

목적은 정적 Listing에서 확인한:

OpInfo +0x90 Heros
 → UpdateHeroInfo
 → HeroInfo.InitHero
 → HeroInfo state
 → Hero/HeroEquip/Ready UI

를 실제 runtime 객체 값으로 대조하는 것이다.

현재는 실제 기기 실행 로그가 아직 없으므로 ProtoHero 원본 field와 HeroInfo field의 1:1 대응은 미확정으로 유지한다.

다음 실행에서 [HERO_INIT] 및 [HERO_GET] 로그를 확보하면:
1. Bootstrap의 실제 Hero 객체 class 확인
2. source field offset/type 확인
3. InitHero 결과 HeroInfo field 확인
4. Level/Star/State/FashionId/Weapon 값을 대응
5. Local Server Bootstrap Hero 계약에 필요한 실제 field만 확정
한다.

## 20. 2026-10-02 Runtime Hero 메뉴 / 무기 변경 확인

최신 Git 로그를 다시 확인했다. 이번 실행에서는 실제 Hero 메뉴 진입과 무기 변경/장착 동작을 수행했으며, 현재 로그에서 확인 가능한 범위와 미확정 범위를 분리한다.

### 20.1 ProtoHero 원본 필드가 실제 runtime에서 확인됨

HeroInfo.InitHero(Alioth.S1.Common.ProtoHero) hook이 실제로 동작했고 source 객체가 ProtoHero임이 확인됐다.

대표 객체:
- ProtoHero @ 0x75d23f50e0
- Id = 10000003
- Level = 30
- Exp = 3570
- Star = 2
- Weapon = 40000300
- Armor = "D"
- Belt = "B"
- Emblem = "H"
- Talent = 0
- Suit = 0
- FashionId = 49000300
- Strategy = 0
- Stigmata1~6 = 0

따라서 ProtoHero.Weapon은 현재 영웅이 참조하는 무기 ID를 담는 필드로 볼 근거가 충분하다. 다만 40000300이 실제 ProtoWeapon.Id와 1:1로 일치하는지는 아직 별도 대조하지 않는다.

### 20.2 Hero UI에서 확인된 소비 경로

OpInfo +0x90 Heros
→ DataCenter.UpdateHeroInfo
→ HeroInfo.InitHero(ProtoHero)
→ HeroInfo Level / Star / State / FashionId / Weapon / WeaponInfomation
→ Hero / HeroEquip / Ready / Weapon UI

runtime에서 HeroInfo.get_Weapon, get_WeaponInfomation, get_Level, get_Star 호출이 실제 발생한 것도 확인됐다.

### 20.3 무기 변경 동작과 네트워크 요청의 구분

이번 로그에는 Hero/Weapon UI 접근과 KCP 요청이 함께 존재한다. 그러나 현재 최종 로그만으로는 무기 변경 동작 직후의 특정 KCP 요청을 무기 장착 요청이라고 1:1 확정할 수 없다.

확인된 KCP 요청 예:
- OpCode=19
- OpCode=22

두 응답은 현재 로그에서 User/Items/Heros/Chapters가 null인 응답으로 확인되며, Hero 무기 장착 계약으로 확정하지 않는다.

현재 결론:
- Hero 메뉴 진입: 확인
- ProtoHero → HeroInfo runtime 변환: 확인
- Weapon 필드의 장착 ID 후보: 확인
- Weapon UI getter 소비: 확인
- 무기 변경에 사용된 정확한 Request OpCode/요청 payload: 미확정
- 변경 후 ProtoHero.Weapon 값이 실제로 변경됐는지: 현재 로그만으로는 미확정

### 20.4 정적 분석에서 확인된 무기 관련 UI/요청 진입점

- HeroPartEquipMono.ClickEquip @ 00f4513c
- HeroPartEquipMono.RefreshWeapon @ 00f4214c
- WeaponPanelMono.DemandByID @ 00f5d484
- WeaponPanelMono.Init @ 00f58380
- WeaponPanelMono.RefreshWeaponInfoBoard @ 00f59c90
- HeroInfo.set_WeaponInfomation @ 016e0750

특히 HeroPartEquipMono.ClickEquip은 실제 장착 동작을 좁혀갈 수 있는 유력한 UI 진입점이므로, 이후 필요할 때 이 함수에서 NetworkCenter/KCPTube 호출까지 역추적한다.

### 20.5 현재 분석 범위 판단

지금은 ProtoHero 내부를 더 깊게 파지 않는다.

현재 Local Server 목표에서는:
Bootstrap 전체 응답
→ Main 진입
→ Hero/Weapon UI가 기존 상태를 정상 소비

를 먼저 검증한다.

따라서 ProtoHero의 Level/Weapon/Fashion/Stigmata 등의 상세 필드 구조는 확인된 데이터 모델로 기록만 유지하고, 실제 서버 계약에 필요한 경우에만 다시 상세 추적한다.

### 20.6 다음 작업

1. Main 화면에서 실제로 읽는 User/Charge/Chapter/Weapon/Equipment 소비처를 계속 확인
2. Local Server Bootstrap Full Response 계약을 구현 가능한 형태로 정리
3. KCP Response serializer/OpInfo 생성 구조로 연결
4. Hero 무기 장착 요청은 필요 시 HeroPartEquipMono.ClickEquip부터 별도 추적

현재 원칙은 Hero 내부 상세 분석보다 Bootstrap → Main 정상 진입 검증을 우선한다.

## 21. Main 화면 소비처 1차 정리

Bootstrap 이후 Main에서 실제로 소비되는 데이터 중 우선순위가 높은 경로를 다시 정리했다.

### 21.1 EquipMax 계열

HomePanelMono.Start @ 00f67adc가 다음 DataCenter getter 계열과 연결된다.

- DataCenter.get_CurrentEquipMax @ 016de53c
- DataCenter.get_NextEquipMax @ 016de648
- DataCenter.get_EquipMax @ 016de7cc

이 getter들은 ListExtensions.Last를 통해 Home 초기화 계층에서 사용된다.

또한 UserInfo.MergeVaryData @ 00dd3030의 -0xE2 key가 EquipMax로 확인되어 있다.

따라서 EquipMax는:
OpInfo +0x70 DictI32 → UserInfo.MergeVaryData → EquipMax → Home UI
라는 연결이 이미 확보된 상태다.

### 21.2 Energy 계열

Bootstrap ProccessRequestRes에는 set_EnergyNextTime @ 016ded44가 직접 존재한다.

정적 Listing에서도 DataCenter.get_EnergyNextTime @ 016decdc가 GUI update 계층에서 사용된다.

runtime에서는 UserInfo.get_Energy가 실제 호출되었고 현재 테스트에서 Energy=134가 관찰됐다.

따라서 Energy는 Bootstrap 직후 Main 상태를 구성하는 실제 소비 데이터로 분류한다.

### 21.3 Home UI의 추가 소비점

다음 Main 소비 함수들이 확인된다.

- HomePanelMono.RefreshUIBanner @ 00f6ca94
- HomePanelMono.RefreshWareHouse_Supply @ 00f6a2ec
- HomePanelMono.RefreshPoint_TaoFA @ 00f69924
- HomePanelMono.RefreshWorldCup @ 00f6c094

현재는 각 함수 내부를 전부 파지 않고, Bootstrap 데이터가 이미 존재하는 상태에서 Main이 어떤 값을 요구하는지 확인하는 용도로만 등록한다.

### 21.4 Main Bootstrap 우선 데이터

현재까지의 증거를 기준으로 Local Server의 최초 구현 검증 대상은 다음으로 좁힌다.

1. UserInfo
   - Id / Name / Level / Exp
   - Energy
   - EquipMax
2. Hero
   - Hero dictionary
   - 최소한 Main/초기 UI가 참조하는 Hero 상태
3. Item
   - Bootstrap Items dictionary
4. Weapon
   - Bootstrap Weapons dictionary
   - Hero.Weapon과 연결될 가능성이 있는 데이터
5. Equipment
   - Bootstrap Equiments dictionary
6. Chapter / Section
   - Main/메뉴 진입에 필요한 최소 collection
7. Charges / Activities 등
   - 실제 Main 소비 확인 후 필요 필드만 유지

현재는 Fashions, Quests, Shops, Friends, Ranks 등의 상세 구조를 먼저 구현 대상으로 확장하지 않는다.

### 21.5 현재 단계 결론

Main 정상 진입에 필요한 것은 모든 Proto 구조를 완전히 복원하는 것이 아니라, Bootstrap OpCode=2에서 실제 Main이 읽는 상태를 먼저 재현하는 것이다.

따라서 다음 작업은 DataCenter getter별로 실제 저장 위치와 Main 호출자를 연결하고, 그 결과를 Local Server response contract의 필수/선택 필드로 분리하는 것이다.


## 22. 2026-10-02 Main 소비 경로 후속 확인 — EquipMax 저장 위치 확정

### 22.1 UserInfo.EquipMax 실제 저장 offset 확인

Git Listing의 `UserInfo$$get_EquipMax @ 00dd27d0` 본문에서:

```text
00dd2838  ldr w0,[x19, #0x58]
00dd2844  ret
```

가 확인된다.

따라서:

```text
UserInfo + 0x58 = EquipMax
```

로 확정한다.

또한 `UserInfo$$set_EquipMax @ 00dd2848`가 존재하고 `UserInfo$$MergeVaryData @ 00dd3030`에서 호출되므로:

```text
OpInfo +0x70 DictI32
  → UserInfo.MergeVaryData
  → UserInfo +0x58 EquipMax
  → DataCenter.get_EquipMax 계열
  → HomePanelMono.Start
```

의 저장/소비 연결이 확보됐다.

### 22.2 Main Bootstrap 계약에서 EquipMax 위치

현재는 ProtoUser 내부 offset을 억지로 추정하지 않는다.

Local Server가 재현해야 하는 의미 단위는:

```text
DictI32 key -0xE2
    ↓
UserInfo.EquipMax
    ↓
HomePanelMono.Start
```

이며 runtime에서 실제 값까지 확보하면 response fixture에 반영한다.

### 22.3 다음 추적 대상

다음은 동일한 방식으로 Main 소비값을 하나씩 확정한다.

1. `UserInfo.Id / Name / Level / Exp` 실제 저장 offset
2. `UserInfo.Energy` 저장/갱신 경로
3. `DataCenter.get_EquipMax / get_CurrentEquipMax / get_NextEquipMax`의 반환원 연결
4. HomePanelMono.Start가 EquipMax 외에 직접 읽는 DataCenter/UserInfo getter
5. 그 결과로 Bootstrap 필수/선택 필드 최종 분리

현재까지는 EquipMax를 **Main 필수 후보 → 저장 offset까지 확정** 상태로 승격한다.


## 23. 2026-10-02 UserInfo Main 소비값 저장 위치 추가 확정

### 23.1 UserInfo 직접 저장 필드

Git Listing 기준 getter의 실제 fallback 저장 offset:

| 값 | getter | 저장 위치 | Main 관련 |
|---|---|---:|---|
| Id | `00dd1884` | `UserInfo +0x10` | UserInfoPanel |
| Name | `00dd1988` | `UserInfo +0x18` | UserInfoPanel |
| Level | `00dd1ba0` | `UserInfo +0x28` | Main/UI 다수 |
| Exp | `00dd1ca4` | `UserInfo +0x2C` | UserInfoPanel |
| EquipMax | `00dd27d0` | `UserInfo +0x58` | HomePanel |
| Energy | `00dd2ce4` | 직접 필드가 아니라 `DataCenter.GetXCount` 경로 | Main/전투 UI |

Id/Name/Level/Exp/EquipMax는 모두 getter의 직접 fallback에서 저장 offset을 확인했다.

### 23.2 Energy는 별도 취급

`UserInfo.get_Energy @ 00dd2ce4`는 단순 `UserInfo + offset` 반환이 아니다.

현재 확인된 경로:

```text
UserInfo.get_Energy
  → DataCenter.GetXCount
  → key = 0x29020c3 (0x20c3 + 0x290 << 16)
```

따라서 Local Server Bootstrap에서 Energy를 `UserInfo` 고정 필드로 넣는 것으로 모델링하지 않는다.

### 23.3 Main Bootstrap 최소 데이터 후보 갱신

현재 직접적인 Main/UI 소비 근거가 확보된 User 영역:

```text
User
 ├─ Id       (+0x10)
 ├─ Name     (+0x18)
 ├─ Level    (+0x28)
 ├─ Exp      (+0x2C)
 └─ EquipMax (+0x58)

Energy
 └─ DataCenter.GetXCount(0x029020C3) 계열
```

### 23.4 다음 추적

다음은 `DataCenter.GetXCount(0x029020C3)`의 실제 데이터 저장/병합 경로를 추적한다.

동시에 `HomePanelMono.Start @ 00f67adc`의 직접 getter 호출 목록을 확정해, 위 User 값 중 실제 Bootstrap 직후 필요한 값과 단순 다른 화면 소비값을 분리한다.


## 24. 2026-10-02 Main 재화 3종의 ItemRecord / GetXCount 연결

UserInfo getter Assembly와 Unity ItemRecord 분석을 대조해 Main 재화 ID를 정리했다.

| 재화 | UserInfo getter | GetXCount itemId | 10진수 ItemRecord ID |
|---|---|---:|---:|
| Coins | `get_Coins @ 00dd2d8c` | `0x029020C1` | `43000001` |
| Crystals | `get_Crystals @ 00dd2e34` | `0x029020C2` | `43000002` |
| Energy | `get_Energy @ 00dd2ce4` | `0x029020C3` | `43000003` |

세 getter 모두 `DataCenter.GetXCount(itemId, 0, 0)`를 호출한다. 따라서 Coins도 UserInfo의 고정 필드가 아니라 Item 상태를 조회하는 값으로 취급한다.

Git의 `09_record_samples.json`에서 세 ID 모두 `ItemRecord.json` Record이며, 아이콘은 각 ID에 대응하는 `item_4300000X`다. SysconfRecord의 개인 정보 재화 표시 설정에도 세 ID가 포함된다.

`DataCenter.MergeItem @ 016e4700`와 `GetXCount @ 016defb0`는 모두 `BaseData +0x24`의 type을 기준으로 ItemType bucket을 선택한다. 현재 Listing에서 확인한 분기는 type `0x1F → bucket 2`, `0x22 → bucket 0`, `0x41 → bucket 1`이다.

단, Record sample의 `baseDataType=0`과 runtime `BaseData.type`의 직접 매핑, 그리고 각 재화 ID의 실제 bucket은 아직 runtime에서 확인하지 않았다. 이 둘을 동일하다고 추정하지 않는다.

따라서 Main Bootstrap fixture에서는 세 재화를 `UserInfo` 내부 숫자 필드로 별도 구성하지 않고, `OpInfo.Items → MergeItem → ItemType bucket → GetXCount` 경로로 구성한다. 실제 Bucket/Count는 다음 runtime 로그로 확정한다.


## 21. 2026-10-02 최신 단일 Frida 로그 반영 및 Main 범위 재정렬

입력 로그:
`research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`
사용자가 기존 로그를 누적하지 않고 이번 실행 최종본만 저장한 파일이다. 이 파일을 기준으로 분석하며 과거 로그를 섞지 않는다.

### 21.1 Bootstrap OpCode 2 runtime 확인

이번 로그의 최초 Bootstrap 응답:

- `OpCode=2`, `ReturnCode=0`
- `User@+0x88 = ProtoUser`
  - Id = 871053
  - Level = 53
  - Exp = 1100
- `Items@+0x98 = Dictionary`, count = 98
- `Heros@+0x90 = Dictionary` non-null
- `Chapters@+0xC0 = Dictionary`, count = 61
- Items → MergeItem 진입 및 정상 종료 확인
- HeroInfo.InitHero가 여러 ProtoHero 원본에 대해 실행됨

이후 발생한 OpCode 19 및 OpCode 22 응답은 User/Items/Heros/Chapters가 null이다. 따라서 이 응답들을 Bootstrap 전체 데이터로 취급하지 않는다.

### 21.2 Main 표시값 runtime 확인

- UserInfo Level = 53
- UserInfo Exp = 1100
- Currency:
  - Energy = 134
  - Coins = 306095
  - Crystals = 2700
- Currency BaseData 3종 모두 발견, runtime type = 0x22
- HeroInfo getter runtime 호출 확인:
  - Level, Star, State, FashionId
  - WeaponInfomation
- HeroInfo.InitHero의 source class = ProtoHero 확인

주의: 이 로그는 해당 getter가 호출된 사실을 확인하지만, 모든 Main 위젯의 데이터 의존성을 완성한 것은 아니다. 특히 HeroInfo getter가 다수 Hero 객체에 대해 호출된 결과이므로 개별 Hero와 화면의 대표 Hero 선택 관계는 별도 확인이 필요하다.

### 21.3 Main 데이터 계약 완료도 — 미완료

| 데이터 영역 | 현재 상태 | 남은 확인 |
|---|---|---|
| User 기본정보 | Bootstrap runtime 확인 | Main에서 실제 표시되는 필드 전체 |
| User vary data (+0x70) | MergeVaryData 정적 경로 확인 | 이번 Bootstrap의 실제 key/value와 소비 UI |
| Items | count 98, MergeItem runtime 확인 | Main 상단/배너/각 위젯에서 참조하는 항목 |
| Coins/Crystals/Energy | 실제 값과 GetXCount 경로 확인 | 표시 외 별도 Main 소비처가 있는지 |
| Heros | Dictionary 및 InitHero runtime 확인 | Main 대표 Hero 선택 및 필요한 필드 최소 집합 |
| Weapons | MergeWeapon 및 Weapon UI 소비처 정적 확인 | Main 진입 필수 여부/실제 데이터 참조 |
| Equiments | MergeEquip 및 Home/Warehouse 소비처 정적 확인 | Main 진입 필수 여부/필요 레코드 범위 |
| Chapters | count 61 및 Chapter UI 정적 연결 | Main 첫 화면에서 실제 필요한 subset |
| Sections | MergeSections 및 IsSectionClear 연결 확인 | Main 초기 로딩에서 필요한지 |
| Teams | 병합 경로 정적 확인 | Main 표시/초기화 소비 여부 |
| Quests | 병합 경로 정적 확인 | Main 배지/알림/퀘스트 UI 소비 여부 |
| Shops/Charges | 병합 경로 정적 확인 | Main 상점/충전 UI 소비 여부 |
| Mails/Friends/Activities/기타 | 일부 필드 병합 구조 확인 | Main 진입 필수 여부와 UI 소비 여부 |

### 21.4 작업 범위 재설정

전투 씬 내부 동작, 로컬 전투 계산/전투 데이터는 현재 Main Bootstrap 목표 범위에서 제외한다. 던전 입장 OpCode 0x16은 서버 요청/응답이 존재한다는 사실만 참고 기록으로 유지하고, 전투 씬 후속 분석은 진행하지 않는다.

이후 우선순위:
1. Main 화면 최초 표시 시점의 UI 컴포넌트별 DataCenter/UserInfo/HeroInfo getter 사용 목록 작성
2. Main 상단 재화/프로필/대표 Hero/배너/메뉴 배지의 실제 소비 필드 확정
3. 각 필드가 Bootstrap OpCode 2에 포함되는지 확인
4. Bootstrap에 없는 데이터가 별도 OpCode 요청으로 채워지는지 확인
5. Local Server가 Main 첫 화면을 표시하는 데 필요한 최소 응답 계약과, 메뉴 진입 시 추가로 필요한 응답 계약을 분리

완료 기준은 모든 서버 데이터 필드를 복원하는 것이 아니라, Main 첫 화면이 정상 표시되는 데 필요한 데이터와 타입/구조/초기화 순서를 식별하는 것이다.


## 22. 2026-10-02 v4.24 최종 단일 로그 재검토 — Main 데이터 조사로 복귀

사용자가 새로 등록한 `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`를 처음부터 다시 확인했다. 이전 로그를 누적해 해석하지 않는다.

### 22.1 이번 실행의 Bootstrap 실측

- Frida script: v4.24, 54 hooks installed
- Bootstrap Request: OpCode 2, SerialNumber 139954759
- Request가 KCPTube.Send에서 ret=1로 수락됨
- Response: 같은 SerialNumber 139954759, OpCode 2, ReturnCode 0
- OpInfo response envelope에서 45개 필드의 이름/타입/offset이 기록됨
- 주요 non-null 데이터:
  - DictI32 (+0x70)
  - User (+0x88)
  - Heros (+0x90)
  - Items (+0x98)
  - Weapons (+0xA0)
  - Equiments (+0xA8)
  - Chapters (+0xC0)
  - Sections (+0xC8)
  - Teams (+0xD0)
  - Fashions (+0xE0)
  - Quests (+0xE8)
  - Charges (+0xF8)
  - Activities (+0x120)
  - AIStrategy (+0x138)
- Mails, ViewItems, Exam, Rival, Msgs, BattleReport 등은 이번 응답에서 null 또는 비어 있는 값으로 관측됐다. null이 영구적으로 불필요하다는 뜻은 아니다.

### 22.2 이번 실행에서 확인된 Main 표시 관련 데이터

- User: Id=871053, Level=53, Exp=1100
- Items Dictionary count=98, MergeItem 실행 확인
- Chapters Dictionary count=61
- HeroInfo.InitHero가 ProtoHero 원본을 받아 여러 HeroInfo를 초기화
- HeroInfo getter runtime 호출: Level, Star, State, FashionId, WeaponInfomation
- Currency runtime 값: Energy=134, Coins=306095, Crystals=2700
- 세 재화의 BaseData.type은 모두 0x22

이것은 Bootstrap 데이터가 실제 Client 상태로 병합된 사실과 일부 getter 사용을 증명한다. 다만 모든 Main UI 위젯이 요구하는 필드 전체를 열거한 것은 아니다.

### 22.3 던전 진입 로그는 Main 범위에서 제외

같은 실행에서:
- ReadyMono.ClickEnterBattle 진입
- CreateBattle(20000000, 21000010)
- KCP OpCode=22 송신 수락
- 응답 OpCode=22, ReturnCode=0
- GoToBattleMono.CreateBattleBack 진입

여기까지는 입장 Request/Response 경계 확인에 해당한다. 전투 씬 내부 동작과 전투 데이터는 사용자의 범위 결정에 따라 추가 분석하지 않는다. 기존 Dungeon 보고서는 요청/응답 참고 기록으로 유지한다.

### 22.4 Main 데이터 완료도 재판정

**아직 완료되지 않았다.** 현재까지 완성된 것은 Bootstrap의 공통 Response envelope와 주요 데이터의 병합 경로이며, Main 첫 화면의 모든 소비 필드/데이터 유형/초기화 순서는 미완료다.

| 영역 | 현재 증거 | 완료 여부 |
|---|---|---|
| OpInfo envelope | 45 fields의 이름/타입/offset 실측 | 구조 확인 |
| User 기본 프로필 | Id/Level/Exp runtime | 일부 확인 |
| 재화 | Coins/Crystals/Energy 값 및 Item 경로 | 핵심 3종 확인 |
| 대표 Hero | ProtoHero → HeroInfo 및 일부 getter | 선택 기준/대표 Hero 연결 미완료 |
| 무기/장비 | Bootstrap merge 및 별도 UI 소비 정적 경로 | Main 필수 데이터 범위 미완료 |
| Chapter/Section | 61 Chapters runtime, Sections dictionary 존재 | 첫 화면 노출 subset 및 표시 의존성 미완료 |
| 배너/이벤트 | HomePanel 소비 함수 진입점 일부 확인 | 필요한 데이터와 배지/노출 조건 미완료 |
| 메뉴 배지/알림 | Quest/Activity 등의 응답 필드 존재 | 실제 UI 소비와 필수성 미완료 |
| Teams/Quests/Shops/Charges/Fashions/Activities | 응답 타입 및 merge 경로 | Main 소비 필드/필수성 미완료 |
| AssetBundle | Main UI 리소스 URL 일부 관측 | 화면 표시용 리소스 의존성 목록 미완료 |

### 22.5 분석 범위 고정

다음부터는 전투 진입을 따라가지 않는다. 목표를 다음과 같이 고정한다.

```
Login 완료
 → Bootstrap OpCode 2
 → DataCenter/UserInfo/HeroInfo 상태 생성
 → Main 최초 화면(HomePanel + 상단 UserInfo)
 → 화면별 getter/데이터 소비
 → 배너/메뉴 배지/표시 조건
 → Main 첫 화면 최소 Bootstrap contract
```

조사 종료 기준:
- 첫 화면에서 실제 표시되는 컴포넌트 목록
- 각 컴포넌트가 읽는 getter/property
- getter가 읽는 저장 객체 및 필드/자료형
- Bootstrap OpInfo field와 DataCenter merge/cache 경로
- Bootstrap에 포함되지 않으면 추가 Request가 필요한지
- 필수/선택/화면 진입 후 lazy-load 항목 분리

이 기준을 충족하기 전까지 Main Bootstrap 데이터 분석을 완료 처리하지 않는다.


## 23. 2026-10-02 Main 상단 프로필 / 재화 UI 소비 정적 확인

대상 Listing: `research/Ghidra_Listing_txt/US.txt`

### 23.1 UserInfoPanelMono.Start @ 00f7e92c

Main 상단 프로필 패널 초기화 경로에서 다음 UserInfo getter 호출이 확인된다.

| Getter | 데이터 | UI 소비 |
|---|---|---|
| `UserInfo.get_Id @ 00dd1884` | 사용자 ID | `lbl_userId` |
| `UserInfo.get_Name @ 00dd1988` | 닉네임 | `lbl_nickName` |
| `UserInfo.get_Level @ 00dd1ba0` | 플레이어 레벨 | `lbl_lv`, 레벨 표시 |
| `UserInfo.get_Exp @ 00dd1ca4` | 플레이어 경험치 | `lbl_userexpshow`, `spr_expbar.fillAmount` |
| `DataCenter.get_HeadData @ 016e80a4` | 프로필 머리/초상 데이터 | `ShowHeadPanel` 경로 |

추가로 레벨별 경험치 테이블을 위한 `BaseMono.GetLvExpdata` 호출이 존재한다. 따라서 EXP 숫자만이 아니라 현재 Level에 대응하는 필요 EXP/진행률 계산이 UI 표시 계약에 포함된다. 테이블 값은 정적 Master Data이며 플레이어 상태와 분리한다.

### 23.2 UserInfoPanelMono.RefreshTopInfos @ 00f7f914

- Calls OUT: `UserInfoPanelMono.ShowCoin @ 00f7e524`
- 상단 재화 표시를 별도 ShowCoin 경로에 위임한다.

### 23.3 UserInfoPanelMono.ShowCoin @ 00f7e524

Calls OUT에서 확인:
- `DataCenter.GetXCount @ 016defb0`
- `Ali.GetBaseData @ 00e035d4`
- `BaseData.get_icon @ 00df3224`
- `BaseData.get_NameByQualityWord @ 00df35ac`
- `CoinitemNode.get_lbl_item_count`
- `CoinitemNode.get_spr_item_icon`
- `CoinitemNode.get_lbl_item_name`
- `Ali.GetExcelData<object> @ 01736d60`
- `BaseData.SplitToInt32ListError @ 00df4238`

따라서 상단 재화 UI는 단순 숫자 3개 고정 출력이 아니라, UI에 구성된 재화 ID 목록을 순회하면서 다음을 조합하는 구조다.

```
재화 ID 목록
 → GetXCount(itemId)
 → GetBaseData(itemId)
 → Count / Icon / Name
 → CoinitemNode UI
```

현재 runtime에서 Coins/Crystals/Energy 3종은 확인됐지만, ShowCoin이 사용하는 전체 ID 목록과 각 항목의 표시 여부는 아직 추출하지 않았다. 상단 재화 contract의 완성 조건은 이 ID 목록과 UI 순서를 확인하는 것이다.

### 23.4 이번 정적 확인으로 확정된 Main 프로필 데이터 최소 집합

- User.Id
- User.Name
- User.Level
- User.Exp
- HeadData
- Level별 필요 EXP 테이블 참조
- 상단 재화 목록의 ItemId
- 각 ItemId에 대한 GetXCount 결과
- 각 ItemId의 BaseData 이름/아이콘 참조

단, HeadData가 Bootstrap User field 중 어느 필드에서 만들어지는지, 상단 재화 목록이 어떤 설정/테이블에서 만들어지는지, 이 패널의 모든 필드가 첫 Main 화면 진입 때 반드시 필요한지는 아직 별도 확인한다.

### 23.5 다음 Main 추적 우선순위

1. `ShowCoin`의 재화 ID 목록 생성부와 순회 항목을 확인해 Main 상단 재화 목록 전체를 확정한다.
2. `HomePanelMono.Start` 및 `RefreshUIBanner`의 실제 getter/Record 참조를 정리한다.
3. Main 첫 화면에 노출되는 배너/메뉴/알림 배지의 getter와 Quest/Activity/Shop/Charge 데이터 연결을 확인한다.
4. 대표 Hero 표시 경로가 별도 Home 소비처인지 확인하고, 모든 Hero의 전체 속성이 아닌 화면 표시 필드만 계약에 반영한다.
5. 각 데이터 항목을 `Bootstrap 필수`, `Main 화면 선택`, `메뉴 진입 시 추가 요청`, `정적 Master Data/Asset`로 분류한다.


## 24. 2026-10-02 Main 최초 화면 소비처 추가 분석

기준 Listing:
- `research/Ghidra_Listing_txt/US.txt`
- `research/Ghidra_Listing_txt/HO.txt`
- 최신 단일 로그: `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`

### 24.1 상단 재화: 목록 기반 동적 생성

`UserInfoPanelMono.ShowCoin @ 00f7e524` 본문에서 다음 순서를 확인했다.

1. `Ali.GetExcelData<object>` 호출
2. 반환 Record의 `+0x80` 값을 `BaseData.SplitToInt32ListError`로 분리
3. 결과 `List<int>`를 순회
4. 각 ID마다 `Ali.GetBaseData(itemId)`
5. `BaseData.icon`, `BaseData.NameByQualityWord`로 아이콘/이름 구성
6. `DataCenter.GetXCount(itemId)`로 수량 표시

따라서 상단 재화는 Coins/Crystals/Energy 세 항목으로 하드코딩된 구조가 아니다. **정적 Excel 설정이 재화 ID 목록을 제공하고, Bootstrap 이후 DataCenter의 실제 보유량을 조회해 UI를 만든다.**

현재 Ghidra Listing에서 GetExcelData 호출의 key 상수는 확인했지만, 해당 상수에 대응하는 Excel Record 명칭 및 전체 ID 목록은 아직 원본 데이터/런타임으로 대조하지 않았다. 그러므로 세 ID 외 추가 항목을 추정하지 않는다.

자료형:
- 설정 목록: Excel Record 내부 문자열/목록 → `List<int>`
- ID: `int`
- 보유량: `GetXCount` 반환 `int`
- 이름/아이콘: BaseData의 문자열/Asset 참조

### 24.2 상단 프로필: User + Master Data 조합

`UserInfoPanelMono.Start @ 00f7e92c`에서:
- `UserInfo.Id` → 사용자 ID Text
- `UserInfo.Name` → 닉네임 Text
- `UserInfo.Level` → 레벨 Text
- `UserInfo.Exp` → 경험치 Text/ProgressBar
- `DataCenter.get_HeadData` → 프로필 초상 표시
- `BaseMono.GetLvExpdata` → 레벨별 필요 경험치 조회

따라서 서버 상태(User)와 정적 Master Data(레벨 경험치/초상 리소스)가 결합된다. User 기본 숫자 필드만으로 프로필 패널의 표시 계약이 완성되지는 않는다.

### 24.3 HomePanel.Start의 메뉴/배지 초기화

`HomePanelMono.Start @ 00f67adc`의 Calls OUT에서 다음 메뉴가 직접 초기화 대상임을 확인했다.

- 출석, Hero, 좌/우 이동, 지원, 개발, 상점, 보급, 전투, PVP, 탐험, 친구, 우편, 활동, 채팅, 임무, 창고, 토벌, 월드컵 등
- `RefreshPoint_Task` → `DataCenter.QuestHaveFinished`
- `RefreshPoint_Mail` → DataCenter cache의 `+0xC0` Dictionary 및 key `-27` 검사, 메일 숫자 표시
- `RefreshWareHouse_Supply` → `DataCenter.get_BoxSupplyTotalCount`
- `RefreshPoint_TaoFA` → `CheckTaskStateByID`, CrusadeAwardType 상태, Excel 설정
- `RefreshUIBanner` → DataCache, BannerGrid, ProtoActivity 변환, Activity/WorldCup 표시
- `DataCenter.IsActivityOver` 결과에 따라 `ProtocolGame_SendRequest.GetActivities @ 00de1f68` 또는 Banner 초기화 경로로 분기

여기서 구분할 점:
- 버튼 오브젝트/이벤트 연결은 UI 구성 데이터
- 빨간 점/숫자 표시는 Quest/Mail/BoxSupply 등 상태 cache를 읽는 표시 로직
- 활동 목록은 Bootstrap의 Activities와 연관될 수 있지만, Home Start에서 별도 GetActivities Request가 호출되는 분기가 있으므로 별도 응답 계약 여부를 검증해야 한다.

### 24.4 Main 소비처별 데이터 유형/근거 표

| 화면/요소 | Client 소비 경로 | 데이터 유형/출처 | 현재 계약 상태 |
|---|---|---|---|
| 프로필 ID/이름/레벨/EXP | UserInfoPanelMono.Start | ProtoUser → UserInfo 기본 필드 | 필드 표시 확인, proto 원본 필드 매핑 추가 확인 |
| 프로필 초상 | get_HeadData / ShowHeadPanel | DataCenter 상태 + 정적 Head/Asset | 소비 확인, 원본 필드 미확정 |
| 레벨 EXP bar | GetLvExpdata + UserInfo.Exp/Level | User 상태 + 레벨 Master Data | 계산 참조 확인 |
| 상단 재화 | ShowCoin → GetXCount/GetBaseData | Excel의 int ID 목록 + Item count + BaseData 이름/아이콘 | 동적 목록 생성 확인, ID 전체 미확정 |
| 창고/아이템 | MergeItem → Warehouse | Dictionary<int, ProtoItem> | runtime 확정 |
| Hero | UpdateHeroInfo/InitHero → HeroInfo getter | Dictionary<int, ProtoHero> 및 연관 Weapon/Fashion | 초기화 확인, Home 대표 Hero 선택 미확정 |
| Chapter/Section | Chapter/Section cache → BattleMap/Ready UI | Dictionary<int, ProtoChapter/ProtoSection> | Bootstrap merge/Chapter UI 연결 확인 |
| 임무 배지 | RefreshPoint_Task → QuestHaveFinished | Quest cache + 완료 상태 | 호출 경로 확인, 구체적인 Quest 필드/카운트 미확정 |
| 우편 배지 | RefreshPoint_Mail | DataCenter +0xC0 Dictionary, key -27 | cache key 검사 및 숫자 표시 확인 |
| 보급/창고 배지 | RefreshWareHouse_Supply → get_BoxSupplyTotalCount | DataCenter 집계 값 | getter 소비 확인, 원본 필드 구성 미확정 |
| 토벌 배지 | RefreshPoint_TaoFA → CheckTaskStateByID/CrusadeAwardType | Task/Crusade 상태 + Excel | 호출 경로 확인 |
| 활동 배너 | RefreshUIBanner / InitBanner | DataCache + ProtoActivity + Excel + Asset | 소비 확인, 별도 GetActivities 분기 존재 |
| 월드컵 배너 | RefreshWorldCup | DataCache/Excel/Dictionary<int,int>/BaseData | 소비 확인, 데이터 공급 요청/응답 추가 확인 |

### 24.5 Bootstrap 데이터 유형 및 병합 분류

Bootstrap OpInfo의 주요 컬렉션은 다음과 같이 분류한다.

| OpInfo 필드 | 런타임/정적 자료형 | 병합/저장 | Main에서 확인된 소비 |
|---|---|---|---|
| User +0x88 | ProtoUser | UserInfo 생성/갱신 | 프로필 |
| Heros +0x90 | Dictionary<int, ProtoHero> | UpdateHeroInfo → HeroInfo | Hero getter 호출 |
| Items +0x98 | Dictionary<int, ProtoItem> | MergeItem → +0x78 category cache | 재화/창고 |
| Weapons +0xA0 | Dictionary<int, ProtoWeapon> | MergeWeapon → +0x40 | Hero/Weapon 표시 연관 |
| Equiments +0xA8 | Dictionary<string, ProtoEquipment> 관측 | MergeEquip → +0x38 | Home/Warehouse EquipMax 관련 |
| Chapters +0xC0 | Dictionary<int, ProtoChapter> | Merge → +0x48 | Chapter UI |
| Sections +0xC8 | Dictionary<int, ProtoSection> | MergeSections → +0x50 | Section 개방/입장 UI |
| Teams +0xD0 | Dictionary<int, ProtoTeam> | Merge → +0x58 | Main 소비 미확정 |
| Quests +0xE8 | Dictionary<int, ProtoQuest> | Merge → +0x80 | 임무 배지 소비 후보 |
| Shops +0xF0 | Dictionary<int, ProtoShop> | Merge → +0x68 | Main 소비 미확정 |
| Charges +0xF8 | Dictionary<int, ProtoCharge> | Merge → +0x70 | Main 소비 미확정 |
| Activities +0x120 | Dictionary<int, ProtoActivity> | response merge 경로 | 배너/활동 소비 후보 |
| AIStrategy +0x138 | 별도 객체/필드 | 조건부 set_AIStrategy | Main 필수 여부 미확정 |

자료형 표기는 현재 Listing/런타임에서 확인된 선언을 기준으로 한다. 특히 Equiments의 Dictionary key type, 일부 응답 필드의 generic value type은 최종 schema 확인 전까지 확정하지 않는다.

### 24.6 현재 완료도 — Main 첫 화면 계약은 미완료

**완료된 범위**
- OpInfo envelope 주요 필드/offset/type 관측
- ProccessRequestRes의 주요 merge 호출과 DataCenter cache 연결
- Items → Warehouse UI runtime 검증
- UserInfo 기본 프로필 getter와 UI 연결
- 상단 재화 ID 목록을 Excel 설정에서 분리해 순회하는 구조
- HomePanel 메뉴 초기화 및 일부 배지 getter 연결
- Chapter/Section/Weapon/Equipment의 주요 cache 경로

**남은 범위**
1. ShowCoin의 Excel key에 대응하는 정확한 Record 및 전체 재화 ID 목록
2. UserInfoPanel의 HeadData 원본 필드/Head master data 연결
3. Home 대표 Hero 선택 기준과 실제 표시 getter 집합
4. Quest/Mail/BoxSupply/TaoFa 배지의 정확한 데이터 필드와 cache source
5. Activities가 Bootstrap만으로 충분한지, GetActivities 별도 응답이 필요한지
6. Main 화면에서 실제로 실행되는 별도 Request 전체 목록과 응답의 목적
7. 각 데이터의 필수/선택/lazy-load 판정

### 24.7 다음 작업 우선순위

1. **ShowCoin 설정 ID 전체 복원** — GetExcelData key를 Unity Excel 원본 데이터와 대조.
2. **Main 첫 화면 추가 Request 목록화** — HomePanel.Start에서 호출되는 GetActivities 및 RegisterData/Http callback 흐름 확인.
3. **대표 Hero 표시 경로** — HeroInfo 전체가 아니라 Home 화면에서 선택하는 Hero와 실제 사용 필드만 추적.
4. **메뉴 배지 데이터 source** — Quest/Mail/BoxSupply/TaoFa 각 getter의 DataCenter cache 원본을 연결.
5. 위 항목을 Bootstrap 응답 필수 / 선택 / 별도 요청 / 정적 Master Data·Asset으로 분리해 Local Server 구현 계약에 넘긴다.

전투 씬 내부 및 전투 데이터 분석은 계속 제외한다.


## 25. 상단 재화 8개 목록 — Sysconf 원본 확인

앞 절의 ShowCoin Listing을 Unity 원본 데이터와 대조했다. 분석 순서는 프로젝트 지침에 따라 다음 문서를 먼저 확인하고 원본 JSON을 읽었다.

- `참고용-unity-behavior-data/데이터_파일_역할_및_계층.md`
- `참고용-unity-behavior-data/데이터_분석/README.md`
- `참고용-unity-behavior-data/MonoBehaviour/SysconfRecord.json`

SysconfRecord에서 `m_desc = 个人信息货币显示`인 Record의 `m_value`는 다음 8개 ID다.

```
43000001
43000002
43000003
43000004
43000005
43230000
43600000
43000017
```

이는 ShowCoin이 Excel 설정에서 문자열을 가져와 `SplitToInt32ListError`로 `List<int>`를 만드는 구조와 일치하는 설정 형태다. 다만 Ghidra의 GetExcelData 상수 `0x05A8AD54`와 이 Sysconf Record의 정확한 key/ID 대응은 아직 직접 확인하지 않았으므로, **목록 값은 원본에서 확인됐지만 호출 상수와 Record의 연결은 미확정**으로 남긴다.

### 상단 재화 UI 데이터 계약

| 순서 | ItemId | 의미 |
|---:|---:|---|
| 1 | 43000001 | Coins |
| 2 | 43000002 | Crystals |
| 3 | 43000003 | Energy |
| 4 | 43000004 | 미확정 |
| 5 | 43000005 | 미확정 |
| 6 | 43230000 | 미확정 |
| 7 | 43600000 | 미확정 |
| 8 | 43000017 | 미확정 |

ShowCoin은 이 목록을 순회해 각 항목에 대해:
- `GetXCount(itemId)` → 현재 수량
- `GetBaseData(itemId)` → BaseData
- `BaseData.icon` → 아이콘
- `BaseData.NameByQualityWord` → 이름

을 UI에 바인딩한다.

따라서 상단 재화 표시 계약은 **8개의 int ItemId + 각 Item의 int Count + BaseData 이름/아이콘 참조**로 구체화됐다. 4~8번 ID의 의미는 ItemRecord 및 관련 Resources/Item 데이터와 대조하기 전까지 추측하지 않는다.

### 다음 확인
1. Sysconf Record의 m_id 및 `0x05A8AD54` 연결을 확인한다.
2. 8개 ID를 ItemRecord/ResourcesRecord와 대조해 UI 표시명·아이콘·종류를 확인한다.
3. 최신 runtime에서 ShowCoin 실제 반복 횟수와 8개 항목의 표시 여부를 확인한다.


### 25.1 Sysconf Record ID와 호출 key 대조 보류

원본 Sysconf Record의 암호화된 `m_id.hiddenValue=95315272`, `currentCryptoKey=444444`이므로 현재 데이터 형식의 복호화 규칙을 적용한 ID는 `94870828`이다.

반면 `ShowCoin`의 `Ali.GetExcelData<object>` Listing에서 전달되는 key 상수는 `0x05A8AD54 = 94940500`이다.

두 값이 일치하지 않는다. 따라서 앞서 찾은 `个人信息货币显示` Sysconf 항목은 **상단 재화 표시와 값 목록이 일치하는 관련 설정**이지만, 현재 Listing의 GetExcelData가 이 Record를 직접 읽는다고 확정할 수 없다. 다른 Excel lookup 경로 또는 별도 변환이 있는지 추가 확인한다.

ItemRecord 원본에서 ID 43000001/2/3은 확인됐다. 반면 43000004/5, 43230000, 43600000, 43000017은 현재 ItemRecord에서 발견되지 않았다. 이 5개는 ItemRecord에 없다는 사실만 기록하며, 다른 Record/외부 Master Data에서 제공되는지 미확정으로 둔다.


## 23. 2026-10-02 v4.24 최종 로그 재검증 — Bootstrap 전체 필드 타입

대상: `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`

이번 로그는 이전 로그가 누적되지 않은 신규 실행본으로 취급했다.

### 23.1 Bootstrap 요청/응답

- 요청 SerialNumber: `139954759`
- Opcode: `2`
- ReturnCode: `0`
- `KCPTube.Send ret=1` 및 `KCP_SEND_ACCEPTED`
- 응답 `ProccessRequestRes`: SerialNumber/Opcode/ReturnCode 일치

따라서 이번 실행에서도 Bootstrap 요청과 응답의 상관관계가 확인됐다.

### 23.2 OpInfo envelope — 45개 필드

이번 실행에서 `RESP_FIELD_END count=45`로 OpInfo의 필드명/offset/type을 전부 출력했다.

| Offset | Field | Runtime type | 이번 응답 관측 |
|---:|---|---|---|
| +0x10 | SerialNumber | UInt32 | 139954759 |
| +0x14 | OpCode | OperationCode | 0x2 |
| +0x18 | ReturnCode | Int32 | 0 |
| +0x20 | Time | DateTime | 값 존재 |
| +0x28 | S_0 | String | 참조 |
| +0x30~+0x40 | Int32_0~4 | Int32 | 0 |
| +0x48 | Int64_0 | Int64 | 0 |
| +0x50~+0x68 | S_1~S_4 | String | 참조 |
| +0x70 | DictI32 | Dictionary<int,int> | 참조 |
| +0x78 | BattleReslut | ProtoBattleResult | null |
| +0x80 | FC | ProtoFC | null |
| +0x88 | User | ProtoUser | 참조 |
| +0x90 | Heros | Dictionary<int,ProtoHero> | 참조 |
| +0x98 | Items | Dictionary<int,ProtoItem> | 참조 |
| +0xA0 | Weapons | Dictionary<int,ProtoWeapon> | 참조 |
| +0xA8 | Equiments | Dictionary<string,ProtoEquipment> | 참조 |
| +0xB0 | Mails | Dictionary<string,ProtoMail> | null |
| +0xB8 | Olds | Dictionary<int,ProtoMailOld> | 값 0 |
| +0xC0 | Chapters | Dictionary<int,ProtoChapter> | 참조 |
| +0xC8 | Sections | Dictionary<int,ProtoSection> | 참조 |
| +0xD0 | Teams | Dictionary<int,ProtoTeam> | 참조 |
| +0xD8 | ViewItems | List<ProtoViewItem> | null |
| +0xE0 | Fashions | Dictionary<int,ProtoFashion> | 참조 |
| +0xE8 | Quests | Dictionary<int,ProtoQuest> | 참조 |
| +0xF0 | Shops | Dictionary<int,ProtoShop> | 값 0 |
| +0xF8 | Charges | Dictionary<int,ProtoCharge> | 참조 |
| +0x100 | Friends | Dictionary<long,ProtoFriend> | 값 0 |
| +0x108 | Exam | ProtoRank | null |
| +0x110 | Rival | ProtoRival | null |
| +0x118 | Ranks | Dictionary<long,ProtoRank> | 값 0 |
| +0x120 | Activities | Dictionary<int,ProtoActivity> | 참조 |
| +0x128 | Msgs | List<ProtoMsg> | null |
| +0x130 | ExploreFloor | ProtoExploreFloor | null |
| +0x138 | AIStrategy | Dictionary<int,Dictionary<int,int>> | 참조 |
| +0x140 | BattleReport | PlayerBattleReport | null |
| +0x148 | ShieldFriends | Dictionary<long,ProtoFriend> | 값 0 |
| +0x150 | SupportHero | Dictionary<int,int> | 값 0 |
| +0x158 | SupportHeroRank | Dictionary<long,ProtoSupportRank> | 값 0 |

참고: 로그에서 reference가 정수 0으로 출력된 필드는 객체 null 여부를 확정한 표기가 아니다. 실제 null과 pointer/boxed value 0을 구분해야 하므로, 위 표는 로그 표현을 그대로 보존한다.

### 23.3 이번 실행에서 수량까지 확인된 데이터

| 데이터 | 확인 내용 | 판정 |
|---|---|---|
| User | Id=871053, Level=53, Exp=1100 | runtime 값 확인 |
| Items | MergeItem 입력 Dictionary count=98 | runtime 수량 확정 |
| Chapters | Dictionary _count=61 | runtime 수량 확정 |
| Heros | InitHero 호출 10회 | 최소 10개 ProtoHero가 처리된 사실 확인 |
| Coins | 306095 | getter 반환값 확인 |
| Crystals | 2700 | getter 반환값 확인 |
| Energy | 134 | getter 반환값 확인 |

Hero 10회는 `InitHero` 호출 관측 횟수이며, 원본 Heros Dictionary 전체 count를 직접 읽은 결과와 동일시하지 않는다.

### 23.4 화면 소비 경로와 현재 범위

기존 정적 분석 및 이번 로그를 결합하면:

- User: `UserInfoPanelMono.Start`에서 Id/Name/Level/Exp 사용. 이번 로그에서 Level/Exp getter 확인.
- Currency: UserInfo의 Coins/Crystals/Energy getter → `GetXCount`. 이번 로그에서 세 값 반환 확인.
- Items: Bootstrap Items 98 → MergeItem → DataCenter cache. Warehouse 목록 생성 경로까지 runtime 확인된 기존 결과 유지.
- Heros: ProtoHero → `HeroInfo.InitHero`. 이번 로그에서 10회 처리 및 주요 Hero 필드 확인.
- Chapters: Bootstrap Chapters 61 → DataCenter cache → Chapter UI 정적 연결 확인.
- Weapons/Equiments: Response 필드와 Merge 경로 확인. 실제 메인 첫 화면의 소비 지점은 추가 확인 대상.
- Sections/Teams/Fashions/Quests/Shops/Charges/Activities 등: Response field와 Merge/저장 경로는 확인했으나 Main 첫 화면에서 실제로 읽는 시점/필수 여부는 미확정.

### 23.5 추가 네트워크 요청과 구분

이번 로그에서 Bootstrap 이후:
- Opcode 19 요청/응답 1건
- Ready 화면에서 사용자가 입장 버튼을 누른 뒤 Opcode 22 요청/응답 1건

이 관측은 Bootstrap 자체의 추가 필드가 아니라 별도 기능 요청이다. 메인화면 Bootstrap 필수 데이터 목록에는 합산하지 않는다. Opcode 22 전투 씬 내부 처리는 현재 분석 범위에서 제외한다.

### 23.6 결론 — 메인화면 데이터 분석은 아직 전체 완료가 아님

현재 확정된 것은 **Bootstrap envelope의 45개 필드 타입, 주요 State 병합 경로, Items/Chapters/User/Currency/Hero의 일부 runtime 데이터**다.

아직 완성되지 않은 것은:
1. Home 첫 화면의 각 UI 컴포넌트가 실제로 읽는 DataCenter cache 목록
2. Weapons/Equiments/Sections/Teams/Fashions/Quests/Charges/Activities 중 Main 첫 화면에서 사용하는 필드
3. Main 진입 직후 발생하는 별도 Opcode 요청의 전체 목록 및 Main UI와의 관계
4. 각 Dictionary의 runtime count 및 내부 Proto 타입 필드
5. Local Server 구현 시 null / 빈 Dictionary / 빈 List 중 어떤 표현을 재현해야 하는지

따라서 지금은 Bootstrap을 최소 필드로 줄이지 않는다. **다음 단계는 전투가 아니라 Home/Main 화면의 UI 소비처와 Bootstrap cache 연결을 끝내는 것**이다.

## 24. 다음 작업 — Main 화면 소비 데이터 확정

1. `HomePanelMono.Start` 및 Home의 초기 Refresh 함수들이 참조하는 DataCenter/UserInfo getter를 Listing 기준으로 목록화한다.
2. `UserInfoPanelMono.Start` 외에 상단 재화/프로필/배너/메일/퀘스트/활동 아이콘의 초기화 함수를 확인한다.
3. v4.25 runtime hook은 Home/Main UI 초기화 함수 진입과 DataCenter getter 호출만 기록하고, 던전/전투 함수 hook은 제외한다.
4. Bootstrap 응답의 각 필드를 `Response → Merge/Store → DataCenter cache → Main UI consumer` 표로 매핑한다.
5. Main 화면 첫 진입에 실제 필요한 값과 메뉴를 열 때만 필요한 값을 구분한다.

완료 기준은 **Main 첫 화면을 Local Server Bootstrap 응답만으로 표시하는 데 필요한 모든 데이터의 타입/저장 위치/소비처가 연결되는 것**이다.


## 25. Main UI 소비처를 기준으로 한 추가 정적 분석

이번 단계는 던전/전투 함수가 아니라 Home/Main 화면의 소비처로 범위를 되돌렸다.

### 25.1 UserInfoPanel 상단 영역

`UserInfoPanelMono.Start @ 00f7e92c`의 Calls OUT 및 Listing에서 확인:
- `UserInfo.get_Id`
- `UserInfo.get_Name`
- `UserInfo.get_Level`
- `UserInfo.get_Exp`
- `DataCenter.get_HeadData`
- `BaseMono.GetLvExpdata`
- `UserInfoPanelMono.ShowHeadPanel`
- 이름/ID/레벨/EXP UI 노드 접근

따라서 프로필 상단은 UserInfo의 식별/성장 필드와 HeadData를 함께 사용한다.

### 25.2 UserInfoPanel 재화 표시

`UserInfoPanelMono.ShowCoin @ 00f7e524`:
- `DataCenter.GetXCount`
- `Ali.GetBaseData`
- `Ali.GetExcelData<object>`
- `BaseData.get_icon`
- `BaseData.get_NameByQualityWord`
- `CoinitemNode.lbl_item_count`
- `CoinitemNode.spr_item_icon`
- `CoinitemNode.lbl_item_name`

재화 UI는 고정된 UserInfo 필드만 표시하는 방식이 아니라 Excel/config에서 목록을 얻고, 각 ID를 `GetXCount`로 조회해 수량·아이콘·이름을 표시하는 구조다. 따라서 재화 종류 목록(config)과 각 재화 보유량(State)을 분리해서 Bootstrap/정적 데이터 계약에 반영해야 한다.

### 25.3 HomePanel 시작 함수의 기존 근거

기존 Listing에서 `HomePanelMono.Start @ 00f67adc`는 다음을 호출하는 것으로 확인됐다.
- `DataCenter.get_CurrentEquipMax`
- `DataCenter.get_NextEquipMax`
- `DataCenter.get_EquipMax`
- `Ali.get_dataCache`
- `Ali.GetExcelDic<object>`

또한 HomePanel의 별도 Refresh 함수:
- `RefreshUIBanner @ 00f6ca94`
- `RefreshWareHouse_Supply @ 00f6a2ec`
- `RefreshPoint_TaoFA @ 00f69924`
- `RefreshWorldCup @ 00f6c094`
- `UIRefreshCamp @ 00f6ac08`

이 함수들은 Home 화면의 별도 표시/배너/공급/포인트/월드컵/캠프 갱신 지점으로 추적 대상으로 등록한다. 각 함수 내부의 구체적인 Response 필드 사용은 아직 모두 연결되지 않았다.

### 25.4 현재 메인화면 데이터 매핑 상태

| UI 영역 | 데이터/유형 | Bootstrap 또는 정적 경로 | 판정 |
|---|---|---|---|
| 프로필 이름/ID/레벨/EXP | UserInfo scalar | OpInfo.User → UpdateHeroInfo/UserInfo | 정적 소비 확인, runtime 일부 |
| 상단 재화 | config ID 목록 + GetXCount 수량 + BaseData icon/name | Items → MergeItem/cache + Excel/BaseData | 구조 확인, 목록 config runtime 추가 |
| 에너지 표시 | item ID 43000003 count | Items → MergeItem → GetXCount | runtime 확인, 서버 권한 |
| 창고 보유 아이템 | Dictionary<int,ProtoItem> | Items → MergeItem → category cache | runtime+static 확인 |
| Hero 대표 정보 | Dictionary<int,ProtoHero> → HeroInfo | Heros → UpdateHeroInfo | runtime InitHero 확인 |
| Chapter 진행 | Dictionary<int,ProtoChapter> | Chapters → cache +0x48 | runtime count + static UI 연결 |
| Equipment 확장 수치 | EquipMax 계열 getter | Equiments/cache 및 UserInfo 관련 상태 | Home Start 참조 확인, 정확한 원천 field 추가 확인 |
| 무기/장비 표시 | ProtoWeapon / ProtoEquipment | Weapons/Equiments → Merge | 메뉴 UI 소비 확인, Home 첫 화면 사용은 추가 확인 |
| 배너/토벌/월드컵/캠프 | config + 각 feature state | Home Refresh 함수들 | 함수 진입/필드 매핑 미확정 |
| Quest/Shop/Charge/Activity/Mail | 각 Proto Dictionary | OpInfo 각 field → DataCenter cache | Response/merge 확인, Home 첫 화면 사용 미확정 |

### 25.5 v4.25 runtime hook

`research/justice_hook.js` v4.25에 Main UI 함수 진입 hook을 추가했다.
- HomePanelMono.Start
- HomePanelMono.RefreshUIBanner
- HomePanelMono.RefreshWareHouse_Supply
- HomePanelMono.RefreshPoint_TaoFA
- HomePanelMono.RefreshWorldCup
- HomePanelMono.UIRefreshCamp
- UserInfoPanelMono.Start
- UserInfoPanelMono.RefreshTopInfos
- UserInfoPanelMono.ShowCoin

던전/전투 hook은 새 Main UI 작업 범위에서 제외했다. 기존 KCP Send/Response 관찰 hook은 유지한다.

Git commit: `7e7a52435507cbe14d132617af3a915df5b872ac`

### 25.6 현재 판단 및 다음 단계

**메인화면 데이터가 모두 끝난 상태는 아니다.** Bootstrap envelope와 핵심 State의 타입/merge는 상당 부분 확인했지만, Home 첫 화면에서 실제 읽는 데이터와 별도 기능 화면에서만 필요한 데이터를 아직 완전히 구분하지 못했다.

다음 실행은 v4.25로 로그인 후 메인화면에 머문 상태에서 로그를 수집한다. 메뉴를 열거나 던전으로 이동하지 않는다. 아래 로그를 확인한다.

```
[MAIN_HOME_START]
[MAIN_HOME_BANNER]
[MAIN_HOME_WAREHOUSE_SUPPLY]
[MAIN_HOME_TAOFA]
[MAIN_HOME_WORLDCUP]
[MAIN_HOME_CAMP]
[MAIN_USERINFO_START]
[MAIN_USERINFO_REFRESH]
[MAIN_USERINFO_SHOWCOIN]
```

이 로그를 통해 Home 최초 표시에서 호출되는 함수만 먼저 확정하고, 이어서 해당 함수들이 참조하는 DataCenter getter/Excel config를 매핑한다. Main 첫 화면 데이터 계약이 끝나기 전에는 Dungeon/Battle 분석으로 범위를 확장하지 않는다.


## 26. 2026-10-02 v4.25 최신 단독 로그 분석 — Main 소비 확인

대상 로그:
`research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`

이 파일은 사용자가 새로 갱신한 단독 실행 로그로 분석했다. 이전 로그와 합산하지 않았다.

### 26.1 Bootstrap OpCode=2 응답 확인

이번 로그의 첫 번째 응답:
- SerialNumber: `141689908`
- OpCode: `0x2`
- ReturnCode: `0`
- User: Id=871053, Level=53, Exp=1100
- Items Dictionary: 98개
- Chapters Dictionary: 61개
- Heros Dictionary: 참조 존재, `HeroInfo.InitHero` 10회 관측

요청은 `KCPTube.Send`에서 같은 SerialNumber/OpCode로 확인됐고, Send ret=1 및 `KCP_SEND_ACCEPTED`가 기록됐다. 응답은 `NetworkCenter.TryHandleResponse → DataCenter.ProccessRequestRes`로 처리됐다.

뒤에 나온 두 번째 응답은 SerialNumber=141689908의 Bootstrap 응답과 다른 객체이며, 로그상 OpCode=0이고 User/Items/Heros/Chapters가 null이다. Bootstrap 본 응답과 혼합하지 않는다.

### 26.2 Main 화면 진입과 직접 소비처

다음 Main 함수 진입이 실제 로그에 남았다.

| Hook | 관측 | 의미 |
|---|---|---|
| `HomePanelMono.Start` | 호출됨 | Home 초기화 진입 |
| `RefreshUIBanner` | 호출됨 | 배너 초기화 |
| `RefreshWareHouse_Supply` | 호출됨 | 보급/창고 배지 갱신 |
| `RefreshPoint_TaoFA` | 호출됨 | 토벌 배지 갱신 |
| `UIRefreshCamp` | 호출됨 | 캠프 관련 UI 갱신 |
| `RefreshWorldCup` | 이번 로그 호출 없음 | 이 실행에서는 확인 안 됨 |
| `UserInfoPanelMono.Start` | 이번 로그 호출 없음 | 프로필 패널 초기화는 미관측 |

주의: Hook 진입은 해당 함수가 실행됐다는 증거다. 그 함수가 읽은 모든 내부 필드/목록을 확인했다는 뜻은 아니다.

### 26.3 실제 재화/프로필 상태

이번 실행에서 다음 값이 확인됐다.

| 항목 | 결과 |
|---|---:|
| UserInfo.Level | 53 |
| UserInfo.Exp | 1100 |
| Energy (43000003) | 134 |
| Coins (43000001) | 306095 |
| Crystals (43000002) | 2700 |

세 재화 ID의 BaseData는 모두 found=true이며 runtime type 값은 `0x22`였다. 세 항목 모두 `GetXCount(mode=0)` 반환값이 확인됐다.

이 값들은 해당 실행 시점의 UI/클라이언트 상태 관측값이다. Energy의 서버 권한/소모 경로를 추가로 분석하는 근거로 사용하지 않는다.

### 26.4 Bootstrap State 소비 연결의 현재 판정

| Bootstrap 필드 | 응답/병합 | Main 소비 증거 | 판정 |
|---|---|---|---|
| User | 응답 non-null, UserInfo 생성 | Level/Exp getter 관측, Home 프로필 panel hook은 미관측 | 부분 확인 |
| Items | 98개, MergeItem | Currency GetXCount 및 기존 Warehouse runtime 연결 | 확인 |
| Heros | 응답 non-null, InitHero 10회 | Home Start 전후 Hero getter 호출 다수 | 부분 확인 |
| Weapons | 응답 non-null, Merge 경로 기존 확인 | Home Hero의 WeaponInfo getter 관측 | 부분 확인 |
| Equiments | 응답 non-null, Merge 경로 기존 확인 | Home EquipMax getter의 정적 소비만 확인 | 부분 확인 |
| Chapters | 61개, ProtoChapter/BoxStatus 열거 | Chapter UI 정적 연결 확인 | 데이터/정적 소비 확인 |
| Sections | 응답 non-null, MergeSections | Ready/Section UI 정적 소비 확인 | 데이터/정적 소비 확인 |
| Teams | 응답 non-null | Main 첫 화면 runtime 소비 미확인 | 미확정 |
| Fashions | 응답 non-null | HeroInfo FashionId getter 관측 | 부분 확인 |
| Quests | 응답 non-null | Home 토벌/임무 배지 소비 정적 경로 | 부분 확인 |
| Charges | 응답 non-null | Main 첫 화면 runtime 소비 미확인 | 미확정 |
| Activities | 응답 non-null | Banner 초기화 runtime 진입, 개별 항목 소비 미관측 | 부분 확인 |
| DictI32 | 응답 참조 존재 | UserInfo 성장/설정 merge 경로 기존 확인 | 부분 확인 |
| 기타 null/빈 컬렉션 | 필드 타입 및 값 출력 | Main에서 필요 여부 미확정 | 축소 테스트 필요 |

### 26.5 v4.25 로그에서 드러난 한계

1. 던전 입장 Hook은 설치됐지만 `[DUNGEON_*]` 로그는 하나도 발생하지 않았다. 이번 실행에서 실제 던전 버튼을 누르지 않은 것으로 취급하며, Main 분석에는 사용하지 않는다.
2. `HomePanelMono.Start`와 일부 Refresh 함수는 관측됐지만, 각 함수가 접근한 DataCenter getter를 전부 기록하지는 않았다.
3. `UserInfoPanelMono.Start/ShowCoin`는 이번 로그에서 호출되지 않았다. 상단 재화 getter 결과는 다른 UI 접근 시점에서 관측됐을 수 있으므로, ShowCoin의 8개 설정 ID가 모두 실제 화면에 표시됐다고 단정하지 않는다.
4. Bootstrap 이후 OpCode=0 응답 객체가 별도로 관측됐다. 별도 응답의 요청 SerialNumber/호출 원인은 아직 연결되지 않았다.
5. AssetBundle HTTP 요청은 게임 상태 OpInfo 요청과 분리한다.

### 26.6 다음 단계 — Main 첫 화면 계약을 마무리

전투 분석은 제외한다. 다음은 Main UI 데이터 소비처에 집중한다.

1. v4.26에서는 `UserInfoPanelMono.Start`, `ShowCoin`, `ShowHeadPanel` 및 Home 초기화 함수에서 읽는 getter를 좁혀 기록한다.
2. `HomePanelMono.Start` → 배너/캠프/토벌/보급/월드컵/임무/메일 Refresh별로 정적 Calls OUT과 DataCenter getter를 연결한다.
3. `DataCenter.get_*`, `UserInfo.get_*` 호출은 반환값 전체 dump 대신 getter 이름/호출 횟수/간단한 숫자 값만 기록한다.
4. Bootstrap 필드마다 Main 첫 화면 필수 / Main 진입 후 lazy-load / 메뉴 진입 시 필요 / 정적 Master Data·Asset으로 최종 분류한다.
5. 필수 필드가 확정되기 전까지 Response 필드 축소는 하지 않는다.

### 26.7 로그 보안 주의

로그에 로그인 요청의 사용자명/비밀번호 형태의 입력값과 인증 Token이 포함된 HTTP body가 기록돼 있다. 이 보고서에는 해당 값을 복사하지 않는다. Git 저장소 접근 권한을 제한하고, 가능하면 해당 인증정보를 폐기/재발급한 뒤 로그 파일에서는 민감값을 마스킹한다. 이후 Hook에서는 인증 요청 body 및 계정/Token 관련 문자열을 출력하지 않도록 한다.

**결론:** Bootstrap OpCode=2의 응답/병합은 이번 실행에서도 정상 확인됐다. Main 화면의 일부 UI 진입과 재화/Hero 데이터 사용도 확인됐지만, 프로필 상단/배너/배지의 전체 소비 목록과 각 Bootstrap 필드의 필수성은 아직 미완료다. 현재 우선순위는 v4.26 Main 전용 getter 관찰이다.


## 17. 2026-10-02 실제 운영 KCP Bootstrap 응답 대조

### 17.1 새 Frida 기준 로그

사용자가 추가한 파일:
- `research/reports/Log/lina_로컬서버로_로그인부터메인화면까지들어온_frida로그_데이터는운영거데이터복제로사용KCP데이터.txt`
- Git blob: `ccf0add99b050d9cb9b9184526955b643e74ec42`
- 981 lines, `justice_hook v4.9`

확인 구간:
- `TryRead LEAVE ret=1`
- `BOOT_RESP OpCode=2`
- `TryHandleResponse LEAVE`
- 이후 응답 루프가 계속 진행됨

같은 시점의 상태 덤프:
`User, Heros, Items, Weapons, Equiments, Chapters, Sections, Teams, Fashions, Quests, Charges, Activities` 모두 non-null.

주의: 이 로그는 성공한 Bootstrap 경계와 object null 여부를 증명하지만, field별 원시 bytes나 dictionary count를 출력하지 않는다. 따라서 field wire schema는 PCAP 변환 자료로 보완한다.

### 17.2 정상 PCAP에서 OpCode=2 응답 확보

기존 Git 자료:
- `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/messages.json`
- Git blob: `5a9f8f12466c2a14fb3769b376f96b6eebc8dfc4`
- 변환 텍스트: `messages.txt`, blob `d666303093ba3fd914858f26b4a699ca9344b05a`

패킷 연결:
- packet 189: C→S, outer field 1=Serial, field 2=2 (OpCode=2 요청)
- packets 192~201: S→C 응답 fragment
- AES 복호화 성공, 응답 plaintext 13,290 bytes
- plaintext가 GZIP이며 해제 후 123,115 bytes
- GZIP 해제 데이터에서 outer field 1의 Serial과 field 2=2가 요청과 일치

따라서 packets 192~201은 실제 운영 서버의 OpCode=2 응답으로 판단할 수 있다. 기존 messages.txt는 GZIP 해제 후 protobuf tree를 출력하지 않지만, messages.json의 `gzip_protobuf`에는 해제 후 전체 field tree가 저장되어 있다.

### 17.3 실제 OpCode=2 wire field 구조

아래 count는 GZIP 해제된 응답의 최상위 field occurrence 수다. Wire type은 protobuf 표준 값 기준이며 2는 length-delimited다.

| Field | Wire | Count | 구조 대응(현재 판정) |
|---:|---:|---:|---|
| 1 | 0 | 1 | SerialNumber |
| 2 | 0 | 1 | OpCode (=2) |
| 4 | 2 | 1 | envelope nested |
| 5, 12~15 | 2 | 각 1 | client/device envelope metadata |
| 21 | 2 | 276 | DictI32 / UserInfo vary data 후보 |
| 35 | 2 | 1 | User |
| 37 | 2 | 4 | Heros |
| 38 | 2 | 35 | Items |
| 39 | 2 | 4 | Weapons |
| 40 | 2 | 13 | Equiments |
| 43 | 2 | 61 | Chapters |
| 44 | 2 | 4 | Sections |
| 45 | 2 | 1 | Teams |
| 48 | 2 | 4 | ViewItems 후보 |
| 49 | 2 | 291 | Fashions 후보 |
| 51 | 2 | 66 | Quests 후보 |
| 56 | 2 | 2,462 | Activities 후보 |

Field 21 및 37/38/39/40/43/44/48/49/51/56은 같은 field 번호가 여러 번 등장한다. 특히 field 56은 2,462회다. 즉 **반복 tag 자체는 정상 응답에서 실제로 사용되는 구조**이며, 반복된다는 이유만으로 parser 실패 원인으로 볼 수 없다.

각 dictionary/list 항목은 대체로 최상위 field occurrence 하나 안에 `field 1 key + field 2 value` 형태의 length-delimited nested 구조를 가진다. 내부 value schema는 객체마다 다르며, field 번호만 채우고 임의 값/임의 wire type을 넣는 방식으로 대체할 수 없다.

### 17.4 현재까지의 필드 대응 수준

- Field 21 → OpInfo.DictI32 → UserInfo.MergeVaryData 경로와 일치한다.
- Field 35 → OpInfo.User, Field 37 → Heros, Field 38 → Items, Field 39 → Weapons, Field 40 → Equiments는 nested map/value 형태와 기존 OpInfo getter 목록이 대응한다.
- Field 43 → Chapters, 44 → Sections, 45 → Teams는 기존 DataCenter merge 경로와 대응한다.
- Field 48/49/51/56은 ViewItems/Fashions/Quests/Activities 후보로 기록한다. 정확한 field attribute/tag mapping은 해당 Proto 타입의 역직렬화 경로 또는 runtime field dump와 한 번 더 대조한 뒤 확정한다.
- PCAP 응답에서 보이지 않는 Mails/Olds/Shops/Charges/Friends/Exam/Ranks/Msgs 등은 이 캡처에서 serialized occurrence가 확인되지 않았다. Frida의 non-null 상태 덤프만으로 해당 필드가 wire payload에 실렸다고 간주하지 않는다. 빈 dictionary의 기본 생성 또는 다른 처리 경로일 수 있다.

### 17.5 로컬 서버 실패 실험에 대한 수정된 판단

기존 실험:
- field 1+2만: ret=1 이후 BOOT_RESP, 후속 크래시
- 임의 field 3~64 추가: ret=0

정상 응답 대조 결과:
1. 실제 응답은 field 3~64를 연속으로 채우지 않는다. 확인된 payload tag는 21, 35, 37, 38, 39, 40, 43, 44, 45, 48, 49, 51, 56 등 sparse field 집합이다.
2. 실제 반복 field는 각자의 nested map/value schema를 가진다. 숫자 field만 존재시키거나 wire type을 맞추지 않는 것으로는 동일 응답이 되지 않는다.
3. 따라서 기존 field 3~64 일괄 추가 실험의 ret=0은 repeated tag 자체보다는 **정상 스키마와 다른 tag/wire/nested value 구성**으로 설명하는 편이 현재 증거와 더 잘 맞는다. 다만 parser 구현의 unknown-field 처리 규칙은 별도 확인 전까지 단정하지 않는다.
4. field 1+2의 ret=1 후 크래시는 deserialize 이후 DataCenter merge/UI 초기화에 필요한 상태가 빠진 문제일 가능성이 남는다. 실제 응답 field set을 기준으로 단계별 추가 검증한다.

### 17.6 다음 작업

1. 정상 응답의 field 21 및 35/37/38/39/40/43/44/45/48/49/51/56 각각의 nested schema를 Proto 타입 Listing과 대조한다.
2. local response generator가 만든 protobuf tree를 같은 형식으로 덤프해 정상 PCAP tree와 field별로 diff한다.
3. 우선 field 21, 35, 37, 38, 39, 40, 43, 44, 45를 우선 비교하고, 이후 나머지 group을 추가한다.
4. deserialize 성공과 DataCenter merge 후 Main UI 진입을 별도 단계로 계측한다.

보안/재현 주의:
- 운영 캡처의 세션/토큰/기기 식별값을 그대로 복제하지 않는다.
- 테스트 fixture에는 필요한 구조와 비민감한 테스트 값을 사용한다.


## 18. Nested value schema와 Main UI 소비처 교차 확인

### 18.1 반복 dictionary entry 내부 구조

정상 응답의 map 계열 field는 대체로 다음 형태다.

```
OpInfo field N (wire=2, repeated)
  └─ field 1: key (varint)
  └─ field 2: value (length-delimited message)
       └─ ProtoX의 실제 field들
```

field 21은 예외적으로 map entry 안의 field 2가 scalar varint다. 총 276건이며 field 1 key는 276건, field 2 value는 17건만 명시되어 있다(기본값 0 생략 가능).

### 18.2 실제 nested field signature

| OpInfo 후보 field | Entry 수 | value 내부 field signature |
|---:|---:|---|
| 35 User | 1 | 1, 3, 4, 7, 14, 20, 21, 22, 24 |
| 37 Heros | 4 | 1, 3, 4, 5, 8, 14 |
| 38 Items | 35 | 1, 3 |
| 39 Weapons | 4 | 1, 3, 4, 5 |
| 40 Equiments | 13 | 1(length-delimited), 3(varint) |
| 43 Chapters | 61 | 1, 2, 3, 4, 9, 10, 11 |
| 44 Sections | 4 | 1, 4, 5 |
| 45 Teams | 1 | 1, 3, 4, 5 |
| 48 ViewItems 후보 | 4 | 1 |
| 49 Fashions 후보 | 291 | 1, 3, 4 |
| 51 Quests 후보 | 66 | 1, 2, 5 |
| 56 Activities | 2,462 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13 |

위 signature는 Ghidra에 있는 Proto 타입의 실제 property 구성을 대조하기 위한 기준이다. 특히 field 56은 ProtoActivity property 구성과 일치한다.

### 18.3 Field 56 = Activities 교차 검증

Ghidra Listing:
- `ProtoActivity$$get_Id @ 015ac230`
- `ProtoActivity$$get_Status @ 015ac240`
- `ProtoActivity$$get_Data @ 015ac2b0`
- `ProtoActivity$$get_Expire @ 015ac290`
- `ProtoActivity$$get_OpenTime @ 015ac250`
- `ProtoActivity$$get_CloseTime @ 015ac260`
- `ProtoActivity$$get_PreOpenTime @ 015ac270`
- `ProtoActivity$$get_PreCloseTime @ 015ac280`
- `ProtoActivity$$get_RechargeID @ 015ac2f0`
- `ProtoActivity$$get_I320/I321/I322/I640`

field 56의 value 내부 field 번호는 위 ProtoActivity 구성과 맞는다. 실제 payload에서는 field 3~7이 2,462개 entry 모두에 있고, field 9는 554개 entry에 나타난다. 나머지는 일부 entry에서만 나타나는 optional 값이다.

더 중요한 점:
- `ProtoActivity$$ToDictonary @ 015ac300` Calls IN에 `HomePanelMono$$RefreshUIBanner @ 00f6ca94`가 확인된다.
- 같은 함수는 `ActiveShowPanelMono$$SignShowType1`, `OnClickSignIn`, `RefreshTipsPoint`에서도 호출된다.

따라서 Bootstrap field 56 Activities는 단순 후속 메뉴 데이터가 아니라 **Home 배너/출석/팁 표시 경로에서 읽히는 Main UI 데이터**다.

### 18.4 local server 구현 우선순위 변경

정상 응답에서 확인된 cardinality와 nested schema를 기준으로 다음 순서로 비교한다.

1. Field 35 User
2. Field 21 DictI32
3. Field 37 Heros / 38 Items / 39 Weapons / 40 Equiments
4. Field 43 Chapters / 44 Sections / 45 Teams
5. Field 56 Activities — HomePanel banner/sign-in 소비 경로
6. Field 48/49/51 등 나머지 collection

이제 field 3~64를 일괄 생성하는 방식은 중단한다. 실제 응답에 있는 field 번호만 대상으로 하고, 각 field의 nested value를 해당 Proto 타입 구조에 맞춰 비교한다.


## 19. Field 56 Activities 내부 tag → ProtoActivity property 대응

정상 PCAP의 field 56 각 map value를 다시 집계하고 Ghidra `ProtoActivity` getter 목록과 대조했다.

| nested tag | ProtoActivity property | wire | 출현 수 |
|---:|---|---:|---:|
| 1 | Id | 0 | 13 |
| 2 | Status | 0 | 2,449 |
| 3 | Data | 2 | 2,462 |
| 4 | Expire | 2 | 2,462 |
| 5 | OpenTime | 2 | 2,462 |
| 6 | CloseTime | 2 | 2,462 |
| 7 | PreOpenTime | 2 | 2,462 |
| 8 | PreCloseTime | 0 | 1 |
| 9 | RechargeID | 2 | 554 |
| 10 | I320 | 0 | 1 |
| 11 | I321 | 0 | 1 |
| 12 | I322 | - | 0 |
| 13 | I640 | 0 | 1 |

이 대응은 다음 Ghidra getter와 일치한다.
- `ProtoActivity.get_Id @ 015ac230`
- `get_Status @ 015ac240`
- `get_Data @ 015ac2b0`
- `get_Expire @ 015ac290`
- `get_OpenTime @ 015ac250`
- `get_CloseTime @ 015ac260`
- `get_PreOpenTime @ 015ac270`
- `get_PreCloseTime @ 015ac280`
- `get_RechargeID @ 015ac2f0`
- `get_I320/I321/I322/I640 @ 015ac2c0/015ac2d0/015ac2e0/015ac2a0`

특히 field 3(Data)는 모든 2,462개 entry에 존재한다. field 4~7도 모든 entry에 존재하지만 단순 varint가 아닌 nested length-delimited 구조다. 따라서 local serializer는 이 네 필드를 scalar timestamp로 임의 변환하지 말고, 실제 nested wire 구조를 보존해야 한다.

이제 field56은 단순히 '반복 Activities 목록'이 아니라 **ProtoActivity의 13개 property tag와 각 wire type/cardinality가 확인된 응답 구조**로 취급한다.

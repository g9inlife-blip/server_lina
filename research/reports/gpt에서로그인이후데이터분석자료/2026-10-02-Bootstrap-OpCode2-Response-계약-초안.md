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

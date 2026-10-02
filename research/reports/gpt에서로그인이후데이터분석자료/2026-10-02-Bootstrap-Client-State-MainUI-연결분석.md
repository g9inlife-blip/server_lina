# 2026-10-02 Bootstrap 응답 → Client State → Main UI 연결 분석

## 1. 분석 기준과 현재 상태

서버 구현 진행과 분리해, 클라이언트가 실제 Bootstrap 응답을 어떤 객체와 cache로 바꾸고 어느 UI에서 소비하는지 연결한다.

- 기준 응답: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/plaintext/000192_s2c.bin`
- 기준 runtime: `research/reports/Log/frida_log_static_신규로갱신되므로기존데이터없이최종본만.txt`
- 기준 정적 분석: `research/Ghidra_Listing_txt/DA.txt`
- 성공 기준선: 운영 Bootstrap Replay로 Main 진입, Gold surgical patch로 999,999 표시 성공(서버 진행상황 문서 기준).

주의: OpInfo 메모리 offset(+0x70, +0x88 등)과 protobuf field 번호(21, 35 등)는 서로 다른 체계다. 아래 연결은 실측 payload와 Ghidra/runtime 근거를 합친 것이다.

## 2. Bootstrap wire field → OpInfo → Client State

| Protobuf field | OpInfo member / offset | 처리 경로 | 현재 연결 상태 |
|---:|---|---|---|
| 21 | DictI32 / +0x70 | UserInfo.MergeVaryData → DataCenter.UserInfo(+0x28) | 정적 Listing으로 확정 |
| 35 | User / +0x88 | UserInfo.ctor → DataCenter(+0x28) | 정적 Listing으로 확정 |
| 37 | Heros / +0x90 | UpdateHeroInfo → HeroInfo.InitHero → FinalUpgradeHero / UpdateAIStrategy | 정적 Listing으로 확정 |
| 38 | Items / +0x98 | MergeItem → DataCenter item category cache(+0x78 계열) | 정적+runtime 확정 |
| 39 | Weapons / +0xA0 | MergeWeapon(상위) → cache(+0x40) | 정적 확정 |
| 40 | Equiments / +0xA8 | MergeEquip → cache(+0x38) | 정적 확정 |
| 43 | Chapters / +0xC0 | generic Merge → cache(+0x48) | 정적 확정 |
| 44 | Sections / +0xC8 | MergeSections → cache(+0x50) | 정적 확정 |
| 45 | Teams / +0xD0 | generic Merge → cache(+0x58) | 정적 확정 |
| 48 | ViewItems 후보 / +0xD8 | 직접 병합 cache 미확정 | 후보 |
| 49 | Fashions 후보 / +0xE0 | 직접 병합 cache 미확정 | 후보 |
| 51 | Quests 후보 / +0xE8 | generic Merge → cache(+0x80) | 정적 연결 |
| 56 | Activities / +0x120 | 실제 ProtoActivity signature와 일치 | payload 타입 연결, 소비처 추가 확인 필요 |

추가로 +0xB0 Mails → cache(+0x88), +0xF0 Shops → cache(+0x68), +0xF8 Charges → cache(+0x70) 처리가 Listing에 존재한다. 다만 이 운영 캡처에서 해당 field의 serialized occurrence가 확인되지 않는 항목은 기본 dictionary 생성 여부와 구분한다.

## 3. 핵심 연결 A — User 기본 정보와 vary data는 별도 입력

```
field 35 User
  → OpInfo +0x88
  → UserInfo.ctor
  → DataCenter +0x28
      ├─ Id / Name
      └─ 기본 User 정보

field 21 DictI32
  → OpInfo +0x70
  → UserInfo.MergeVaryData
  → 동일 UserInfo 갱신
      ├─ Level / Exp
      ├─ EquipMax
      ├─ FCTimes
      ├─ SignInDays / SignInRewardDay
      ├─ StepId
      └─ 기타 vary key
```

UserInfoPanelMono.Start는 UserInfo의 Id, Name, Level, Exp getter를 직접 읽는다. 따라서 User 필드만 분석해서 Level/Exp를 모두 설명하면 안 된다. field 21의 vary data까지 함께 봐야 한다.

## 4. 핵심 연결 B — Items와 재화 표시

```
field 38 Items
  → OpInfo +0x98
  → DataCenter.MergeItem
  → BaseData.type별 item category cache(+0x78 계열)
      ├─ WareHousePanelMono.InitData → 창고 List/UI
      └─ DataCenter.GetXCount(itemId)
           ├─ UserInfo.get_Coins    (43000001)
           ├─ UserInfo.get_Crystals (43000002)
           └─ UserInfo.get_Energy   (43000003)
```

- MergeItem runtime 입력 Dictionary는 98개로 관측됐다.
- MergeItem은 BaseData를 조회하고 type 분류를 수행한다.
- GetXCount도 BaseData.type을 기준으로 수량 조회 경로를 분기한다.
- Coins/Crystals/Energy getter는 UserInfo 고정 수치가 아니라 GetXCount를 호출한다.
- 서버 진행상황 문서의 Gold 변경 성공은 field 38의 currency entry 중 ID 43000001의 nested field 3(amount)을 변경한 결과다. 즉 이 변경은 Client의 Items → MergeItem/GetXCount → 재화 UI 경로와 연결되는 것으로 해석된다.

field 38의 entry는 map key/value 외에 ProtoItem 내부 값이 있으므로, 단순히 map key만 바꾸는 것과 실제 표시 수량을 바꾸는 것은 다르다. 정확한 테스트 시에는 ID와 amount가 함께 일치하는지 확인한다.

## 5. 핵심 연결 C — Hero와 무기

```
field 37 Heros
  → OpInfo +0x90
  → DataCenter.UpdateHeroInfo
  → HeroInfo.InitHero
  → FinalUpgradeHero
  → UpdateAIStrategy
  → HeroInfo state

field 39 Weapons
  → OpInfo +0xA0
  → MergeWeapon @ 016e414c
  → DataCenter cache +0x40
  → HeroInfo.get_Weapon / get_WeaponInfomation
  → HeroPartEquipMono.RefreshWeapon / Weapon UI
```

runtime에서 ProtoHero → HeroInfo 변환이 관측됐다. ProtoHero의 Id/Level/Exp/Star/Weapon/FashionId/Stigmata ID 등이 HeroInfo 생성에 입력되고, HeroInfo에는 WeaponInfomation 객체가 생성된다.

확인된 HeroInfo 소비 함수:
- get_Weapon
- get_WeaponInfomation
- HeroPartEquipMono.RefreshWeapon
- WeaponPanelMono.Init / RefreshWeaponInfoBoard

단, 각 화면이 DataCenter +0x40을 직접 읽는 offset-level 연결은 아직 미확정이다.

## 6. 핵심 연결 D — Equipment / Chapter / Section

### Equipment

```
field 40 Equiments
  → OpInfo +0xA8
  → MergeEquip
  → DataCenter cache +0x38
  → EquipMax 계열 getter
  → HomePanelMono.Start / Warehouse 계열
```

HomePanelMono.Start가 EquipMax, NextEquipMax, CurrentEquipMax 계열 getter를 호출한다. 따라서 Equipment 응답은 단순 상세 메뉴 전용으로 볼 수 없다. 단, 각 getter와 cache +0x38의 직접 1:1 연결은 추가 Listing 확인 대상이다.

### Chapter

```
field 43 Chapters
  → OpInfo +0xC0
  → generic Merge
  → DataCenter cache +0x48
  → BattleMapMono.LayChapterItem
  → ProtoChapter / Chapter UI
```

runtime Chapter Dictionary 61개와 ProtoChapter.BoxStatus가 확인됐다. ProtoChapter의 +0x10 Id, +0x14 Status, +0x18 Progress, +0x1C BoxStatus를 소비한다.

### Section과 Section snapshot

```
field 44 Sections
  → OpInfo +0xC8
  → MergeSections
  → DataCenter cache +0x50

Section snapshot
  → MergeSectionSnapShot
  → DataCenter +0x90 (Dictionary<int,int>)
  → IsSectionClear
```

Section collection과 Section snapshot은 별도 상태다. DataCenter +0x90을 ProtoChapter.BoxStatus와 혼동하지 않는다.

## 7. 현재 Main UI 연결 요약

| 화면/소비처 | 읽는 상태 | 증거 수준 |
|---|---|---|
| UserInfoPanelMono.Start | UserInfo Id/Name/Level/Exp | 정적 Listing |
| HomePanelMono.Start | EquipMax 계열, Hero 관련 상태 등 | 정적 호출 관계 |
| HomePanelMono.RefreshUIBanner | Main 배너/활동 상태 후보 | 함수 진입 runtime 확인, 개별 field 매핑 미확정 |
| HomePanelMono.RefreshWareHouse_Supply | Warehouse/Item 관련 상태 | 함수 진입 runtime 확인 |
| WareHousePanelMono.InitData | MergeItem category cache | 정적+runtime |
| BattleMapMono.LayChapterItem | Chapters / ProtoChapter | 정적 |
| HeroPartEquipMono.RefreshWeapon | HeroInfo WeaponInformation | 정적 |

Main 진입 성공은 전체 UI 데이터가 모두 완전히 연결됐다는 뜻은 아니다. 각 데이터가 response에 존재하는 것, DataCenter에 병합되는 것, UI가 실제 읽는 것은 별도 증거로 유지한다.

## 8. 다음 클라이언트 분석 순서

1. **Currency chain 마무리**: field 38 → MergeItem → GetXCount의 BaseData.type별 실제 bucket을 연결하고, 재화 UI가 어느 시점에 getter를 호출하는지 정리한다.
2. **UserInfo vary data 검증**: field 21의 실제 key/value와 UserInfo.MergeVaryData의 key 분기를 대조해 Level/Exp/EquipMax 등 표시값의 출처를 확정한다.
3. **Hero main 소비처**: HeroInfo.InitHero 결과 중 HomePanelMono.Start가 실제 접근하는 getter만 추려 field 37의 필수 속성을 정리한다.
4. **Weapon/Equipment 직접 cache 소비**: cache +0x40/+0x38의 getter 및 UI 호출자를 연결한다.
5. **Chapter/Section UI 경계**: Chapter UI와 Section snapshot의 별도 state가 어떤 화면/요청에 쓰이는지 연결한다.
6. **나머지 응답 그룹**: field 49/51/56(Fashions/Quests/Activities) 및 Shops/Charges/Mails는 Main UI에서 실제 소비가 확인되는 항목만 추가 추적한다.

## 9. 분석 범위 원칙

- 서버 raw payload 생성/수정은 별도 작업 흐름에서 담당한다.
- 본 분석은 Client의 Deserialize 이후 처리, State cache, UI 소비처 연결에 집중한다.
- 운영 데이터의 인증/세션/기기 식별값은 재현용 문서에 복사하지 않는다.
- 각 연결은 CONFIRMED / STATIC / RUNTIME / CANDIDATE로 구분하고, 추정 매핑을 확정처럼 쓰지 않는다.
- Main 화면 진입이 성공한 현재는 KCP/암복호화 재분석을 반복하지 않는다. 클라이언트에서 막히는 구체적 기능이 생길 때만 해당 경계를 다시 조사한다.

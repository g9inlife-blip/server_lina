# 참고용-unity-behavior-data 파일 역할 및 계층

> 범위: 이 폴더의 MD와 MonoBehaviour/*.json 데이터만 기준으로 정리한다.
> 목적: 각 Record가 무엇을 정의하고, 다른 Record를 어떤 방향으로 참조하는지 파악하기 위한 내부 구조 문서.
> 주의: 아직 API/Response 구조나 Research MD와 연결하지 않는다. 확인되지 않은 런타임 동작은 추정으로 표시한다.

## 1. 전체 계층

공통/시스템: Sysconf / Resources / Exp / Leveleffect / Cost / Result
→ 콘텐츠: Actor / Skill / Weapon / Equipment / Fashion / Stigmata / Suit / Talent
→ 아이템/보상: Item → Itembox → Itempackage
→ 아이템 패키지 사용처: Draw / Shopcommodity / Tollgate / Task / Mission / Checkin / Dailyaddition / Activitydetails / Globalreward
→ 스테이지: Chapter → Tollgate → Challenge / Bosspart / Terrain
→ 이벤트: Activitymain → Activitydetails / Crusade / Examinationreward / Explorefloor / Explorerandom / Friendschallenge
→ 표시: Word / Dialog / Mailtemplate / Broadcast / Sound / Cv / Eff / CameraShot / AnimateProperties

핵심은 파일명 순서가 아니라 ID 참조가 실제 계층을 만든다는 점이다.

## 2. 아이템·보상

| 파일 | 역할 | 주요 연결 |
|---|---|---|
| ItemRecord | 개별 아이템의 기본 정의. ID, 품질, 종류, 이름/설명, 아이콘, 최대치 등을 보유 | Itempackage 등 |
| ItemboxRecord | 아이템을 묶어 표현/지급하기 위한 중간 정의 | Itempackage |
| ItempackageRecord | 여러 아이템/재화로 구성된 지급 패키지 | Draw, Shop, Tollgate, Task 등 |
| CostRecord | 기능에 요구되는 비용 구성 | Shop, 강화/제작 등 |
| ResultRecord | 처리 결과/결과 구성 정의 | 콘텐츠 결과 처리 |
| ResourcesRecord | 공통 재화/리소스 정의 | 비용·보상·상점 전반 |

ItemRecord는 무엇인가, ItempackageRecord는 무엇을 몇 개 지급하는가에 가까운 역할로 분리되어 있다.

## 3. 가챠·상점

| 파일 | 역할 | 계층 |
|---|---|---|
| DrawRecord | 가챠 상품/뽑기 정의. m_itemPackageId 등으로 실제 지급 패키지와 연결 | Draw → Itempackage |
| DrawpreviewRecord | 가챠 화면의 후보/확률/미리보기 정보 계층 | Draw ↔ 표시 후보 |
| ShopRecord | 상점의 상위 상품/상점 구성 정의 | Shop → Shopcommodity |
| ShopcommodityRecord | 실제 판매 항목/가격/상품 연결 | Shopcommodity → Item/Itempackage/Cost |
| RechargeRecord | 유료 재화 충전/구매 상품 정의 | 결제상품 → 재화 |
| GiftcodeRecord | 쿠폰/코드 보상 정의 | 코드 → 보상 |

현재 데이터상 Draw와 Drawpreview는 동일 데이터가 아니라 실제 지급 정의와 표시/확률 정보가 분리되어 있을 가능성이 높다. 실행 순서는 코드 분석에서 확정한다.

## 4. 전투·스테이지

| 파일 | 역할 | 주요 연결 |
|---|---|---|
| ChapterRecord | 챕터/월드의 상위 스테이지 그룹 | Chapter → Tollgate |
| TollgateRecord | 실제 전투 스테이지 정의. 보상 패키지, 경험치, 골드, 도전과제 ID 등을 포함 | Chapter → Tollgate → Challenge/Itempackage |
| ChallengeRecord | 추가 조건·도전 목표 | Tollgate |
| BosspartRecord | 보스 파트/보스 구성 | 전투/스테이지 |
| TerrainRecord | 전투 지형/환경 | 전투 |
| CrusadeRecord | 별도 전투/토벌형 콘텐츠 | 전투/보상 |
| FriendschallengeRecord | 친구/대전형 도전 콘텐츠 | Challenge 계층 |

Tollgate은 맵 번호만 정의하는 파일이 아니라 전투 실행에 필요한 보상·경험치·도전과제 정보를 모으는 중심 Record로 보인다.

## 5. 캐릭터·장비·스킬

| 파일 | 역할 |
|---|---|
| ActorRecord | 캐릭터/전투 유닛 핵심 정의 |
| ActorshowRecord | 캐릭터 표시/연출 |
| ActorbreachRecord | 캐릭터 돌파/승급 단계 |
| WeaponRecord | 무기 정의 |
| EquipmentRecord | 장비 정의 |
| FashionRecord | 외형/코스튬 |
| StigmataRecord | 스티그마타 개별 정의 |
| StigmatacombiRecord | 스티그마타 조합/세트 효과 |
| SuitRecord | 슈트/세트 계층 |
| SkillRecord | 스킬 상위 정의 |
| SkillattackRecord | 공격형 스킬 세부 효과 |
| SkillbuffRecord | 버프형 효과 |
| SkilleffRecord | 스킬 효과 세부 정의 |
| SkillrandRecord | 스킬 랜덤/확률 관련 정의 |
| SkillshowRecord | 스킬 표시/연출 |
| TalentRecord | 개별 특성/재능 |
| TalenttreeRecord | 재능 트리 및 노드 관계 |
| AitendencyRecord | AI 행동 성향 |
| AI_Boss_BT | 보스 행동 트리 |
| AI_Unit_Skill_Select | 유닛 스킬 선택 AI |

성장 구조: Actor → Actorbreach / Talent → Talenttree / Skill → Attack·Buff·Eff·Rand·Show

## 6. 과제·보상·출석·이벤트

| 파일 | 역할 |
|---|---|
| TaskRecord | 진행형 과제. taskType, target, totalProgress, reward, unlock, versionOpen 등 |
| MissionRecord | 미션 정의 |
| CheckinRecord | 출석 보상 정의 |
| DailyadditionRecord | 일일 추가 보상/일일 콘텐츠 |
| GlobalrewardRecord | 전역 보상 |
| ExaminationrewardRecord | 시험/평가형 콘텐츠 보상 |
| ActivitymainRecord | 활동/이벤트 상위 정의 |
| ActivitydetailsRecord | 이벤트 세부 단계/조건/보상 |
| ExplorefloorRecord | 탐색 층/구역 |
| ExplorerandomRecord | 탐색 랜덤 이벤트/결과 |
| CrusadeRecord | 토벌/기간형 전투 콘텐츠 |
| FriendschallengeRecord | 친구 도전 콘텐츠 |

beginTime, endTime, period, versionOpen 및 계정 시작/종료 조건은 콘텐츠 활성 조건을 구성하는 공통 축으로 보인다.

## 7. 계정·로그인·시스템

| 파일 | 역할 |
|---|---|
| LoginRecord | 로그인/초기 데이터 |
| SimulationplayerRecord | 시뮬레이션/가상 플레이어 정의 |
| SysconfRecord | 시스템 전역 설정값 |
| ResourcesRecord | 공통 재화/리소스 |
| UsernameRecord | 이름/닉네임 관련 정의 |
| SensitivecharRecord | 금칙/민감 문자 |
| SdkeventRecord | SDK 이벤트 |
| GiftcodeRecord | 코드 입력 및 보상 |

SysconfRecord는 개별 콘텐츠보다 상위에서 전역 설정값을 공급하는 성격으로 분류한다.

## 8. 가이드·텍스트·메일

| 파일 | 역할 |
|---|---|
| GuideRecord | 일반 게임 가이드/튜토리얼 |
| GuidenoviceRecord | 초보자 가이드 |
| DialogRecord | 대화/스토리 대사 |
| MailtemplateRecord | 우편 템플릿 |
| BroadcastRecord | 공지/방송 메시지 |
| WordRecord | 다국어 공통 텍스트 키/문구 |
| Word__krRecord | 한국어 텍스트 |
| HeadiconRecord | 프로필/헤드 아이콘 |
| CvRecord | 캐릭터 음성/보이스 연결 |

콘텐츠 Record의 m_nameId, m_describeId 같은 값은 Word 계층과 연결되는 표시용 ID 패턴이 확인된다.

## 9. 연출·에셋

| 파일 | 역할 |
|---|---|
| SoundRecord | 공통 사운드 리소스 |
| Sound__de/en/fr/jp/kr/ru/twRecord | 언어별 사운드 데이터 |
| EffRecord | 이펙트 리소스/효과 |
| CameraShot | 카메라 연출 |
| AnimateProperties | 애니메이션 속성 |
| AnimateProperties #75623 / #82904 | 개별/추출 애니메이션 데이터 변형본 |
| AssetFileInfoListScriptableObject | 에셋 파일 목록/메타 정보 |

## 10. 숫자·랜덤·성장 보조

| 파일 | 역할 |
|---|---|
| ExpRecord | 경험치/레벨 기준값 |
| LeveleffectRecord | 레벨에 따른 효과/변화 |
| RandomattrRecord | 랜덤 속성 정의 |
| RandomnumRecord | 랜덤 숫자/범위 정의 |
| ForginglistRecord | 제작/단조 조합 목록 |

## 11. 참조 그래프 해석 규칙

1. m_id가 기본 식별자다.
2. xxxId / m_xxxId는 다른 Record ID를 가리키는 후보 필드다.
3. ID가 문자열인 경우도 있으므로 숫자 ID만 가정하지 않는다.
4. a*b 형태는 Task의 reward처럼 ID × 수량 표현으로 사용될 수 있다.
5. 시간/버전 필드는 콘텐츠 활성 조건을 별도 축으로 구성한다.
6. Word 계층은 게임 규칙 데이터와 분리된 표시 계층이다.
7. 따라서 Record 하나만 보지 말고 ID → 참조 Record → 실제 대상 Record 순으로 추적해야 한다.

## 12. 현재 분석에서 가장 중요한 중심 노드

ItemRecord ← ItemboxRecord ← ItempackageRecord ← Draw / Shopcommodity / Tollgate / Task·Mission / Checkin·Dailyaddition / Activitydetails / Globalreward

Chapter → Tollgate → Challenge / Bosspart / Terrain / Exp·Gold / Itempackage

Actor → Actorbreach / Talent → Talenttree / Skill → Skillattack·Skillbuff·Skilleff·Skillrand·Skillshow

## 13. 다음 단계

모든 JSON에서 실제 참조 필드명을 자동 추출하여 Record A → field → Record B 형태의 실제 ID 그래프를 만드는 것이 다음 우선 작업이다. Response 구조나 Research 문서는 이 그래프가 확보된 뒤 작성한다.
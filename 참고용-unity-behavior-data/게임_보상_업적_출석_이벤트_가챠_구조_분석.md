# 아르메블랑쉐 데이터 구조 확장 분석 — 출석/일일보상/업적/이벤트/한정가챠

> 분석 기준: `참고용-unity-behavior-data/MonoBehaviour`
>
> 목적: 서버 구현이 아니라 Unity 데이터 테이블 간 관계를 복원하고, 게임 내 보상/업적/출석/이벤트/가챠 시스템의 실제 구성을 파악한다.

## 1. 전체 구조 요약

현재까지 확인되는 큰 구조는 다음과 같다.

```
LoginRecord
  └─ 로그인 화면/연출 정의
       │
       ├─ CheckinRecord
       │    └─ 장기 출석 보상 (1~3000일)
       │
       ├─ TaskRecord
       │    └─ 일일/주간/장기/이벤트성 과제 및 업적성 목표
       │         └─ 보상 Item ID
       │
       ├─ ChallengeRecord
       │    └─ 스테이지/미션 도전 조건
       │
       └─ ActivitymainRecord
            └─ 이벤트/기간 콘텐츠의 상위 정의
                 └─ ActivitydetailsRecord
                      └─ 실제 이벤트 세부 데이터/상점/미션 연결

ShopRecord
  └─ 상점/가챠 UI 및 그룹
       └─ m_drawPreviewGroup
            └─ DrawpreviewRecord
                 └─ 실제 표시 대상 아이템 + 확률
       └─ DrawRecord
            └─ 등급/추첨 정의
                 └─ ItempackageRecord (452xxxxx 계열)
                      └─ ItemRecord / ItemboxRecord

GlobalrewardRecord
  └─ 기간/계정 조건이 있는 우편형 보상

ExaminationrewardRecord
  └─ 시험/랭킹/점수 구간별 보상

GiftcodeRecord
  └─ 쿠폰/채널별 보상
```

---

# 2. 출석 시스템 — CheckinRecord

## 2.1 핵심 확인

`CheckinRecord.json`은 단순한 UI용 데이터가 아니라 **실제 출석 보상표**로 보인다.

- 레코드 수: **3000**
- 논리 ID: **61000000 ~ 61002999**
- `m_days`: **1 ~ 3000**
- 핵심 필드:
  - `m_days`
  - `m_signedAwards`
  - `m_grandTotal`

즉, 이 게임은 최소한 데이터상 **3000일 장기 출석 테이블**을 가지고 있다.

## 2.2 일반 출석 보상

초기 7일은 다음 패턴이다.

| 출석일 | m_signedAwards | m_grandTotal |
|---:|---|---|
| 1 | 43000001*10000 | |
| 2 | 43001000*1 | |
| 3 | 43000017*1 | 43000002*100 |
| 4 | 43101000*1 | |
| 5 | 43000017*1 | 43600000*10 |
| 6 | 43600000*2 | |
| 7 | 43100013*1 | 43000002*100 |

여기서 `m_signedAwards`는 해당 출석일의 기본 보상, `m_grandTotal`은 특정 누적 출석일에 추가 지급되는 누적 보상으로 해석할 수 있다.

## 2.3 누적 출석 보상 패턴

확인된 누적 보상은 예를 들어 다음과 같다.

- 3일: `43000002*100`
- 5일: `43600000*10`
- 7일: `43000002*100`
- 10일: `43600000*10`
- 15일: `43000002*100`
- 20일: `43600000*10`
- 25일: `43000002*100`
- 30일: `43600000*10`
- 이후에도 5일 단위 패턴이 장기간 반복된다.

따라서 출석은 단순히 "오늘 보상 1개"가 아니라,

**일일 보상 + 특정 누적 출석 마일스톤 보상**

의 2단 구조로 보는 것이 적절하다.

---

# 3. DailyadditionRecord — 일일 보상과 별개의 일일 추가/보정 시스템

`DailyadditionRecord.json`은 이름 때문에 일일보상 테이블로 오해하기 쉽지만 내용은 `CheckinRecord`와 확실히 다르다.

- 레코드 수: **366**
- 논리 ID: **47000000 ~ 47000365**
- `m_day`: 1~366
- 주요 필드:
  - `m_metaphysicsBonus`
  - `m_luckyBonus`
  - `m_stigmataTimes`
  - `m_stigmataTimesLimit`
  - `m_stigmataBonus`
  - `m_stigmataReduce`
  - `m_stigmataCostIncrease`
  - `m_stigmataCostReduce`

즉 이 테이블은 출석 보상 자체가 아니라 **날짜/일수에 따른 추가 보정값 및 특정 시스템의 일일 변동값**을 정의하는 데이터로 보인다.

특히 `m_luckyBonus`와 `m_metaphysicsBonus`가 존재하므로, 이후 관련 게임 로직을 분석할 때 이 테이블을 별도의 "일일 보너스/확률 보정 계층"으로 분리해야 한다.

**중요:** 현재 증거만으로 이것을 "일일보상"이라고 단정하면 안 된다. 실제 출석 보상은 `CheckinRecord`가 직접 담당한다.

---

# 4. TaskRecord — 일반 과제 + 업적성 시스템의 핵심 후보

`TaskRecord.json`:

- 레코드 수: **732**
- 논리 ID: 6000xxxx 계열
- 주요 필드:
  - `m_refreshtype`
  - `m_taskType`
  - `m_target`
  - `m_totalProgress`
  - `m_reward`
  - `m_show`
  - `m_unlock`
  - `m_lockCondition`
  - `m_tollgateId`
  - `m_loginDetection`
  - `m_retain`
  - `m_automatic`
  - `m_versionOpen`

특히 `m_taskType`이 **45종 이상**으로 분화되어 있어, 단순 일일퀘스트 한 종류의 테이블이 아니다.

확인된 taskType:

`1, 5, 6, 13, 14, 15, 16, 17, 19, 27, 29, 30, 31, 32, 34, 35, 38, 42, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75`

예시:

- type 27: 목표 5/6 등, 보상 `43000002*50|43200002*2`
- type 6: 목표 3/4 등, 보상 `43000002*100`
- type 17: 목표 10/20 등, refreshType 0/2가 혼재
- type 5: 214개로 가장 큰 비중 중 하나이며 `m_tollgateId` 기반 콘텐츠와 연결
- type 69: 다른 Task ID들을 `m_target`으로 참조하는 메타/누적형 과제 구조가 확인됨
- type 51~68 등은 특정 콘텐츠/업적성 조건으로 보이는 단발/소수 레코드들이 존재

### 결론

**업적 시스템을 찾을 때 ChallengeRecord만 보면 안 된다.**

현재 데이터 구조상:

```
TaskRecord
  ├─ 반복/일일/주간 과제
  ├─ 콘텐츠 달성 과제
  ├─ 누적 과제
  └─ 업적성 목표
```

가 섞여 있을 가능성이 높다.

따라서 다음 단계에서는 `m_taskType + m_nameId + m_describeId + m_target + m_reward`를 묶어 실제 "일일/주간/업적/이벤트" 분류를 만들어야 한다.

---

# 5. ChallengeRecord — 스테이지 업적/도전 조건

`ChallengeRecord.json`:

- 레코드 수: **431**
- 논리 ID: 2500xxxx 계열
- 주요 필드:
  - `m_type`
  - `m_condition`
  - `m_display`
  - `m_describeId`

초기 데이터에서 다음과 같은 조건이 확인된다.

- type 1: 0.3 / 0.5 / 0.7
- type 2: 0.3 / 0.5 / 0.7
- type 3: 5 / 7 / 10 / 20 / 15
- type 4: `1|1`, `3|1`, `4|1`, `1|2`, `2|2`, `3|2`, `4|2`, `2|3`, `3|3` 등

이 테이블은 앞서 분석한 `MissionRecord.m_challengeIds`와 직접 연결된다.

따라서 현재 구조는:

```
ChapterRecord
  └─ MissionRecord
       └─ m_challengeIds
            └─ ChallengeRecord
```

이다.

이것이 **스테이지별 6개 도전/업적 조건**을 구성하는 핵심이다.

---

# 6. Chapter 업적과 일반 업적을 분리해서 봐야 함

현재 발견된 업적 관련 계층은 최소 2개다.

### A. 스테이지 도전 업적

```
MissionRecord
 └─ 6 × ChallengeRecord
```

앞서 확인한 Chapter 4 기준:

- 10개 미션
- 미션당 6개 Challenge
- 총 60개 Challenge

### B. 전역/콘텐츠 과제

```
TaskRecord
 └─ m_taskType
    └─ 다양한 목표/누적 진행
```

따라서 "업적"이라는 이름 하나로 합치면 안 되고,

**스테이지 별 도전과제**와 **계정/콘텐츠 누적 과제**를 분리해서 복원하는 것이 정확하다.

---

# 7. 이벤트 시스템 — ActivitymainRecord + ActivitydetailsRecord

이 부분은 상당히 중요하다.

## ActivitymainRecord

- 레코드 수: **1491**
- 논리 ID: 9000xxxx 계열
- 주요 필드:
  - `m_type`
  - `m_showType`
  - `m_order`
  - `m_sysconfID`
  - `m_endType`
  - `m_endParameters`
  - `m_preOpenDate`
  - `m_preCloseDate`
  - `m_openDate`
  - `m_closeDate`
  - `m_bannerJump`
  - `m_activityJump`
  - `m_activityTaskWord`
  - `m_button1`, `m_function1`, `m_Jump1`
  - `m_button2`, `m_function2`, `m_Jump2`
  - `m_tab`
  - `m_versionOpen`

실제 데이터에서 2017년~2118년까지의 기간이 들어 있고, 2022년의 하루 단위 이벤트도 다수 존재한다.

예:

- 90001160: 2022-02-28 ~ 2022-03-01
- 90002220: 2022-03-01 ~ 2022-03-02
- 90002240: 2022-03-02 ~ 2022-03-03
- 이후 같은 형태의 일일 이벤트가 연속됨

따라서 Activitymain은 **이벤트 스케줄러/메인 화면 정의** 역할이 매우 강하다.

## ActivitydetailsRecord

- 레코드 수: **4577**
- 부모 ID 종류: 약 **1354개**
- 핵심 필드:
  - `m_parentId`
  - `m_activityData`
  - `m_condition1`
  - `m_condition2`
  - `m_reward`
  - `m_mainTemplateId`
  - `m_turnTo`
  - `m_seqencing`

즉:

```
ActivitymainRecord (9000xxxx)
        ↓
ActivitydetailsRecord (9100xxxx)
        ↓
m_activityData
        ↓
Shop / Task / Mission / 기타 콘텐츠 ID
```

구조가 보인다.

실제 예:

- parent 90000500 → activityData 18200400
- parent 90000900 → activityData 18200500
- parent 90000006 → activityData 27030005~27030007
- parent 90000007 → activityData 27030008~27030010
- parent 90000008 → activityData 27030000~27030001

따라서 **한정 이벤트는 Activitymain/Activitydetails에서 시작해서 실제 Shop/Task/콘텐츠로 내려가는 구조**로 보는 것이 유력하다.

---

# 8. 기간 한정 보상 — GlobalrewardRecord

`GlobalrewardRecord.json`:

- 레코드 수: **1287**
- 논리 ID: 7000xxxx 계열
- 핵심 필드:
  - `m_beginTime`
  - `m_endTime`
  - `m_accountStart`
  - `m_accountEnd`
  - `m_mailTempId`
  - `m_reward`
  - `m_versionOpen`

이 구조는 매우 명확하게 **기간 + 계정 가입 조건 + 우편 보상**을 표현한다.

예:

```
begin: 09/28/2017
end:   10/16/2017
accountStart: 01/01/2016
accountEnd:   10/16/2017
mailTempId: 92000011
reward: 43001000*5
```

따라서:

**기간 이벤트 보상 / 보상 우편 시스템**

으로 분리해야 한다.

---

# 9. ExaminationrewardRecord — 시험/점수 구간 보상

`ExaminationrewardRecord.json`:

- 레코드 수: **216**
- group: **1~7**
- rewardRange: 1~30 및 40,50,60...600 등
- 핵심:
  - `m_group`
  - `m_rewardRange`
  - `m_reward`

예:

- group 1 / range 1 → `43000004*1500|43230000*150`
- group 1 / range 2 → `43000004*1400|43230000*125`
- 이후 점수/순위 구간별로 보상이 내려간다.

따라서 이것은 일반 퀘스트가 아니라 **시험/점수/랭킹형 보상표**로 별도 분리한다.

---

# 10. GiftcodeRecord — 쿠폰/채널 보상

`GiftcodeRecord.json`:

- 레코드 수: **68**
- 주요 필드:
  - `m_distinguish`
  - `m_repeat`
  - `m_group`
  - `m_channel`
  - `m_itemId`

확인된 채널:

`TT, UC, 小米, OPPO, VIVO, 华为, 360, 当乐, 游鲤, 渠道服, 应用宝, 91, 多酷, B站, 小七, 果盘, 夜神, 悟饭游戏, 九妖`

따라서 쿠폰은 단순한 코드 하나가 아니라 **채널/그룹별 보상 정의**를 가지고 있다.

---

# 11. 가챠 — 일반 / UP / 이벤트/한정 계층이 실제로 분리되어 있음

현재까지 가장 명확하게 확인된 부분이다.

## DrawRecord 그룹

총 **2922개**.

주요 그룹:

### group 1
기본 장비 가챠.

설명에:

- 5星装备
- 4星装备
- 碎片
- 3星装备
- 武器

등이 존재.

`m_itemPackageId`는 `452xxxxx` 계열.

### group 2
별도의 장비 풀.

설명에 `世界杯—5星装备` 등 별도 테마가 존재한다.

### group 10~27
캐릭터/장비 **UP 가챠** 계열.

실제 설명:

- 莎拉UP
- 南丁格尔UP
- 风魔小次郎UP
- 西蒙·海亚UP
- 妙法村正UP
- 维拉UP
- 苏UP
- 茱莉娅UP
- 神乐UP
- 齐格飞UP
- 尤利安娜UP
- 李逍儿UP
- 莫妮卡UP
- 海伦UP
- 瑟曦UP
- 弗兰UP
- 希帕蒂娅UP
- 珊德尔UP

즉 **한정/UP 배너가 실제 DrawRecord에 독립 group으로 존재**한다.

### group 30
남딘글 관련 별도 UP/파생 풀.

### group 100
탐험 보물상자.

### group 200 / 201
각각:

- 秩序刻印库
- 光铸刻印库

계열의 별도 추첨 풀.

### group 300~305
복주머니/특수 이벤트 상자.

### group 310~315
1주년 계열 `周年庆典箱`.

### group 320~338
캐릭터별 **禁忌时装(금기/특수 의상)** 및 다이아 충전 계열.

### group 400~405
2주년.

### group 410~415
3주년.

### group 420~425
4주년.

따라서 가챠 시스템은 단일 "장비 뽑기"가 아니라,

```
일반 장비 가챠
├─ 기본 풀
├─ 테마 풀
├─ 캐릭터 UP 풀
├─ 탐험 상자
├─ 특수 재화/각인 풀
├─ 복주머니
├─ 기념일 상자
└─ 의상/특수 이벤트
```

로 구성되어 있다.

---

# 12. DrawpreviewRecord — 실제 표시 확률/등장 아이템 그룹

`DrawpreviewRecord.json`:

- 레코드 수: **112**
- group:
  `1, 2, 100~117, 200, 201, 1000`

### group 1

11개 레코드.

확률 합계 = **1.0**

확률 예:

- 0.0075 = 0.75%
- 0.005 = 0.5%
- 0.015 = 1.5%
- 0.03 = 3%
- 0.2 = 20%
- 0.245 = 24.5%
- 0.45 = 45%

### group 100~117

각각 4개 레코드.

확률 구성은 공통적으로:

- 0.012
- 0.0114
- 0.057
- 0.36

이며 합계는 0.4404.

이 그룹들이 ShopRecord의 개별 상점과 연결되어 있다.

예:

```
Shop 18200300 → preview 111 / 2
Shop 18200400 → preview 110 / 2
Shop 18200500 → preview 105 / 2
Shop 18200700 → preview 112 / 2
...
Shop 18201300 → preview 100 / 2
Shop 18201400 → preview 101 / 2
...
```

즉 **상점/가챠 배너별 미리보기 풀이 따로 존재한다.**

---

# 13. ShopRecord — 가챠 배너/상점의 상위 연결점

`ShopRecord.json`:

- 레코드 수: **154**
- shopType: 1,2,3,4,5,6,10,11,12,200 등
- 특히 shopType 1에서 일반 장비/가챠 계열이 다수 존재
- shop group:
  - 2000~2023
  - 2100
  - 2200
  - 2300
  - 3001~
  - 4000~
  등

가챠와 직접 연결되는 핵심 필드는:

`m_drawPreviewGroup`

예:

```
Shop 18200000 → group 2000 → preview 1
Shop 18200200 → group 2002 → preview 200
Shop 18200300 → group 2003 → preview 111|2
Shop 18200400 → group 2004 → preview 110|2
...
```

따라서 가챠 화면을 복원할 때는 ShopRecord만 보는 것이 아니라:

```
ShopRecord
  ↓
m_drawPreviewGroup
  ↓
DrawpreviewRecord
  ↓
DrawRecord group
  ↓
ItempackageRecord
  ↓
ItemRecord
```

를 모두 연결해야 한다.

---

# 14. 현재까지 확정도가 높은 시스템 분류

| 시스템 | 핵심 파일 | 현재 판단 |
|---|---|---|
| 장기 출석 | CheckinRecord | **확정** |
| 일일 추가/보정 | DailyadditionRecord | **확정적으로 별도 테이블**, 정확한 기능명은 코드 확인 필요 |
| 스테이지 도전 | ChallengeRecord | **확정** |
| 일반/누적 과제 | TaskRecord | **확정** |
| 이벤트 메인 | ActivitymainRecord | **확정** |
| 이벤트 상세 | ActivitydetailsRecord | **확정** |
| 기간 우편 보상 | GlobalrewardRecord | **확정** |
| 시험/점수 보상 | ExaminationrewardRecord | **확정** |
| 쿠폰 | GiftcodeRecord | **확정** |
| 일반/UP/특수 가챠 | DrawRecord | **확정** |
| 가챠 표시 확률 | DrawpreviewRecord | **확정** |
| 가챠/상점 연결 | ShopRecord | **확정** |
| 가챠 결과 패키지 | ItempackageRecord | **강하게 확인됨** |
| 실제 아이템 | ItemRecord | **확정** |

---

# 15. 특히 중요한 발견: "한정가챠"는 Activity와 Draw 양쪽에서 관리될 가능성이 높음

현재 데이터상 한정 콘텐츠는 단일 테이블에만 존재하지 않는다.

예를 들어:

```
Activitymain
  └─ 기간/버전/노출 제어

Activitydetails
  └─ 실제 이벤트 데이터 연결

ShopRecord
  └─ 상점/배너 그룹

DrawRecord
  └─ 실제 UP/특수 추첨 그룹

DrawpreviewRecord
  └─ 표시 확률/아이템 목록

ItempackageRecord
  └─ 실제 결과 패키지

ItemRecord
  └─ 아이템 속성
```

즉 **"언제 열리는가"와 "무엇을 뽑는가"가 서로 다른 데이터 계층**에 있을 가능성이 높다.

이것은 한정가챠 복원에서 매우 중요하다.

---

# 16. 다음 분석 우선순위

다음 단계는 파일을 더 찾는 것보다 **ID 관계를 자동으로 연결하는 작업**이 가장 중요하다.

### 1순위 — TaskRecord 완전 분류
```
m_taskType
→ 실제 한국어 설명
→ 목표 타입
→ refreshType
→ reward
→ versionOpen
```

를 연결하여:

- 일일퀘스트
- 주간퀘스트
- 업적
- 장기 업적
- 이벤트 과제

로 분류.

### 2순위 — CheckinRecord 완전 복원
3000일 전체를 분석해서:

- 기본 출석 보상
- 3/5/7/10/15... 누적 보상
- 장기 반복 패턴
- 특정 날짜의 특별 보상

을 표로 정리.

### 3순위 — Activity → 실제 콘텐츠 연결
```
9000xxxx
→ 9100xxxx
→ m_activityData
→ 18xxxxxx / 27xxxxxx / 기타 ID
```

를 전부 연결해서 **이벤트 종류별 목록**을 만든다.

### 4순위 — 한정 가챠 완전 복원
각 UP group에 대해:

```
Draw group
→ Shop
→ Preview group
→ 5/4/3성
→ ItemPackage
→ 실제 Item
→ 오픈/종료 조건
```

을 연결한다.

### 5순위 — 확률 공식 확인
현재 `DrawRecord.m_probability`와 `DrawpreviewRecord.m_probability`가 존재하지만, 둘을 단순히 곱하거나 같은 값으로 취급하면 안 된다.

실제 코드에서:

- group 선택
- 등급 선택
- ItemPackage 선택
- 중복 처리
- 보장/천장
- `m_limit`
- `m_PumpingCard1`
- `m_PumpingCard2`

의 의미를 확인해야 최종 확률식을 확정할 수 있다.

---

# 17. 결론

현재 파일 구성만으로도 게임의 보상/이벤트 시스템이 생각보다 훨씬 크게 분리되어 있다는 것이 확인된다.

특히 중요한 축은 다음 6개다.

```
① CheckinRecord
   → 3000일 출석

② TaskRecord
   → 일반/반복/누적/업적성 과제

③ ChallengeRecord
   → 스테이지별 도전 업적

④ Activitymain + Activitydetails
   → 기간 한정 이벤트 프레임워크

⑤ Globalreward
   → 기간/계정 조건 보상 우편

⑥ Shop + Draw + Drawpreview + Itempackage
   → 일반/UP/기념일/특수 한정 가챠
```

따라서 앞으로 데이터를 복원할 때는 "보상 파일 하나"를 찾는 방식보다 **ID를 중심으로 여러 Record를 조인하는 방식**으로 분석해야 한다.

현재 가장 가치가 큰 다음 작업은 **TaskRecord 732개를 실제 기능별로 분류하고, Activity 1491개를 이벤트 종류별로 묶은 뒤, Draw group 1~425를 Shop/Preview/Package/Item까지 연결하는 것**이다.

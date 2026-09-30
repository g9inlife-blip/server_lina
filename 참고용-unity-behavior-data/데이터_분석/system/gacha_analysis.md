# 가챠 / 뽑기 1차 분석

## 1. 분석 대상

현재 원본에서 직접 확인된 핵심 Record:

- `DrawRecord.json`
- `DrawpreviewRecord.json`
- `ItempackageRecord.json`
- `ShopRecord.json`
- `ShopcommodityRecord.json`

현재 단계에서는 전체 연결을 확정하기보다, 실제 필드 구조와 ID 관계가 확인된 부분을 기록한다.

---

## 2. DrawpreviewRecord에서 확인된 구조

`DrawpreviewRecord`에는 다음과 같은 필드가 존재한다.

```text
m_id
m_quality
m_period
m_star
m_type
m_group
m_probability
m_articleID
m_nameId
m_describeId
...
```

특히 중요한 것은:

```text
m_group
m_probability
m_articleID
```

의 조합이다.

즉 하나의 Preview Record가:

```text
Group
  |
  +-- Probability
  |
  +-- Article ID 목록
```

형태로 연결되는 구조가 확인된다.

---

## 3. 실제 확률 데이터 확인

확인된 `m_group = 1` 데이터에는 다음과 같은 확률 값이 존재한다.

| Preview ID | 확률 | Article 목록 |
|---|---:|---|
| 54020000 | 0.0075 | 17개 |
| 54020001 | 0.0075 | 32개 |
| 54020002 | 0.005 | 다수 |
| 54020003 | 0.005 | 9개 |
| 54020004 | 0.005 | 12개 |
| 54020005 | 0.015 | 다수 |
| 54020006 | 0.030 | 9개 |
| 54020007 | 0.030 | 12개 |
| 54020008 | 0.200 | 12개 |
| 54020009 | 0.245 | 9개 |
| 54020010 | 0.450 | 다수 |

위에 표시된 11개 그룹의 확률 합은 1.0이다.

따라서 적어도 이 데이터 구간에서는:

```text
m_group = 1
    |
    +-- 여러 등급/보상군
           |
           +-- m_probability
           +-- m_articleID[]
```

형태의 확률 Pool이 실제로 존재한다고 볼 수 있다.

단, `m_quality`, `m_type`, `m_nameId` 중 어떤 필드가 실제 UI 등급/등급명에 해당하는지는 추가 Record 연결 후 확정한다.

---

## 4. m_articleID의 의미

예:

```text
m_articleID =
40000004|40000104|40000204|40000304|...
```

또는:

```text
41105110|41105111|41105112|...
```

처럼 여러 ID가 하나의 문자열에 들어간다.

이것은 이번 분석에서 발견한 `ID|ID|ID` 다중 목록 구조와 정확히 일치한다.

따라서:

```text
DrawpreviewRecord
   |
   +-- m_group
   +-- m_probability
   +-- m_articleID
          |
          +-- Article A
          +-- Article B
          +-- Article C
          ...
```

로 복원할 수 있다.

중요한 점은 `m_articleID`의 각 ID가 실제 어떤 Record를 가리키는지 추가로 확인해야 한다는 것이다.

---

## 5. ID 난독화도 정상적으로 확인

`m_id`는 일반 정수 대신 다음 구조다.

```json
{
  "currentCryptoKey": 444444,
  "hiddenValue": 54431676
}
```

현재 Python 분석기의 XOR 복원 규칙을 적용하면:

```text
54431676 XOR 444444 = 54020000
54431677 XOR 444444 = 54020001
54431678 XOR 444444 = 54020002
54431679 XOR 444444 = 54020003
```

형태가 된다.

따라서 DrawpreviewRecord의 실제 ID inventory도 정상적으로 사용할 수 있다.

---

## 6. Group 구조

확인된 데이터에는 최소한 `m_group = 1`, `m_group = 2`가 존재한다.

예를 들어 group 2에서는:

```text
0.0015
0.0015
0.0014
0.0014
0.0008
0.0072
0.0072
0.0036
0.2000
0.2450
...
```

형태의 확률 데이터가 반복된다.

이는 단순 UI 데이터가 아니라 **여러 개의 뽑기 확률 Pool/테이블이 존재할 가능성**을 보여준다.

그러나 현재 단계에서는 group 1/2가:

- 서로 다른 가챠인지
- 동일 가챠의 다른 상태인지
- 기간/등급별 Pool인지
- 일반/한정 Pool인지

를 아직 확정하지 않는다.

---

## 7. ShopRecord와의 연결 후보

`ShopRecord`에서 다음 필드를 확인했다.

```text
m_shopType
m_showType
m_bookmark
m_sysId
m_week
m_currency
m_seqencing
m_group
m_refreshCycle
m_drawPreviewGroup
m_context
m_versionOpen
```

특히:

```text
m_group
m_drawPreviewGroup
m_currency
m_refreshCycle
```

가 존재한다.

예:

```text
m_currency = 43000003|43000001|43000002
m_refreshCycle = 24
m_drawPreviewGroup = 1
```

따라서 ShopRecord 역시 단순한 상점 UI 목록만이 아니라:

```text
Shop
  |
  +-- Currency
  +-- Group
  +-- Refresh
  +-- DrawPreviewGroup
  +-- VersionOpen
```

구조를 갖는다.

`m_drawPreviewGroup`와 DrawpreviewRecord의 `m_group` 관계는 다음 단계에서 실제 연결 여부를 검증한다.

---

## 8. 현재 가챠 구조 후보

현재까지의 직접 확인 결과를 기반으로 하면 가장 유력한 데이터 구조 후보는 다음과 같다.

```text
Shop / Draw
      |
      +-- DrawRecord
      |
      +-- DrawPreviewGroup
               |
               +-- Group 1
               |     |
               |     +-- Probability
               |     +-- Article IDs
               |
               +-- Group 2
                     |
                     +-- Probability
                     +-- Article IDs
```

그리고 Article ID를 실제 Item/Equipment/Character 등의 Record와 연결하면:

```text
Draw
 |
 +-- Probability Pool
       |
       +-- 0.0075
       |     +-- Article A
       |     +-- Article B
       |
       +-- 0.2000
       |     +-- Article C
       |
       +-- 0.4500
             +-- Article D
             +-- Article E
```

형태로 실제 가챠 목록과 확률표를 복원할 수 있다.

---

## 9. 아직 확인해야 하는 것

### 우선순위 1

`DrawRecord`의 실제 필드 구조를 확보한다.

확인할 항목:

- Draw ID
- 비용
- 재화
- 1회/10회
- DrawPreview 연결
- ItemPackage 연결
- 제한
- 기간
- 보장/천장
- 무료 뽑기

### 우선순위 2

`m_articleID` 대상 Record를 찾는다.

예:

```text
40000004
41105110
41003000
43255110
...
```

이 ID들이 어떤 Record인지 분류한다.

### 우선순위 3

`ItempackageRecord`와 연결한다.

최종적으로:

```text
Draw
 ↓
DrawPreview
 ↓
Article
 ↓
ItemPackage / Item / Equipment / Character
```

관계를 확인한다.

### 우선순위 4

확률의 의미를 확정한다.

현재 `m_probability`는 실제 확률 테이블 값으로 보이지만, 최종 구현에서는:

- 전체 Pool 확률
- 그룹 확률
- 개별 Article 확률
- 가중치

중 어느 수준인지 연결 구조를 통해 확정해야 한다.

---

## 10. 현재 결론

가챠 데이터는 단순 추측 수준을 넘어 **실제 확률과 대상 목록을 가진 구조가 확인된 상태**다.

특히 다음 연결은 강한 근거가 있다.

```text
DrawpreviewRecord
    |
    +-- m_group
    +-- m_probability
    +-- m_articleID[]
```

그리고 ShopRecord에는:

```text
m_drawPreviewGroup
m_group
m_currency
m_refreshCycle
```

가 존재한다.

따라서 다음 단계는 전체 미해결 Reference를 해결하는 것이 아니라:

```text
DrawRecord
   ↓
DrawpreviewRecord
   ↓
m_group
   ↓
m_probability
   ↓
m_articleID
   ↓
실제 Item/Equipment/Character Record
```

를 구체적으로 매핑하는 것이다.

이 매핑이 완료되면 실제 오프라인 가챠 시스템에 사용할 수 있는 정규화 데이터로 변환할 수 있다.

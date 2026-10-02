# Bootstrap OpCode=2 실제 Protobuf 구조 (실측)_lina

**작성일**: 2026-10-02
**출처**: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화_kcp/plaintext/000192_s2c.bin`
- 압축: gzip (13290B → 123115B)
- 패킷: 192, S→C Bootstrap 응답

---

## 1. 최상위 필드 구조

| Field | Wire | 개수 | 추정 매핑 |
|-------|------|------|-----------|
| 1 | varint | 1 | SerialNumber (2551705426) |
| 2 | varint | 1 | OpCode (2) |
| 4 | bytes | 1 | 요청 echo (11B) |
| 5 | string | 1 | "samsung SM-S936N" |
| 12 | string | 1 | device ID |
| 13 | string | 1 | "cbcfdf10d56e57a89f7cb19a491d13" |
| 14 | string | 1 | "Handheld" |
| 15 | string | 1 | "Android OS 16 / API-36..." |
| 21 | bytes | 276 | Items? (각 5~13B, field1=ID, field2=count) |
| 35 | bytes | 1 | **User** (33B, field1=871047, field14='g9in2') |
| 37 | bytes | 4 | ? |
| 38 | bytes | 35 | ? |
| 39 | bytes | 4 | ? |
| 40 | bytes | 13 | ? |
| 43 | bytes | 61 | **Chapters** (문서와 일치: 61개!) |
| 44 | bytes | 4 | ? |
| 45 | bytes | 1 | ? (21B) |
| 48 | bytes | 4 | ? |
| 49 | bytes | 291 | ? |
| 51 | bytes | 66 | ? |
| 56 | bytes | 2462 | ? (대량) |

**중요**: 우리가 추측한 field 3~64가 아님! 실제 태그는 21, 35, 37, 38, 39, 40, 43, 44, 45, 48, 49, 51, 56.

---

## 2. Field 35 = User (확정)

```
field 1 (varint): 871047        ← User ID
field 3 (varint): 4
field 4 (varint): 250
field 7 (varint): 18100000
field 14 (string): 'g9in2'      ← Username
field 20 (varint): 3
field 21 (varint): 3
field 22 (varint): 10
field 24 (varint): 1
```

---

## 3. Field 21 = Items (추정, 276개)

각 entry 구조:
```
field 1 (varint): ID (예: 21000010, 21000020)
field 2 (varint): count (예: 1)
```

첫 entry는 특수값:
```
field 1: 18446744073709551587 (0xFFFFFFFFFFFFFFE3)
field 2: 79
```

---

## 4. Field 43 = Chapters (확정, 61개)

문서의 "Chapters = 61개"와 정확히 일치.

---

## 5. 메모리 오프셋 vs Protobuf 태그 매핑 (추정)

| 메모리 | 필드명 | Protobuf 태그 (추정) | 근거 |
|--------|--------|---------------------|------|
| +0x88 | User | 35 | field1=UserID, field14=username |
| +0x90 | Heros | ? | 37(4개)? 38(35개)? |
| +0x98 | Items | 21 | 276개, ID+count 구조 |
| +0xC0 | Chapters | 43 | 61개로 일치 |

나머지 태그(39, 40, 44, 45, 48, 49, 51, 56)는 추가 분석 필요.

---

## 6. 다음 단계

1. **각 태그의 내부 구조 파싱**: 37, 38, 39, 40, 44, 48, 49, 51, 56의 nested message 구조 분석.
2. **메모리 필드와 매핑**: 각 태그가 어떤 메모리 오프셋에 들어가는지 Frida로 확인 (이미 BOOT_STATE 후크 있음).
3. **최소 응답 구성**: User(35) + Items(21) + Chapters(43)만으로 게임이 진행되는지 테스트.
4. **서버 구현**: 실제 태그 번호로 Bootstrap 응답 빌더 작성.

**더 이상 태그를 추측하지 않는다. 실측 데이터를 기준으로 구현한다.**

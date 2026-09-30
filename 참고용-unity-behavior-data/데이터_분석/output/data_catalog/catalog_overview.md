# Data Catalog Structural Overview

정규화된 Local Data의 실제 Record 구조를 통계적으로 요약한 결과이다.

- Record: 118,015
- 고유 schema signature: 69

## System candidate
- other: 77,977
- skill: 23,470
- item: 6,222
- gacha: 3,034
- shop: 2,868
- item_package: 2,028
- equipment: 1,523
- reward: 1,503
- achievement: 682
- daily: 393
- monster: 242
- event: 101

## 상위 Schema Signature
1. 34,331 records / 19 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_cn, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_name, m_nameId, m_obtainSound, m_period, m_quality, m_specialShow, m_star, m_surface, m_type
2. 11,548 records / 18 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_quality, m_sensitiveChar, m_specialShow, m_star, m_surface, m_type
3. 11,371 records / 55 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_actionType, m_attribute, m_backRange, m_breakType, m_buffLevel, m_criticalLevel, m_describe1Id, m_describeId, m_didden, m_displayStatus, m_dodge, m_dodgeLevel, m_effTime, m_effectLevel, m_failureTips, m_frame, m_frontRange, …
4. 5,274 records / 25 fields — baseDataType, m_CD, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_level, m_mainSkillEff, m_nameId, m_obtainSound, m_pathfinding, m_period, m_quality, m_showEff, m_skillEff, m_skillId, …
5. 4,577 records / 27 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_activityData, m_condition1, m_condition2, m_describe1Id, m_describeId, m_display, m_frame, m_icon, m_iconshow, m_id, m_mainTemplateId, m_nameId, m_obtainSound, m_parentId, m_period, m_position, m_quality, …
6. 3,958 records / 46 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_act1, m_act2, m_act3, m_act4, m_describe1Id, m_describeId, m_flash, m_frame, m_icon, m_iconshow, m_id, m_idle1, m_idle2, m_idle3, m_idle4, m_model1, m_model2, …
7. 3,306 records / 19 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_cn, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_quality, m_specialShow, m_star, m_surface, m_type, m_volume
8. 3,288 records / 40 fields — baseDataType, m_ActorSound, m_PumpingCard1, m_PumpingCard2, m_Tllight, m_atkEffId, m_desSkin, m_describe1Id, m_describeId, m_effEventGroup, m_enterAni, m_eventEffects, m_eventGroup, m_fireAni, m_fireEffId, m_frame, m_ghost, m_hitEffects, m_icon, m_iconshow, …
9. 3,242 records / 18 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_itemId, m_nameId, m_obtainSound, m_period, m_quality, m_specialShow, m_star, m_surface, m_type
10. 3,000 records / 20 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_days, m_describe1Id, m_describeId, m_frame, m_grandTotal, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_quality, m_signedAwards, m_specialShow, m_star, m_surface, m_type
11. 2,922 records / 22 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_desc, m_describe1Id, m_describeId, m_frame, m_group, m_icon, m_iconshow, m_id, m_itemPackageId, m_limit, m_nameId, m_obtainSound, m_period, m_probability, m_quality, m_specialShow, m_star, …
12. 2,714 records / 32 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_costId, m_costNum, m_describe1Id, m_describeId, m_frame, m_group, m_icon, m_iconshow, m_id, m_item1Id, m_itemId, m_itemNum, m_limit, m_limitNum, m_mallIcon, m_nameId, m_obtainSound, …
13. 2,028 records / 18 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_itemWeight, m_nameId, m_obtainSound, m_period, m_quality, m_specialShow, m_star, m_surface, m_type
14. 1,742 records / 34 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_buffIcon, m_buffMarker, m_changeIsClear, m_describe1Id, m_describeId, m_frame, m_hitEffects, m_icon, m_iconshow, m_id, m_longEffId, m_nameId, m_obtainSound, m_parameterA, m_parameterB, m_parameterC, m_parameterD, …
15. 1,694 records / 32 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_parameterA, m_parameterB, m_parameterC, m_parameterD, m_parameterE, m_parameterF, m_parameterG, m_parameterH, m_parameterI, …
16. 1,507 records / 35 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_backgroundMusic, m_bossBurstPointPicture, m_bossIds, m_describe1Id, m_describeId, m_fail, m_frame, m_friendlyPosition, m_icon, m_iconshow, m_id, m_itemPackageId, m_monsterPosition, m_nameId, m_neutralPosition, m_obtainSound, m_period, …
17. 1,491 records / 43 fields — baseDataType, m_Jump1, m_Jump2, m_PumpingCard1, m_PumpingCard2, m_activityJump, m_activityTaskWord, m_activityicon, m_bannerJump, m_bookmark, m_button1, m_button2, m_closeDate, m_describe1Id, m_describeId, m_endParameters, m_endType, m_frame, m_function1, m_function2, …
18. 1,395 records / 26 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_desc, m_desc1, m_describe1Id, m_describeId, m_frame, m_group, m_icon, m_iconshow, m_id, m_location, m_luckyBonus, m_metaphysicsBonus, m_nameId, m_obtainSound, m_part, m_period, m_quality, …
19. 1,292 records / 39 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_angle, m_boneName, m_describe1Id, m_describeId, m_directionType, m_display, m_effAni, m_effModel, m_frame, m_icon, m_iconshow, m_id, m_leftEffAni, m_leftPosition, m_loop, m_loopAni, m_name, …
20. 1,287 records / 24 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_accountEnd, m_accountStart, m_beginTime, m_describe1Id, m_describeId, m_endTime, m_frame, m_icon, m_iconshow, m_id, m_mailTempId, m_nameId, m_obtainSound, m_period, m_quality, m_reward, m_specialShow, …
21. 1,100 records / 76 fields — baseDataType, m_Isplug, m_PumpingCard1, m_PumpingCard2, m_actionTimes, m_actorShowId, m_atk, m_atkPct, m_avatarId, m_bearhelpplus, m_biochemistrydef, m_biochemistryplus, m_cd, m_collision, m_critchance, m_critcoefficient, m_critdef, m_def, m_defPct, m_describe1Id, …
22. 997 records / 18 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_quality, m_randomNum, m_specialShow, m_star, m_surface, m_type
23. 984 records / 24 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_actorID, m_describe1Id, m_describeId, m_frame, m_group, m_icon, m_iconshow, m_id, m_maxTime, m_nameId, m_necessaryActor, m_obtainSound, m_optionId, m_period, m_power, m_quality, m_specialShow, …
24. 952 records / 26 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_isOpen, m_itemPackageId, m_jump, m_location, m_max, m_model, m_nameId, m_obtainSound, m_parameter, m_period, m_quality, …
25. 924 records / 28 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_attribute1, m_attribute2, m_attribute3, m_attribute4, m_decompose, m_demandLevel, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_order, m_period, m_quality, …
26. 784 records / 26 fields — baseDataType, m_ActivityMainId, m_PumpingCard1, m_PumpingCard2, m_challenge, m_describe1Id, m_describeId, m_exploreRandomId1, m_exploreRandomId2, m_exploreRandomId3, m_floor, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_power, m_quality, …
27. 732 records / 37 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_automatic, m_clearData, m_describe1Id, m_describeId, m_dialog1Id, m_dialog2Id, m_displayPanel, m_frame, m_icon, m_iconshow, m_id, m_lockCondition, m_loginDetection, m_nameId, m_obtainSound, m_period, m_quality, …
28. 713 records / 19 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_articleID, m_describe1Id, m_describeId, m_frame, m_icon, m_iconshow, m_id, m_nameId, m_obtainSound, m_period, m_quality, m_specialShow, m_star, m_surface, m_template, m_type
29. 682 records / 55 fields — baseDataType, m_PumpingCard1, m_PumpingCard2, m_ShowAvatar, m_SkillRandId, m_allowTeam, m_attributes, m_backGround, m_battlefieldTIM, m_captainPackageId, m_challengeIds, m_chaos, m_chapter, m_consume, m_describe1Id, m_describeId, m_endDialogId, m_endshow, m_eventPoint, m_first, …
30. 599 records / 39 fields — baseDataType, m_MaxWeaponSkillLevel, m_PumpingCard1, m_PumpingCard2, m_attack, m_attack_g, m_changeAni, m_code, m_cost, m_describe1Id, m_describeId, m_development, m_frame, m_icon, m_iconshow, m_id, m_line, m_linkUser, m_nameId, m_notUnlocked, …

## 상위 Field
- m_id: 118,015
- baseDataType: 118,015
- m_icon: 118,015
- m_quality: 118,015
- m_frame: 118,015
- m_surface: 118,015
- m_period: 118,015
- m_star: 118,015
- m_type: 118,015
- m_specialShow: 118,015
- m_nameId: 118,015
- m_describeId: 118,015
- m_describe1Id: 118,015
- m_obtainSound: 118,015
- m_PumpingCard1: 118,015
- m_PumpingCard2: 118,015
- m_iconshow: 118,015
- m_cn: 37,823
- m_name: 36,020
- m_parameterA: 14,807
- m_parameterB: 14,807
- m_probability: 14,405
- m_priority: 13,230
- m_power: 13,139
- m_effectLevel: 12,471
- m_attribute: 12,184
- m_target: 12,125
- m_trigger: 11,674
- m_sensitiveChar: 11,548
- m_actionType: 11,401
- m_source: 11,371
- m_targetType: 11,371
- m_triggerRound: 11,371
- m_hpPer: 11,371
- m_triggerSkillType: 11,371
- m_dodge: 11,371
- m_didden: 11,371
- m_effTime: 11,371
- m_userIds: 11,371
- m_targetIds: 11,371
- m_userGroup: 11,371
- m_targetGroup: 11,371
- m_partExist: 11,371
- m_partLost: 11,371
- m_criticalLevel: 11,371
- m_dodgeLevel: 11,371
- m_skilleffPre: 11,371
- m_skilleffNeg: 11,371
- m_buffLevel: 11,371
- m_targetBuffLevel: 11,371

## 원칙
- Schema signature는 구조 묶음 확인용이다.
- system candidate는 의미 확정값이 아니다.
- Field type은 자료형만 기록한다.
- 샘플은 사실 확인용으로 제한한다.
- Unknown / Server Candidate는 별도로 유지한다.

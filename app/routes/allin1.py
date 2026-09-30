"""V3 AllInOne 라우트 (부트스트랩).

참고: 실제 구현은 app/routes/login.py의 v3_allin1에 있음.
(form 파싱 + sign 검증이 필요해서 login.py에 통합)
"""
from fastapi import APIRouter

router = APIRouter()
# 라우트는 login.py에 정의됨

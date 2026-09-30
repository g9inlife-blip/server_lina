"""익명/게스트 라우트."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/v3/account/anon")
def anon():
    # TODO: API_Anon 스펙 확정 후 구현
    return {"ret": 0, "msg": "ok"}

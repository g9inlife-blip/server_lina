"""V3 AllInOne 라우트 (부트스트랩)."""
from fastapi import APIRouter, HTTPException

from .. import config
from ..crypto import verify_sign
from ..models import SignedParams

router = APIRouter()


@router.post("/allin1")
def v3_allin1(params: SignedParams):
    body = params.model_dump()
    sign = body.pop("sign")

    if not verify_sign(config.LOGIN_CONTENT, body, sign):
        raise HTTPException(status_code=400, detail="sign verification failed")

    # TODO: 실제 AllInOne 응답 구조는 캡처 후 확정
    return {"ret": 0, "msg": "ok"}

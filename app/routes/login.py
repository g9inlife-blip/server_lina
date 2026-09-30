"""V4 로그인 라우트."""
from fastapi import APIRouter, HTTPException

from .. import config
from ..crypto import verify_sign
from ..models import LoginParams, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def v4_login(params: LoginParams):
    # Sign 검증: content는 클라이언트가 Sign에 넘긴 값
    # TODO: content가 요청에 포함되는지, 별도 필드인지 캡처로 확정
    body = params.model_dump()
    sign = body.pop("sign")

    # content 후보: 고정 MD5 (Frida 캡처)
    # 실제 content 전달 방식이 확정되면 수정
    if not verify_sign(config.LOGIN_CONTENT, body, sign):
        raise HTTPException(status_code=400, detail="sign verification failed")

    # TODO: 계정 검증, 토큰 발급
    return LoginResponse(ret=0, msg="ok", token="local-dev-token")

"""요청/응답 모델.

클라이언트가 보내는 파라미터 구조 (Frida 캡처 기반):
- V3 (AllInOne): n, d, r, v, m + sign
- V4 (Login): n, d, r, v, m, t, u, p, method, platform, p2 + sign
"""
from pydantic import BaseModel
from typing import Optional


class SignedParams(BaseModel):
    """Sign 서명된 파라미터 딕셔너리. 추가 필드 허용."""

    model_config = {"extra": "allow"}

    n: str          # .NET Ticks 타임스탬프
    d: str          # 기기 ID (고정 MD5)
    r: str = "7"
    v: str = "3.1.0"
    m: str = "official"
    sign: str       # Sign() 출력 (MD5 hex)


class LoginParams(SignedParams):
    """V4_POST_Login 파라미터."""

    t: str          # base64 (256 bytes 디코드), 세션마다 변경
    u: str          # 계정 ID
    p: str          # 비밀번호
    method: str = ""
    platform: str = "google"
    p2: str = "logout"


class LoginResponse(BaseModel):
    """로그인 응답. 실제 필드는 서버 응답 캡처 후 확정."""

    ret: int = 0
    msg: str = "ok"
    token: Optional[str] = None

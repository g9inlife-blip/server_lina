"""V4 로그인 라우트.

실제 캡처 기반 (2026-09-30):
- URL: POST /v5/account/login?<random>
- Content-Type: application/x-www-form-urlencoded
- 응답: JSON (아래 LoginResponse 참고)
"""
import time
import urllib.parse
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import config
from ..crypto import verify_sign, compute_sign

router = APIRouter()


def parse_form_body(body: bytes) -> dict[str, str]:
    """application/x-www-form-urlencoded 파싱.
    
    중요: keep_blank_values=True 필수!
    method="" 같은 빈 값도 Sign 계산에 포함되기 때문.
    """
    return dict(urllib.parse.parse_qsl(body.decode("utf-8"), keep_blank_values=True))


@router.post("/v5/account/login")
async def v4_login(request: Request):
    body = await request.body()
    params = parse_form_body(body)

    # sign 검증
    sign = params.pop("sign", "")
    # content는 고정 MD5 (Frida 캡처)
    if not verify_sign(config.LOGIN_CONTENT, params, sign):
        return JSONResponse(
            status_code=400,
            content={"Status": 1, "Desc": "sign verification failed"},
        )

    # 로그인 응답 (2026-09-30 캡처 기반)
    # Token: 실제 서버는 344자 Base64 (368B 핸드셰이크용)
    # 운영처럼 랜덤 바이트 사용 (null 없음)
    import base64
    import os
    # 256바이트 랜덤 -> Base64 344자 (서버 재시작마다 고정)
    # 고정값을 위해 시드 기반 생성
    import hashlib
    seed = b"server_lina-fixed-token-v1"
    token_bytes = hashlib.sha256(seed).digest()  # 32B
    # 256B로 확장 (SHA256 반복)
    full = b""
    counter = 0
    while len(full) < 256:
        full += hashlib.sha256(seed + counter.to_bytes(4, 'little')).digest()
        counter += 1
    token_bytes = full[:256]
    new_token = base64.b64encode(token_bytes).decode()
    assert len(new_token) == 344, f"토큰 길이 오류: {len(new_token)}"

    # 응답의 sign은 요청 파라미터들로 계산 (서버도 sign을 포함)
    resp_sign = compute_sign(config.LOGIN_CONTENT, params)

    return {
        "logout_ex_time": 0,
        "sign": resp_sign,
        "t": params.get("t", ""),
        "platform": params.get("platform", "google"),
        "UserId": 861197,  # TODO: 실제 사용자 DB 연동
        "p2": params.get("p2", "logout"),
        "FCMStatus": 4,
        "v": params.get("v", "3.1.0"),
        "RealName": True,
        "m": params.get("m", "official"),
        "u": params.get("u", ""),
        "Age": 27,
        "Status": 0,
        "Desc": "成功",
        "First": 0,
        "method": params.get("method", ""),
        "d": params.get("d", ""),
        "p": params.get("p", ""),
        "r": params.get("r", "7"),
        "n": params.get("n", ""),
        "Token": new_token,
    }


@router.post("/v3/ain1")
async def v3_allin1(request: Request):
    """AllInOne - API URL 목록 반환."""
    body = await request.body()
    params = parse_form_body(body)

    sign = params.pop("sign", "")
    if not verify_sign(config.LOGIN_CONTENT, params, sign):
        return JSONResponse(
            status_code=400,
            content={"Status": 1, "Desc": "sign verification failed"},
        )

    # 로컬 서버 URL로 변경
    base = f"http://{config.HOST}:{config.PORT}"
    cdn_base = f"{base}/cdn/v310/202608022111/"
    resp_sign = compute_sign(config.LOGIN_CONTENT, params)

    return {
        "v": "3.1.0",
        "Keys": [
            {"Key": "API_Login", "URL": f"{base}/api/v5/account/login"},
            {"Key": "API_Anon", "URL": f"{base}/api/v3/account/anon"},
            {"Key": "API_Allin1", "URL": f"{base}/api/v3/ain1"},
        ],
        "m": "official",
        "Desc": "成功",
        "Status": 0,
        "sign": resp_sign,
        "Servers": [{"Host": config.HOST, "Port": 8000}],
        "Assets": [
            {
                "Ping": f"{cdn_base}readme.txt",
                "CDN": cdn_base,
                "Version": "3.1.88",
            }
        ],
        "n": params.get("n", ""),
        "d": params.get("d", ""),
        "r": params.get("r", "7"),
    }

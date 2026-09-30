"""Sign 알고리즘 — 2026-09-29 런타임 검증으로 확정.

원본: ProtocolGame_HttpRequest.Sign(string content, Dictionary<string,string> dict)
동작:
    1. dict의 key를 문자열 오름차순으로 정렬
    2. 정렬된 key의 value들을 "." 으로 연결
    3. 마지막에 content 추가
    4. MD5 해시
    5. dict["sign"]에 저장 (클라이언트) / 검증 (서버)

근거: Arme-lina research/reports/2026-09-29-Sign-알고리즘-런타임-검증.md
"""
import hashlib


def compute_sign(content: str, params: dict[str, str]) -> str:
    """Sign 알고리즘 재현. dict는 수정하지 않고 sign 문자열만 반환."""
    keys = sorted(params.keys())
    values = [params[k] for k in keys]
    values.append(content)
    joined = ".".join(values)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()


def verify_sign(content: str, params: dict[str, str], sign: str) -> bool:
    """클라이언트가 보낸 sign이 올바른지 검증.
    
    params에는 "sign" 키 자체가 포함되면 안 된다
    (Sign 입력에 sign 키는 포함되지 않음).
    """
    check = dict(params)
    check.pop("sign", None)
    return compute_sign(content, check) == sign.lower()


def sign_params(content: str, params: dict[str, str]) -> dict[str, str]:
    """Sign()의 in-place 동작 재현: dict에 sign 키를 추가한 복사본 반환."""
    out = dict(params)
    out["sign"] = compute_sign(content, params)
    return out

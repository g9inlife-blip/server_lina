"""AES-128-CBC 암복호화 (PKCS7 패딩).

KCP 페이로드는 AES-128-CBC/PKCS7로 암호화됨.
PCAP 실제 복호화 성공 (2026-09-30).
"""
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """AES-128-CBC 암호화.

    IV는 어떻게 결정되는지 확인 필요.
    일단 16바이트 0으로 가정 — 실제 패킷으로 검증 필요.
    """
    if len(key) != 16:
        raise ValueError(f"키는 16바이트여야 함: {len(key)}")
    # TODO: IV 결정 방식 확인 (패킷에서 추출 or 고정)
    iv = b"\x00" * 16
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def aes_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    """AES-128-CBC 복호화."""
    if len(key) != 16:
        raise ValueError(f"키는 16바이트여야 함: {len(key)}")
    # TODO: IV 결정 방식 확인
    iv = b"\x00" * 16
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)

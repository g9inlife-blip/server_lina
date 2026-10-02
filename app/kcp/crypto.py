"""AES-128-CBC 암복호화 (PKCS7 패딩).

KCP 페이로드는 AES-128-CBC/PKCS7로 암호화됨.
Ghidra DecryptUnSafe 분석 (2026-10-02):
- encrypted payload = [IV 16B][Rijndael CBC ciphertext]
- IV는 고정 0이 아니라 데이터 앞 16바이트
- 16바이트 단위 TransformBlock 반복, 나머지는 TransformFinalBlock
"""
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def aes_encrypt(key: bytes, plaintext: bytes, iv: bytes | None = None) -> bytes:
    """AES-128-CBC 암호화.

    IV를 지정하지 않으면 랜덤 16B 생성 후 앞에 붙여서 반환.
    (DecryptUnSafe 형식: [IV 16B][ciphertext])
    """
    if len(key) != 16:
        raise ValueError(f"키는 16바이트여야 함: {len(key)}")
    import os
    if iv is None:
        iv = os.urandom(16)
    if len(iv) != 16:
        raise ValueError(f"IV는 16바이트여야 함: {len(iv)}")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(pad(plaintext, AES.block_size))


def aes_decrypt(key: bytes, data: bytes) -> bytes:
    """AES-128-CBC 복호화.

    입력 형식: [IV 16B][ciphertext]
    IV는 데이터 앞 16바이트에서 추출.
    """
    if len(key) != 16:
        raise ValueError(f"키는 16바이트여야 함: {len(key)}")
    if len(data) < 32:  # IV(16) + 최소 1블록(16)
        raise ValueError(f"데이터가 너무 짧음: {len(data)}B")
    if (len(data) - 16) % 16 != 0:
        raise ValueError(f"암호문 길이가 16의 배수가 아님: {len(data)-16}B")
    iv = data[:16]
    ciphertext = data[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)


def aes_decrypt_with_iv(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    """IV를 별도로 지정하는 복호화 (하위 호환)."""
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("키와 IV는 16바이트여야 함")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)

"""DH64 키교환.

Ghidra 분석 확정 (2026-09-30):
- modulus p = 2^64 - 59 = 0xFFFFFFFFFFFFFFC5
- secret = peerPublic ^ localPrivate mod p
- Key = LE64(secret1) || LE64(secret2) (16 bytes)

Handshake2 패킷 구조:
- peer public #1 = UInt64(packet + 0x11)
- peer public #2 = UInt64(packet + 0x19)
"""
import os
import struct

# DH modulus: 2^64 - 59
P = 0xFFFFFFFFFFFFFFC5


def dh_secret(local_private: int, peer_public: int) -> int:
    """DH secret 계산: peerPublic ^ localPrivate mod p."""
    return pow(peer_public, local_private, P)


def derive_key(secret1: int, secret2: int) -> bytes:
    """16바이트 세션 키: LE64(secret1) || LE64(secret2)."""
    return struct.pack("<Q", secret1) + struct.pack("<Q", secret2)


class DH64:
    """서버 측 DH64 키교환."""

    def __init__(self):
        # 서버 private 키 2개 생성 (64비트 랜덤)
        self.private1 = int.from_bytes(os.urandom(8), "little")
        self.private2 = int.from_bytes(os.urandom(8), "little")
        self.session_key: bytes | None = None

    def get_public_pair(self) -> tuple[int, int]:
        """서버 public 키 반환 (클라이언트에 전송용).

        참고: 실제 DH에서는 generator g가 필요.
        Ghidra에서 generator 확인 필요 — 현재는 placeholder.
        """
        # TODO: Ghidra에서 generator g 확인
        # 일단 private를 public처럼 반환 (실제 구현 시 수정)
        return self.private1, self.private2

    def compute_session_key(self, peer_public1: int, peer_public2: int) -> bytes:
        """클라이언트 public 키로 세션 키 계산."""
        secret1 = dh_secret(self.private1, peer_public1)
        secret2 = dh_secret(self.private2, peer_public2)
        self.session_key = derive_key(secret1, secret2)
        return self.session_key

    @staticmethod
    def parse_handshake2(packet: bytes) -> tuple[int, int]:
        """Handshake2 패킷에서 peer public 키 추출.

        - public #1 = UInt64(packet + 0x11)
        - public #2 = UInt64(packet + 0x19)
        """
        if len(packet) < 0x21:
            raise ValueError(f"Handshake2 패킷이 너무 짧음: {len(packet)}")
        pub1 = struct.unpack_from("<Q", packet, 0x11)[0]
        pub2 = struct.unpack_from("<Q", packet, 0x19)[0]
        return pub1, pub2

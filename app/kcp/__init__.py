"""KCP 게임 서버.

구조:
- DH64 키교환으로 세션 키 생성
- AES-128-CBC로 페이로드 암복호화
- Opcode 기반 요청/응답

참고: research/reports/2026-09-30-KCP-DH64-Key-Recovery-PCAP-복호화.md
"""
from .dh64 import DH64
from .crypto import aes_decrypt, aes_encrypt
from .server import KCPServer

__all__ = ["DH64", "aes_decrypt", "aes_encrypt", "KCPServer"]

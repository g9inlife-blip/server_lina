"""KCP 게임 서버 (UDP).

포트 8000/UDP에서 클라이언트 패킷 대기.
DH64 핸드셰이크 → 세션 키 생성 → 암호화 통신.

프로토콜 (PCAP 기반):
- C→S Handshake1 (373B, UDP): Base64 DH 키
- S→C Handshake1 응답 (37B, UDP): 서버 public #1, #2
- 이후 KCP 암호화 통신 (AES-128-CBC)
"""
import socket
import struct
import threading
from .dh64 import DH64


class KCPServerUDP:
    """UDP 기반 KCP 게임 서버."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.running = False
        # addr -> DH64 매핑 (세션별)
        self.sessions: dict = {}

    def start(self):
        """서버 시작."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        print(f"[*] KCP UDP 서버 시작: {self.host}:{self.port}")

        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                t = threading.Thread(target=self.handle_packet, args=(data, addr))
                t.daemon = True
                t.start()
            except Exception as e:
                if self.running:
                    print(f"[!] 수신 실패: {e}")

    def handle_packet(self, data: bytes, addr):
        """패킷 처리."""
        pkt_len = len(data)
        print(f"[*] {addr}에서 {pkt_len}B 수신")

        if pkt_len == 373:
            self.handle_handshake1(data, addr)
        elif pkt_len < 373:
            # KCP 데이터 패킷 (암호화됨)
            print(f"[*] KCP 데이터 패킷: {pkt_len}B")
            # TODO: 복호화 → opcode 처리
        else:
            print(f"[!] 알 수 없는 패킷 크기: {pkt_len}")

    def handle_handshake1(self, data: bytes, addr):
        """Handshake1 (368B) 처리."""
        print(f"[*] Handshake1 감지 ({len(data)}B) from {addr}")

        dh = DH64()
        self.sessions[addr] = dh

        # 세션 ID 생성 (8B 랜덤)
        import random
        session_id = random.getrandbits(64)

        # 서버 응답 (33B, PCAP 형식)
        # 0x00-0x07: zeros (8B)
        # 0x08: 0x01 (1B)
        # 0x09-0x10: session ID (8B)
        # 0x11-0x18: ??? (8B)
        # 0x19-0x20: server public? (8B)
        srv_pub1, srv_pub2 = dh.get_public_pair()

        resp = bytearray(33)
        struct.pack_into("<Q", resp, 0x00, 0)  # zeros
        resp[0x08] = 0x01
        struct.pack_into("<Q", resp, 0x09, session_id)
        # 0x11: 8B (PCAP: bfca... - 용도 불명, 랜덤으로)
        struct.pack_into("<Q", resp, 0x11, random.getrandbits(64))
        # 0x19: server public #1 (8B)
        struct.pack_into("<Q", resp, 0x19, srv_pub1)
        # 0x21: 1B 남음 (PCAP 33B)

        self.sock.sendto(bytes(resp), addr)
        print(f"[*] Handshake1 응답 전송: 33B to {addr}")
        print(f"[*] Session ID: {session_id:#x}")
        print(f"[*] Server public #1: {srv_pub1:#x}")

        # 세션 저장 (session_id -> dh)
        self.sessions[session_id] = dh

    def stop(self):
        """서버 중지."""
        self.running = False
        if self.sock:
            self.sock.close()


def main():
    server = KCPServerUDP()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[*] 종료 중...")
        server.stop()


if __name__ == "__main__":
    main()

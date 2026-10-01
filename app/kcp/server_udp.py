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

        if pkt_len == 373 or pkt_len == 368:
            self.handle_handshake1(data, addr)
        elif pkt_len == 51:
            self.handle_handshake_51(data, addr)
        elif pkt_len == 221:
            self.handle_kcp_data(data, addr)
        elif pkt_len < 373:
            # 기타 KCP 데이터 패킷
            print(f"[*] KCP 데이터 패킷: {pkt_len}B from {addr}")
            print(f"    hex: {data[:64].hex()}...")
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

    def handle_handshake_51(self, data: bytes, addr):
        """51B 핸드셰이크 처리 (UDP)."""
        print(f"[*] 51B 핸드셰이크 감지 from {addr}")

        dh = DH64()
        self.sessions[addr] = dh

        try:
            # 0x08: public #1 (8B), 0x10: public #2 (8B)
            pub1 = struct.unpack_from("<Q", data, 0x08)[0]
            pub2 = struct.unpack_from("<Q", data, 0x10)[0]
            print(f"[*] Client public #1: {pub1:#x}")
            print(f"[*] Client public #2: {pub2:#x}")

            # 2중 DH
            secret1 = pow(pub1, dh.private1, 0xFFFFFFFFFFFFFFC5)
            secret2 = pow(pub2, dh.private2, 0xFFFFFFFFFFFFFFC5)
            print(f"[*] Secret #1: {secret1:#x}")
            print(f"[*] Secret #2: {secret2:#x}")

            session_key = struct.pack("<Q", secret1) + struct.pack("<Q", secret2)
            print(f"[*] 세션 키: {session_key.hex()}")

            # 토큰 (0x18~)
            token = data[0x18:0x18+40].split(b'\x00')[0].decode('utf-8', errors='ignore')
            print(f"[*] 토큰: {token}")
        except Exception as e:
            print(f"[!] DH 실패: {e}")
            import traceback
            traceback.print_exc()
            return

        # 51B에 대한 서버 응답: 33B (PCAP의 실제 서버 응답 형식)
        # PCAP [1] S→C 33B:
        # 0x00-0x07: zeros
        # 0x08: 0x01
        # 0x09-0x10: session ID (8B)
        # 0x11-0x18: ??? (8B)
        # 0x19-0x20: server public? (8B)
        try:
            import random
            session_id = random.getrandbits(64)
            srv_pub1, srv_pub2 = dh.get_public_pair()

            resp = bytearray(33)
            struct.pack_into("<Q", resp, 0x00, 0)  # zeros
            resp[0x08] = 0x01
            struct.pack_into("<Q", resp, 0x09, session_id)
            struct.pack_into("<Q", resp, 0x11, random.getrandbits(64))  # ???
            struct.pack_into("<Q", resp, 0x19, srv_pub1)  # server public

            self.sock.sendto(bytes(resp), addr)
            print(f"[*] 33B 응답 전송 to {addr}")
            print(f"[*] Session ID: {session_id:#x}")
            print(f"[*] Server public: {srv_pub1:#x}")

            # 세션 저장
            self.sessions[session_id] = (dh, session_key)
        except Exception as e:
            print(f"[!] 응답 실패: {e}")
        return

    def handle_kcp_data(self, data: bytes, addr):
        """221B KCP 데이터 패킷 처리."""
        # 0x00-0x07: session ID (8B)
        session_id = struct.unpack_from("<Q", data, 0x00)[0]
        print(f"[*] KCP 데이터: session={session_id:#x}, len={len(data)}B")

        # 세션 키 조회
        session = self.sessions.get(session_id)
        if not session:
            print(f"[!] 세션 없음: {session_id:#x}")
            return

        dh, session_key = session

        # 암호문 추출 (0x20부터)
        # 221B - 32B 헤더 = 189B
        ciphertext = data[0x20:]
        print(f"[*] 암호문 길이: {len(ciphertext)}B")

        # AES-128-CBC 복호화 시도
        try:
            from .crypto import aes_decrypt
            # 16의 배수로 자르기 (PKCS7 패딩 고려)
            # 189B는 16의 배수가 아님 - 앞부분만 시도
            for try_len in [176, 192]:
                if try_len <= len(ciphertext):
                    try:
                        ct = ciphertext[:try_len]
                        pt = aes_decrypt(session_key, ct)
                        print(f"[*] 복호화 성공! (len={try_len})")
                        print(f"    평문 hex: {pt[:64].hex()}")
                        print(f"    평문 ASCII: {''.join(chr(b) if 32<=b<127 else '.' for b in pt[:64])}")
                        break
                    except Exception as e:
                        continue
            else:
                print(f"[!] 복호화 실패 (모든 길이 시도)")
        except Exception as e:
            print(f"[!] 복호화 오류: {e}")

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

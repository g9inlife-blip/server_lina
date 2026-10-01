"""KCP 게임 서버 스켈레톤.

포트 8000에서 클라이언트 연결 대기.
DH64 핸드셰이크 → 세션 키 생성 → 암호화 통신.

현재 상태: 뼈대만 구현. Opcode 핸들러는 TODO.
"""
import socket
import struct
import threading
from .dh64 import DH64
from .crypto import aes_decrypt, aes_encrypt


class KCPServer:
    """KCP 게임 서버."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.running = False
        # opcode -> handler 매핑 (나중에 추가)
        self.handlers: dict[int, callable] = {}

    def start(self):
        """서버 시작."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        print(f"[*] KCP 서버 시작: {self.host}:{self.port}")

        while self.running:
            try:
                conn, addr = self.sock.accept()
                print(f"[+] 연결: {addr}")
                t = threading.Thread(target=self.handle_client, args=(conn, addr))
                t.daemon = True
                t.start()
            except Exception as e:
                if self.running:
                    print(f"[!] Accept 실패: {e}")

    def handle_client(self, conn: socket.socket, addr):
        """클라이언트 처리."""
        try:
            dh = DH64()
            # 1. Handshake 수신 (Handshake1: 373B 또는 Handshake2: 56B)
            data = conn.recv(4096)
            if not data:
                return

            pkt_len = len(data)
            print(f"[*] Handshake 패킷 수신: {pkt_len} bytes")

            if pkt_len == 373:
                # Handshake1: Base64 DH 키 교환
                print(f"[*] Handshake1 감지")
                # 서버 응답 (37 bytes, PCAP 형식)
                # 0x00-0x07: zeros
                # 0x08-0x0B: 25 (0x19)
                # 0x0C: 0x01
                # 0x0D-0x14: ??? (PCAP: d106000000000000)
                # 0x15-0x1C: server public key (8B)
                # 0x1D-0x24: ??? (PCAP: f946af9e83fde980)
                srv_pub1, _ = dh.get_public_pair()
                resp = bytearray(37)
                struct.pack_into("<Q", resp, 0x00, 0)  # zeros
                struct.pack_into("<I", resp, 0x08, 25)  # length
                resp[0x0C] = 0x01
                # 0x0D: PCAP 값 그대로 사용 (의미 불명)
                resp[0x0D:0x15] = bytes.fromhex("d106000000000000")
                struct.pack_into("<Q", resp, 0x15, srv_pub1)
                # 0x1D: PCAP 값 그대로 사용
                resp[0x1D:0x25] = bytes.fromhex("f946af9e83fde980")
                conn.send(bytes(resp))
                print(f"[*] Handshake1 응답 전송: 37 bytes")
                print(f"[*] Server public: {srv_pub1:#x}")

                # Handshake2 대기
                data = conn.recv(4096)
                if not data:
                    return
                pkt_len = len(data)
                print(f"[*] Handshake2 패킷 수신: {pkt_len} bytes")

            if pkt_len == 56:
                # Handshake2: 토큰 전송
                print(f"[*] Handshake2 감지")
                print(f"    hex: {data.hex()}")
                # 토큰 추출 (0x19부터)
                try:
                    token_raw = data[0x19:]
                    token = ''.join(chr(b) if 32 <= b < 127 else '' for b in token_raw)
                    print(f"[*] 토큰: {token[:50]}")
                except:
                    pass

                # DH public 키 (0x11)
                try:
                    pub1 = struct.unpack_from("<Q", data, 0x11)[0]
                    print(f"[*] Client public: {pub1:#x}")
                    # 세션 키 계산 (단일 DH)
                    secret = pow(pub1, dh.private1, dh.P if hasattr(dh, 'P') else 0xFFFFFFFFFFFFFFC5)
                    print(f"[*] Secret: {secret:#x}")
                except Exception as e:
                    print(f"[!] DH 계산 실패: {e}")

                # Handshake2 응답 (56B, 에코)
                resp = bytearray(56)
                resp[0:0x11] = data[0:0x11]
                srv_pub1, _ = dh.get_public_pair()
                struct.pack_into("<Q", resp, 0x11, srv_pub1)
                # 토큰 부분은 그대로
                resp[0x19:] = data[0x19:]
                conn.send(bytes(resp))
                print(f"[*] Handshake2 응답 전송: 56 bytes")

            # 3. 이후 패킷 처리 루프
            print(f"[*] 핸드셰이크 완료, 데이터 대기 중...")
            while True:
                pkt = conn.recv(4096)
                if not pkt:
                    break
                print(f"[*] 패킷 수신: {len(pkt)} bytes, hex: {pkt[:32].hex()}...")

        except Exception as e:
            print(f"[!] 클라이언트 처리 실패 ({addr}): {e}")
        finally:
            conn.close()
            print(f"[-] 연결 종료: {addr}")

    def stop(self):
        """서버 중지."""
        self.running = False
        if self.sock:
            self.sock.close()


if __name__ == "__main__":
    server = KCPServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[*] 종료 중...")
        server.stop()

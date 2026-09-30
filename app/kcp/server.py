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
            # 1. Handshake2 수신
            # TODO: 실제 핸드셰이크 패킷 구조 확인
            data = conn.recv(4096)
            if not data:
                return

            print(f"[*] Handshake 패킷 수신: {len(data)} bytes")
            print(f"    hex: {data[:32].hex()}...")

            # 2. Peer public 키 추출 시도
            try:
                pub1, pub2 = DH64.parse_handshake2(data)
                print(f"[*] Peer public: {pub1:#x}, {pub2:#x}")
                session_key = dh.compute_session_key(pub1, pub2)
                print(f"[*] 세션 키: {session_key.hex()}")
            except Exception as e:
                print(f"[!] Handshake 파싱 실패: {e}")
                return

            # 3. 이후 패킷 처리 루프
            # TODO: KCP 패킷 구조 파악 후 구현
            while True:
                pkt = conn.recv(4096)
                if not pkt:
                    break
                print(f"[*] 패킷 수신: {len(pkt)} bytes")
                # TODO: 복호화 → opcode 파싱 → 핸들러 호출 → 응답

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

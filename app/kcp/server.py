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
            data = conn.recv(4096)
            if not data:
                return

            print(f"[*] Handshake 패킷 수신: {len(data)} bytes")
            print(f"    hex: {data.hex()}")
            # 패킷 저장 (분석용)
            import time
            ts = int(time.time() * 1000)
            pkt_path = f"/tmp/hs_{ts}_{addr[1]}.bin"
            try:
                with open(pkt_path, "wb") as f:
                    f.write(data)
                print(f"    저장: {pkt_path}")
            except:
                pass

            # 2. Peer public 키 추출
            try:
                pub1, pub2 = DH64.parse_handshake2(data)
                print(f"[*] Peer public: {pub1:#x}, {pub2:#x}")
                session_key = dh.compute_session_key(pub1, pub2)
                print(f"[*] 세션 키: {session_key.hex()}")
            except Exception as e:
                print(f"[!] Handshake 파싱 실패: {e}")
                return

            # 2.5. 서버 Handshake 응답 전송
            # 클라이언트 패킷과 동일한 구조 (56 bytes, public 키는 0x11, 0x19)
            try:
                srv_pub1, srv_pub2 = dh.get_public_pair()
                print(f"[*] Server public: {srv_pub1:#x}, {srv_pub2:#x}")
                # 응답 패킷 구성 (클라이언트 패킷 구조 모방)
                resp = bytearray(56)
                # 헤더 복사 (0x00-0x10)
                resp[0:0x11] = data[0:0x11]
                # 서버 public 키 삽입
                struct.pack_into("<Q", resp, 0x11, srv_pub1)
                struct.pack_into("<Q", resp, 0x19, srv_pub2)
                # 나머지 복사
                resp[0x21:] = data[0x21:]
                conn.send(bytes(resp))
                print(f"[*] Handshake 응답 전송: {len(resp)} bytes")
            except Exception as e:
                print(f"[!] Handshake 응답 실패: {e}")
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

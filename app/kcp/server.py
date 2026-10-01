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
                print(f"[*] Handshake1 감지 (373B)")
                # 서버 응답 (37 bytes, PCAP 형식)
                # 0x00-0x07: zeros
                # 0x08-0x0B: 25 (0x19)
                # 0x0C: 0x01
                # 0x0D-0x14: TCPConvID (8B)
                # 0x15-0x1C: Server DH public #1 (8B)
                # 0x1D-0x24: Server DH public #2 (8B)
                srv_pub1, srv_pub2 = dh.get_public_pair()
                resp = bytearray(37)
                struct.pack_into("<Q", resp, 0x00, 0)  # zeros
                struct.pack_into("<I", resp, 0x08, 25)  # length
                resp[0x0C] = 0x01
                # 0x0D: TCPConvID (랜덤 생성)
                import random
                conv_id = random.getrandbits(64)
                struct.pack_into("<Q", resp, 0x0D, conv_id)
                # 서버 public 키 #1, #2 (생성된 값 사용!)
                struct.pack_into("<Q", resp, 0x15, srv_pub1)
                struct.pack_into("<Q", resp, 0x1D, srv_pub2)
                conn.send(bytes(resp))
                print(f"[*] Handshake1 응답 전송: 37 bytes")
                print(f"[*] Server public #1: {srv_pub1:#x}")
                print(f"[*] Server public #2: {srv_pub2:#x}")

                # Handshake2 대기
                data = conn.recv(4096)
                if not data:
                    return
                pkt_len = len(data)
                print(f"[*] Handshake2 패킷 수신: {pkt_len} bytes")

            if pkt_len == 56:
                # Handshake2: 클라이언트→서버
                # 56B 프로토콜: public #1만 있음 (0x11)
                print(f"[*] Handshake2 감지 (56B)")

                # DH public #1 (0x11, 8B)만 사용 (단일 DH)
                try:
                    pub1 = struct.unpack_from("<Q", data, 0x11)[0]
                    print(f"[*] Client public #1: {pub1:#x}")

                    # 단일 DH secret 계산
                    secret1 = pow(pub1, dh.private1, 0xFFFFFFFFFFFFFFC5)
                    print(f"[*] Secret #1: {secret1:#x}")

                    # 16B 세션 키
                    session_key = struct.pack("<Q", secret1) + struct.pack("<Q", secret1)
                    print(f"[*] 세션 키: {session_key.hex()}")
                except Exception as e:
                    print(f"[!] DH 계산 실패: {e}")

                # 서버 응답 전송 (56B)
                # 클라이언트가 응답을 기다리는 것으로 보임
                try:
                    srv_pub1, _ = dh.get_public_pair()
                    resp = bytearray(56)
                    resp[0:0x11] = data[0:0x11]  # 헤더 복사
                    struct.pack_into("<Q", resp, 0x11, srv_pub1)  # 서버 public
                    resp[0x19:] = data[0x19:]  # 나머지 (토큰 포함) 복사
                    conn.send(bytes(resp))
                    print(f"[*] Handshake2 응답 전송: 56 bytes")
                    print(f"[*] Server public #1: {srv_pub1:#x}")
                except Exception as e:
                    print(f"[!] 응답 전송 실패: {e}")

                print(f"[*] KCP 패킷 대기 중...")

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

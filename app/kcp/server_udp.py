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

    # 고정 서버 DH 키 (서버 재시작까지 유지)
    # 클라이언트가 서버 공개키를 캐싱할 수 있으므로 매번 새로 생성하면 안 됨
    _fixed_dh = None

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.running = False
        # addr -> DH64 매핑 (세션별)
        self.sessions: dict = {}
        # 고정 DH 키 초기화 (최초 1회)
        if KCPServerUDP._fixed_dh is None:
            KCPServerUDP._fixed_dh = DH64()
            print(f"[*] 고정 서버 DH 키 생성")
            print(f"    Public #1: {KCPServerUDP._fixed_dh.public1:#x}")
            print(f"    Public #2: {KCPServerUDP._fixed_dh.public2:#x}")

    def start(self):
        """서버 시작."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        # 타임아웃 설정 (CTRL+C 종료 가능하도록)
        self.sock.settimeout(1.0)
        self.running = True
        print(f"[*] KCP UDP 서버 시작: {self.host}:{self.port}")
        print(f"[*] 종료: CTRL+C (또는 CTRL+Break)")

        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                t = threading.Thread(target=self.handle_packet, args=(data, addr))
                t.daemon = True
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[!] 수신 실패: {e}")

    def handle_packet(self, data: bytes, addr):
        """패킷 처리."""
        pkt_len = len(data)
        print(f"[*] {addr}에서 {pkt_len}B 수신")

        if pkt_len == 373 or pkt_len == 368:
            self.handle_handshake1(data, addr)
        elif pkt_len == 51 or pkt_len == 364:
            # 51B/364B: 같은 구조, 토큰 길이만 다름
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
        """Handshake1 (368B) 처리 - 51B와 동일한 로직."""
        print(f"[*] Handshake1 감지 ({len(data)}B) from {addr}")

        # 고정 DH 키 사용 (51B와 동일)
        dh = KCPServerUDP._fixed_dh

        try:
            # 368B 구조: 0x08 public #1, 0x10 public #2, 0x18~ token
            # 51B와 동일한 오프셋!
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
            token = data[0x18:0x18+344].split(b'\x00')[0][:40]
            print(f"[*] 토큰 앞 40자: {token}")
        except Exception as e:
            print(f"[!] DH 실패: {e}")
            import traceback
            traceback.print_exc()
            return

        # 33B 응답 (51B와 동일: 두 공개키 모두 전송)
        try:
            import random
            session_id = random.getrandbits(64)
            srv_pub1, srv_pub2 = dh.get_public_pair()

            resp = bytearray(33)
            struct.pack_into("<Q", resp, 0x00, 0)
            resp[0x08] = 0x01
            struct.pack_into("<Q", resp, 0x09, session_id)
            struct.pack_into("<Q", resp, 0x11, srv_pub2)  # server public #2
            struct.pack_into("<Q", resp, 0x19, srv_pub1)  # server public #1

            self.sock.sendto(bytes(resp), addr)
            print(f"[*] Handshake1 응답 전송: 33B to {addr}")
            print(f"[*] Session ID: {session_id:#x}")
            print(f"[*] Server public #1: {srv_pub1:#x}")
            print(f"[*] Server public #2: {srv_pub2:#x}")

            # 세션 저장
            self.sessions[session_id] = (dh, session_key)
        except Exception as e:
            print(f"[!] 응답 실패: {e}")
        return

    def handle_handshake_51(self, data: bytes, addr):
        """51B 핸드셰이크 처리 (UDP)."""
        print(f"[*] 51B 핸드셰이크 감지 from {addr}")

        # 고정 DH 키 사용 (클라이언트 캐싱 대응)
        dh = KCPServerUDP._fixed_dh

        try:
            # 0x08: public #1 (8B), 0x10: public #2 (8B)
            pub1 = struct.unpack_from("<Q", data, 0x08)[0]
            pub2 = struct.unpack_from("<Q", data, 0x10)[0]
            print(f"[*] Client public #1: {pub1:#x}")
            print(f"[*] Client public #2: {pub2:#x}")

            # 2중 DH (고정 서버 키 사용)
            secret1 = pow(pub1, dh.private1, 0xFFFFFFFFFFFFFFC5)
            secret2 = pow(pub2, dh.private2, 0xFFFFFFFFFFFFFFC5)
            print(f"[*] Secret #1: {secret1:#x}")
            print(f"[*] Secret #2: {secret2:#x}")

            # 세션 키: LE64(s1) || LE64(s2) (Handshake2 확인)
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
            struct.pack_into("<Q", resp, 0x11, srv_pub2)  # server public #2
            struct.pack_into("<Q", resp, 0x19, srv_pub1)  # server public #1

            self.sock.sendto(bytes(resp), addr)
            print(f"[*] 33B 응답 전송 to {addr}")
            print(f"[*] Session ID: {session_id:#x}")
            print(f"[*] Server public #1: {srv_pub1:#x}")
            print(f"[*] Server public #2: {srv_pub2:#x}")

            # 세션 저장
            self.sessions[session_id] = (dh, session_key)
        except Exception as e:
            print(f"[!] 응답 실패: {e}")
        return

    def handle_kcp_data(self, data: bytes, addr):
        """221B KCP 데이터 패킷 처리 - 구조 분석 우선 (복호화 시도 중단)."""
        session_id = struct.unpack_from("<Q", data, 0x00)[0]
        print(f"[*] 221B 수신: session={session_id:#x} from {addr}")

        # 221B 구조 분석 (원본 훼손 없이)
        print(f"[*] 221B 구조:")
        print(f"    전체: {len(data)}B")
        for offset in [0x00, 0x08, 0x10, 0x18, 0x20, 0x30, 0x40, 0x50]:
            if offset + 16 <= len(data):
                chunk = data[offset:offset+16]
                ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f"    0x{offset:02X}: {chunk.hex()}  |{ascii_repr}|")

        # 16B 배수 검사
        from_0x20 = len(data) - 0x20
        print(f"    0x20~끝: {from_0x20}B, 16의 배수: {from_0x20 % 16 == 0}")

        # 세션 확인만
        if session_id not in self.sessions:
            print(f"[!] 세션 없음: {session_id:#x}")

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

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
from .crypto import aes_encrypt


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
        # KCP RX 상태 (세션별): {"received": set(SN), }
        # - 중복/재전송 판별, 누적 UNA 계산용 (GPT 자문 2026-10-02)
        self.kcp_rx: dict = {}
        # KCP TX 상태 (세션별): {"snd_nxt": int}
        # - 서버→클라이언트 DATA fragment의 SN 공간 (0부터 증가)
        self.kcp_tx: dict = {}
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

            # 2중 DH (크로스 페어링)
            # 33B 응답: 0x11=srv_pub2, 0x19=srv_pub1
            # 클라이언트는 0x11->peer#1, 0x19->peer#2로 읽음
            # 따라서 secret1 = client_pub1 ^ server_private2
            #         secret2 = client_pub2 ^ server_private1
            secret1 = pow(pub1, dh.private2, 0xFFFFFFFFFFFFFFC5)
            secret2 = pow(pub2, dh.private1, 0xFFFFFFFFFFFFFFC5)
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

            # 2중 DH (고정 서버 키 사용, 크로스 페어링)
            # 33B 응답: 0x11=srv_pub2, 0x19=srv_pub1
            # 클라이언트는 0x11->peer#1, 0x19->peer#2로 읽음
            secret1 = pow(pub1, dh.private2, 0xFFFFFFFFFFFFFFC5)
            secret2 = pow(pub2, dh.private1, 0xFFFFFFFFFFFFFFC5)
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
        """221B KCP 데이터 패킷 처리 - 올바른 구조 파싱 및 복호화."""
        session_id = struct.unpack_from("<Q", data, 0x00)[0]
        print(f"[*] 221B 수신: session={session_id:#x} from {addr}")

        # 221B 구조 (GPT 분석 확정):
        # [Session ID 8B][Header 16B][Length 4B][Flag 1B][IV 16B][Ciphertext 176B]
        if len(data) < 0x2D:
            print(f"[!] 패킷이 너무 짧음: {len(data)}B")
            return

        header = data[0x08:0x18]  # 16B
        app_len = struct.unpack_from("<I", data, 0x18)[0]  # 193
        flag = data[0x1C]  # 0x80 = Encrypt, 0x40 = Compress
        iv = data[0x1D:0x1D+16]  # 16B
        ciphertext = data[0x1D+16:]  # 176B

        # KCP 헤더 파싱 (GPT 자문 2026-10-02: SN/UNA는 하드코딩 금지, 수신 헤더에서 추출)
        # [CMD 1B][FRG 1B][WND 2B][TS 4B][SN 4B][UNA 4B] (LE)
        kcp_cmd = header[0x00]
        kcp_frg = header[0x01]
        kcp_wnd = struct.unpack_from("<H", header, 0x02)[0]
        kcp_ts = struct.unpack_from("<I", header, 0x04)[0]
        kcp_sn = struct.unpack_from("<I", header, 0x08)[0]
        kcp_una = struct.unpack_from("<I", header, 0x0C)[0]

        print(f"[*] 221B 구조:")
        print(f"    Session: {session_id:#x}")
        print(f"    Header (16B): {header.hex()}")
        print(f"    KCP: CMD={kcp_cmd:#x} FRG={kcp_frg} WND={kcp_wnd} TS={kcp_ts:#x} SN={kcp_sn} UNA={kcp_una}")

        # KCP RX 상태 업데이트 (세션별)
        rx = self.kcp_rx.setdefault(session_id, {"received": set()})
        is_duplicate = kcp_sn in rx["received"]
        rx["received"].add(kcp_sn)
        # 누적 UNA: 0부터 세어 가장 작은 미수신 SN (KCP cumulative ACK)
        una = self._current_rx_una(session_id)
        if is_duplicate:
            print(f"[*] 중복 패킷 (SN={kcp_sn}), 앱 처리 생략 — ACK만 전송")

        # 즉시 ACK (중복 패킷에도 ACK 전송이 KCP 규칙)
        # 수신 SN을 그대로 ACK하고 UNA는 누적 수신 상태로 계산
        self.send_kcp_ack(session_id, kcp_sn, una, addr)

        if is_duplicate:
            return
        print(f"    App Length: {app_len}")
        print(f"    Flag: {flag:#x} ({'Encrypt' if flag & 0x80 else ''}{'Compress' if flag & 0x40 else ''})")
        print(f"    IV: {iv.hex()}")
        print(f"    Ciphertext: {len(ciphertext)}B (16의 배수: {len(ciphertext) % 16 == 0})")

        # 세션 키 가져오기
        if session_id not in self.sessions:
            print(f"[!] 세션 없음: {session_id:#x}")
            return

        dh, session_key = self.sessions[session_id]
        print(f"[*] 세션 키: {session_key.hex()}")

        # 복호화 시도 (flag 0x80)
        if flag & 0x80:
            try:
                from app.kcp.crypto import aes_decrypt_with_iv
                plaintext = aes_decrypt_with_iv(session_key, iv, ciphertext)
                print(f"[*] 복호화 성공! 평문: {len(plaintext)}B")
                print(f"    평문 전체 hex ({len(plaintext)}B):")
                print(f"    {plaintext.hex()}")
                # printable 확인
                try:
                    text = plaintext.decode('utf-8', errors='strict')
                    print(f"    평문 (utf-8): {text[:200]}")
                except:
                    # 부분 printable
                    printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in plaintext[:200])
                    print(f"    평문 (부분): {printable}")

                # Protobuf 파싱 시도
                print(f"[*] Protobuf 파싱 시도...")
                serial = None
                opcode = None
                try:
                    # 간단한 protobuf wire format 파서
                    pos = 0
                    fields = []
                    while pos < len(plaintext):
                        if pos >= len(plaintext):
                            break
                        tag = plaintext[pos]
                        pos += 1
                        field_num = tag >> 3
                        wire_type = tag & 0x07
                        if wire_type == 0:  # varint
                            val = 0
                            shift = 0
                            while pos < len(plaintext):
                                b = plaintext[pos]
                                pos += 1
                                val |= (b & 0x7F) << shift
                                if not (b & 0x80):
                                    break
                                shift += 7
                            fields.append(f"field {field_num} (varint): {val}")
                            if field_num == 1:
                                serial = val
                            elif field_num == 2:
                                opcode = val
                        elif wire_type == 2:  # length-delimited
                            length = 0
                            shift = 0
                            while pos < len(plaintext):
                                b = plaintext[pos]
                                pos += 1
                                length |= (b & 0x7F) << shift
                                if not (b & 0x80):
                                    break
                                shift += 7
                            data = plaintext[pos:pos+length]
                            pos += length
                            try:
                                s = data.decode('utf-8')
                                fields.append(f"field {field_num} (string): {s[:100]}")
                            except:
                                fields.append(f"field {field_num} (bytes {length}B): {data[:32].hex()}...")
                        else:
                            fields.append(f"field {field_num} (wire_type {wire_type}): skip")
                            break
                    print(f"    Protobuf 필드:")
                    for f in fields[:20]:
                        print(f"      {f}")
                except Exception as e:
                    print(f"    [!] Protobuf 파싱 실패: {e}")

                # Bootstrap probe (실험용):
                # PROBE_MODE="simple": field 1+2만 (7B, 1 fragment)
                # PROBE_MODE="multifrag": 실측과 동일한 조건으로 최소 응답 (12 fragment)
                # PROBE_MODE="real": 실측 protobuf 구조로 실제 Bootstrap 응답 (2026-10-02 15:44)
                #   - field 35=User, field 21=Items, field 43=Chapters 등 실측 태그 사용
                #   - gzip 압축 + flag 0xC4 (실측과 동일)
                #   - 출처: 000192_s2c.bin 분석 (research/reports/2026-10-02-Bootstrap-실측-protobuf-구조_lina.md)
                # 2026-10-02 13:00 관측: multitag 후 클라이언트가 transport ACK조차 안 보냄.
                # 2026-10-02 13:05 GPT 재분석: "protobuf 파서 사망"보다
                # "S→C KCP 세그먼트 자체를 클라이언트 KCP가 거부"가 1순위 가설.
                # (KCP 정상 수신이면 파싱 전에 ACK가 먼저 나와야 함.
                # 12:43에 올바른 28B ACK에도 재전송이 멈추지 않은 것도 같은 맥락 —
                # 33B 핸드셰이크(앱 계층)는 되는데 S→C KCP 세그먼트가 안 받아들여짐.)
                # 파서 예외설은 logcat 확인 전까지 확정하지 않음.
                # 2026-10-02 13:23: 다음 실험 = 실측과 동일한 조건의 최소 응답 (multifrag).
                # 2026-10-02 13:27: multifrag로 transport 개통 확인 (클라이언트 ACK 번들 수신).
                #   다음 = Frida opinfo_dump.js와 함께 multifrag_tag로 태그 매핑.
                # 2026-10-02 13:57: justice_hook_local.js(GPT v4.22+리다이렉트)로 테스트.
                #   KCP Send(OpCode=2)까지 갔으나 게임 크래시. multifrag_tag의 56개 태그가
                #   원인일 수 있어 일단 multifrag(검증됨)로 되돌림.
                # 2026-10-02 14:18: GPT 분석문서에서 OpInfo 전체 메모리 레이아웃 20개 확보.
                #   Frida v5의 BOOT_STATE를 20개 필드로 확장. 태그 매핑을 위해
                #   multifrag_tag로 다시 전환 (한 번에 매핑 시도).
                PROBE_MODE = "real"  # 실측 구조 기반 실제 Bootstrap (2026-10-02 15:44)
                if opcode == 2 and serial is not None:
                    base = self._pb_varint(1, serial) + self._pb_varint(2, 2)
                    flag = 0x84
                    if PROBE_MODE == "multitag":
                        probe = base
                        for f in range(3, 65):
                            if f in (4, 5, 12, 13, 14, 15):
                                continue  # 요청에서 쓰는 태그(문자열)는 제외
                            probe += self._pb_nested(f, b"")
                    elif PROBE_MODE == "multifrag":
                        probe = base
                        while len(probe) < 16384:
                            probe += base
                    elif PROBE_MODE == "real":
                        # 실측 구조 기반 Bootstrap 응답 (2026-10-02 15:44)
                        # 출처: 000192_s2c.bin (gzip 압축 해제 후 protobuf)
                        import gzip
                        # --- User (field 35) ---
                        # 실측: field1=871047(ID), field14='g9in2'(username)
                        user_inner = b""
                        user_inner += self._pb_varint(1, 861197)  # User ID (로컬 계정)
                        user_inner += self._pb_varint(3, 4)
                        user_inner += self._pb_varint(4, 250)
                        user_inner += self._pb_varint(7, 18100000)
                        user_inner += self._pb_string(14, "witchwind3")
                        user_inner += self._pb_varint(20, 3)
                        user_inner += self._pb_varint(21, 3)
                        user_inner += self._pb_varint(22, 10)
                        user_inner += self._pb_varint(24, 1)
                        # --- Items (field 21, 반복) ---
                        # 실측: 276개, 각 {field1=ID, field2=count}
                        items_part = b""
                        # 테스트용 최소 아이템 5개
                        for item_id in [21000010, 21000020, 21000030, 21000040, 21000050]:
                            item_inner = self._pb_varint(1, item_id) + self._pb_varint(2, 1)
                            items_part += self._pb_nested(21, item_inner)
                        # --- Chapters (field 43, 반복) ---
                        # 실측: 61개
                        chapters_part = b""
                        # 테스트용 최소 챕터 3개
                        for ch_id in [20000100, 20000200, 20000300]:
                            ch_inner = self._pb_varint(1, ch_id) + self._pb_varint(2, 0)
                            chapters_part += self._pb_nested(43, ch_inner)
                        # --- 조립 ---
                        probe = base  # field 1 (serial) + field 2 (opcode=2)
                        probe += self._pb_nested(35, user_inner)
                        probe += items_part
                        probe += chapters_part
                        # gzip 압축 (실측과 동일)
                        probe_compressed = gzip.compress(probe)
                        print(f"    [real] protobuf {len(probe)}B → gzip {len(probe_compressed)}B")
                        probe = probe_compressed
                        flag = 0xC4  # 압축 플래그 (실측과 동일)
                    elif PROBE_MODE == "multifrag_tag":
                        # TAG_RANGE 환경변수로 태그 구간 지정 (이분 탐색용)
                        # 예: TAG_RANGE="3-20", TAG_RANGE="21-40", TAG_RANGE="41-64"
                        # 미지정시 전체 3~64
                        import os
                        tag_range = os.environ.get("TAG_RANGE", "3-64")
                        try:
                            rs, re_ = tag_range.split("-")
                            r_start, r_end = int(rs), int(re_)
                        except:
                            r_start, r_end = 3, 64
                        print(f"    [태그구간] field {r_start}~{r_end}")
                        unit = base
                        for f in range(r_start, r_end + 1):
                            if f in (4, 5, 12, 13, 14, 15):
                                continue
                            unit += self._pb_nested(f, b"")
                        probe = unit
                        while len(probe) < 16384:
                            probe += unit
                    else:  # simple
                        probe = base
                    print(f"[*] Bootstrap probe 전송 [{PROBE_MODE}] (serial={serial}, {len(probe)}B)")
                    self.send_kcp_message(session_id, flag, probe, addr)
            except Exception as e:
                print(f"[!] 복호화 실패: {e}")
        else:
            print(f"[*] 암호화 플래그 없음, 평문으로 처리")

    @staticmethod
    def _pb_varint(field_no: int, value: int) -> bytes:
        """최소 protobuf varint 필드 인코더 (tag wire_type=0)."""
        out = bytearray()
        out.append((field_no << 3) | 0)
        v = value
        while True:
            b = v & 0x7F
            v >>= 7
            if v:
                out.append(b | 0x80)
            else:
                out.append(b)
                break
        return bytes(out)

    @staticmethod
    def _pb_string(field_no: int, s: str) -> bytes:
        """string 필드 인코더 (wire type 2)."""
        return KCPServerUDP._pb_nested(field_no, s.encode('utf-8'))

    @staticmethod
    def _pb_nested(field_no: int, payload: bytes) -> bytes:
        """length-delimited 필드 인코더 (nested message / string / bytes)."""
        out = bytearray()
        tag = (field_no << 3) | 2
        while True:
            b = tag & 0x7F
            tag >>= 7
            if tag:
                out.append(b | 0x80)
            else:
                out.append(b)
                break
        ln = len(payload)
        while True:
            b = ln & 0x7F
            ln >>= 7
            if ln:
                out.append(b | 0x80)
            else:
                out.append(b)
                break
        out += payload
        return bytes(out)

    def _current_rx_una(self, session_id: int) -> int:
        """세션의 현재 누적 UNA (0부터 세어 가장 작은 미수신 SN)."""
        rx = self.kcp_rx.get(session_id, {"received": set()})
        una = 0
        for s in sorted(rx["received"]):
            if s == una:
                una += 1
            elif s > una:
                break
        return una

    def send_kcp_message(self, session_id: int, flag: int, plaintext: bytes, addr):
        """앱 메시지 1개를 AES 암호화 → KCP fragment들로 분할 전송 (S→C).
        실측 구조 (어플시작_로그인까지.json frame 177-187):
        - fragment: [Session 8B][KCP 16B][ChunkLen 4B][chunk]
        - chunk들을 frg 내림차순으로 이으면 [Flag 1B][IV 16B][Ciphertext]
        - SN은 서버 TX 공간에서 0부터 증가, frg=N-1..0, chunk ≤1372B
        - WND=32, UNA=현재 RX 누적값, 한 메시지의 TS는 동일
        """
        import os
        import time
        if session_id not in self.sessions:
            print(f"[!] 세션 없음, 전송 생략: {session_id:#x}")
            return
        tx = self.kcp_tx.setdefault(session_id, {"snd_nxt": 0})
        _, session_key = self.sessions[session_id]

        iv = os.urandom(16)
        enc = aes_encrypt(session_key, plaintext, iv)  # [IV 16B][ciphertext]
        msg = bytes([flag]) + enc

        # === 자가검증: 서버가 보낸 암호문을 서버가 직접 복호화 ===
        # 클라이언트 없이 crypto 경로 검증 (2026-10-02)
        try:
            from app.kcp.crypto import aes_decrypt
            # enc = [IV 16B][ciphertext] (aes_encrypt가 IV를 앞에 붙여서 반환)
            dec_plain = aes_decrypt(session_key, enc)
            if dec_plain == plaintext:
                print(f"    [자가검증] 복호화 성공 ({len(plaintext)}B 일치)")
            else:
                print(f"    [자가검증] ⚠ 복호화 불일치! 원본={len(plaintext)}B 복호={len(dec_plain)}B")
        except Exception as e:
            print(f"    [자가검증] ⚠ 복호화 실패: {e}")

        CHUNK = 1372
        chunks = [msg[i:i + CHUNK] for i in range(0, len(msg), CHUNK)]
        n = len(chunks)
        una = self._current_rx_una(session_id)
        ts = int(time.time() * 1000) & 0xFFFFFFFF

        for i, chunk in enumerate(chunks):
            sn = tx["snd_nxt"]
            tx["snd_nxt"] += 1
            frg = n - 1 - i
            seg = bytearray(24 + 4 + len(chunk))
            struct.pack_into("<Q", seg, 0, session_id)
            seg[8] = 0x51  # CMD = DATA
            seg[9] = frg
            struct.pack_into("<H", seg, 10, 32)  # WND (실측값)
            struct.pack_into("<I", seg, 12, ts)
            struct.pack_into("<I", seg, 16, sn)
            struct.pack_into("<I", seg, 20, una)
            struct.pack_into("<I", seg, 24, len(chunk))
            seg[28:] = chunk
            self.sock.sendto(bytes(seg), addr)
            print(f"[*] KCP DATA 전송: SN={sn} FRG={frg} chunk={len(chunk)}B to {addr}")
        print(f"[*] 메시지 전송 완료: {n}개 fragment, 총 {len(msg)}B")

    def send_kcp_ack(self, session_id: int, sn: int, una: int, addr):
        """28B KCP ACK 전송 (GPT 분석: 2026-10-02).
        구조: [Session 8B][0x52][0x00][Window 2B][Timestamp 4B][SN 4B][UNA 4B][Reserved 4B]
        SN/UNA는 하드코딩 금지 — 수신 KCP 헤더 + 세션 RX 상태에서 도출.
        """
        try:
            import time
            ack = bytearray(28)
            struct.pack_into("<Q", ack, 0x00, session_id)  # Session ID
            ack[0x08] = 0x52  # KCP ACK command
            ack[0x09] = 0x00  # Fragment
            # Window: 실제 서버 raw 바이트 = 1f 00 (LE uint16 = 31)
            # 주의: 0x1F00으로 pack하면 raw가 00 1f가 되어 클라이언트가 ACK를 무시함
            struct.pack_into("<H", ack, 0x0A, 31)  # Window = 31 (LE)
            # Timestamp: 현재 시간 (ms의 하위 32비트)
            ts = int(time.time() * 1000) & 0xFFFFFFFF
            struct.pack_into("<I", ack, 0x0C, ts)
            struct.pack_into("<I", ack, 0x10, sn)  # ACK 대상 SN (수신 패킷의 SN)
            struct.pack_into("<I", ack, 0x14, una)  # UNA (누적 확인)
            struct.pack_into("<I", ack, 0x18, 0)  # Reserved

            self.sock.sendto(bytes(ack), addr)
            print(f"[*] 28B KCP ACK 전송 to {addr}")
            print(f"    ACK: session={session_id:#x}, SN={sn}, UNA={una}")
            print(f"    ACK raw: {bytes(ack).hex()}")
        except Exception as e:
            print(f"[!] ACK 전송 실패: {e}")

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

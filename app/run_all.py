"""HTTP + UDP KCP 서버를 하나의 프로세스로 실행.

사용법:
    set LINA_HOST=10.87.155.119
    python -m app.run_all

또는:
    python -m app.run_all --host 10.87.155.119 --http-port 8888 --udp-port 8000
"""
import argparse
import os
import threading
import sys


def main():
    parser = argparse.ArgumentParser(description="JusticeSchool 로컬 서버 (HTTP + UDP)")
    parser.add_argument("--host", default="0.0.0.0", help="바인드 주소 (기본: 0.0.0.0)")
    parser.add_argument("--http-port", type=int, default=8888, help="HTTP 포트 (기본: 8888)")
    parser.add_argument("--udp-port", type=int, default=8000, help="UDP 포트 (기본: 8000)")
    parser.add_argument("--lina-host", default=None, help="LINA_HOST (클라이언트에 알려줄 서버 주소)")
    args = parser.parse_args()

    # LINA_HOST 설정 (인자가 있으면 환경변수보다 우선)
    if args.lina_host:
        os.environ["LINA_HOST"] = args.lina_host

    lina_host = os.environ.get("LINA_HOST", "(미설정)")
    print(f"[*] LINA_HOST: {lina_host}")
    print(f"[*] HTTP: {args.host}:{args.http_port}")
    print(f"[*] UDP: {args.host}:{args.udp_port}")
    print(f"[*] 종료: CTRL+C")
    print()

    # UDP KCP 서버를 백그라운드 스레드로 시작
    from app.kcp.server_udp import KCPServerUDP

    udp_server = KCPServerUDP(host=args.host, port=args.udp_port)
    udp_thread = threading.Thread(target=udp_server.start, daemon=True, name="UDP-KCP")
    udp_thread.start()
    print(f"[*] UDP KCP 서버 스레드 시작")

    # HTTP 서버를 메인 스레드에서 실행 (uvicorn)
    import uvicorn
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.http_port,
            log_level="warning",  # 로그 간소화
        )
    except KeyboardInterrupt:
        print("\n[*] 종료 중...")
    finally:
        udp_server.stop()


if __name__ == "__main__":
    main()

"""서버 설정."""
import os

HOST = os.getenv("LINA_HOST", "127.0.0.1")
PORT = int(os.getenv("LINA_PORT", "8080"))

# 클라이언트 버전 (GetDefaultParams의 v와 일치해야 함)
APP_VERSION = "3.1.0"

# 로그인 content (Frida 캡처에서 확인된 고정 MD5)
# 실제 content 구조가 확정되면 여기를 갱신
LOGIN_CONTENT = "90f04cb7a1fa5c2f58ca19cde2a2b128"

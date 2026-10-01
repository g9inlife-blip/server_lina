// 토큰 길이 캡처용 (운영 서버)
// justice_hook.js의 SaveLoginToken 후크를 단순화

'use strict';

console.log("[*] 토큰 길이 캡처 시작");

// justice_hook.js의 헬퍼 함수들 필요
// 간단히: HTTP 응답에서 Token 필드 파싱

// UnityWebRequest 후킹으로 로그인 응답 캡처
let libil2cppBase = null;

function findLibil2cpp() {
    const modules = Process.enumerateModules();
    for (let m of modules) {
        if (m.name === 'libil2cpp.so') {
            return m.base;
        }
    }
    // /proc/self/maps에서 찾기
    try {
        const maps = File.readAllText('/proc/self/maps');
        for (let line of maps.split('\n')) {
            if (line.includes('libil2cpp.so')) {
                const addr = line.split('-')[0];
                return ptr(addr);
            }
        }
    } catch (e) {}
    return null;
}

// 간단한 방법: HTTP 응답 바디에서 "Token" 찾기
// UploadHandler 데이터를 후킹

console.log("[*] 수동 방법: 게임 로그인 후 HTTP 응답 확인");
console.log("[*] 또는 justice_capture.js 사용");

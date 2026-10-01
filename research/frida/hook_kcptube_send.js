/**
 * KCPTube.Send 후킹 - 암호화 전 평문 확인
 * 
 * Ghidra: KCPTube$$Send @ 015aeddc
 * Send(request) -> ProtoBuf.Serialize -> EncryptUnSafe -> KCP.Send
 * 
 * Send의 인자를 확인해서 어떤 request가 전송되는지 파악
 */

'use strict';

console.log("[*] KCPTube.Send 후킹 스크립트");

// libil2cpp base 찾기
function findLibil2cppBase() {
    // /proc/self/maps에서 찾기
    try {
        const maps = File.readAllText('/proc/self/maps');
        for (let line of maps.split('\n')) {
            if (line.includes('libil2cpp.so')) {
                const addr = line.split('-')[0].trim();
                console.log("[*] libil2cpp.so: " + addr);
                return ptr(addr);
            }
        }
    } catch (e) {
        console.log("[!] maps 읽기 실패: " + e);
    }
    return null;
}

function readIl2cppString(ptr) {
    if (ptr.isNull()) return '(null)';
    try {
        const len = ptr.add(16).readInt();
        if (len < 0 || len > 10000) return '(invalid len:' + len + ')';
        return ptr.add(20).readUtf16String(len);
    } catch (e) {
        return '(read failed)';
    }
}

const base = findLibil2cppBase();
if (base) {
    // KCPTube.Send @ 015aeddc (RVA)
    // 주의: RVA가 버전마다 다를 수 있음
    const sendRva = ptr('0x15aeddc');
    const sendAddr = base.add(sendRva);
    
    console.log("[*] KCPTube.Send 후킹: " + sendAddr);
    
    try {
        Interceptor.attach(sendAddr, {
            onEnter(args) {
                console.log("\n========== KCPTube.Send called ==========");
                console.log("  this (x0): " + args[0]);
                console.log("  request (x1): " + args[1]);
                
                // request 객체의 타입 확인 시도
                try {
                    const reqPtr = args[1];
                    if (!reqPtr.isNull()) {
                        const klass = reqPtr.readPointer();
                        console.log("  request klass: " + klass);
                        // TODO: 클래스명 읽기
                    }
                } catch (e) {
                    console.log("  request 읽기 실패: " + e.message);
                }
            }
        });
        console.log("[+] 후킹 성공");
    } catch (e) {
        console.log("[!] 후킹 실패: " + e.message);
        console.log("[!] RVA가 틀렸을 수 있음. Ghidra에서 확인 필요.");
    }
} else {
    console.log("[!] libil2cpp.so를 찾지 못함");
}

// 실제 서버 로그인 토큰 캡처용
// 운영 서버용 (리다이렉트 OFF)

console.log("[*] 토큰 캡처 스크립트 시작");

// LoginManager.SaveLoginToken 후킹
function hookSaveToken() {
    try {
        // IL2CPP API로 메서드 찾기
        const domain = Il2Cpp.Domain.Get();
        const assemblies = domain.Assemblies;

        for (let asm of assemblies) {
            if (asm.Name.includes("Assembly-CSharp")) {
                const loginManager = asm.GetType("LoginManager");
                if (loginManager) {
                    const saveToken = loginManager.GetMethod("SaveLoginToken");
                    if (saveToken) {
                        console.log("[*] SaveLoginToken 찾음");
                        Interceptor.attach(saveToken.VirtualAddress, {
                            onEnter(args) {
                                // 첫 번째 인자가 토큰 문자열
                                const token = args[1];
                                if (token && !token.isNull()) {
                                    const str = token.readUtf16String();
                                    console.log("[TOKEN] 길이: " + str.length);
                                    console.log("[TOKEN] 값: " + str.substring(0, 100));
                                    if (str.length > 100) {
                                        console.log("[TOKEN] 전체: " + str);
                                    }
                                }
                            }
                        });
                        return true;
                    }
                }
            }
        }
    } catch (e) {
        console.log("[!] 후킹 실패: " + e);
    }
    return false;
}

// 도메인 준비 대기
let attempts = 0;
const timer = setInterval(() => {
    attempts++;
    if (hookSaveToken() || attempts > 30) {
        clearInterval(timer);
        if (attempts > 30) {
            console.log("[!] SaveLoginToken을 찾지 못함");
        }
    }
}, 1000);

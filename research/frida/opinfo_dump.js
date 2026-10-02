/**
 * OpInfo 필드 덤프 스크립트 (JusticeSchool)
 *
 * 목적: 서버의 multi-tag probe를 받은 뒤 DataCenter.ProccessRequestRes에
 * 전달된 OpInfo 객체의 필드 목록(이름 + null 여부)을 덤프.
 * 서버가 보낸 태그 중 어떤 것이 실제 OpInfo 필드로 인식됐는지 확인용.
 *
 * 사용법 (폰, proot Ubuntu):
 *   frida -H 127.0.0.1:27042 -n Gadget -l research/frida/opinfo_dump.js
 *   → 게임에서 로그인 → 서버 probe 수신 → [OPINFO_DUMP] 로그 확인
 *
 * v4 스타일: frida-il2cpp-bridge 없이 직접 IL2CPP API 호출.
 */
'use strict';

const LIB_NAME = 'libil2cpp.so';
let api = null;

function exp(name) {
    const mods = Process.enumerateModules();
    for (const m of mods) {
        if (m.name === LIB_NAME) {
            const e = m.getExportByName(name);
            if (!e.isNull()) return e;
        }
    }
    // fallback: 전역에서 찾기
    const g = DebugSymbol.fromName(name);
    if (g && !g.address.isNull()) return g.address;
    return null;
}

function initApi() {
    api = {
        domain_get: new NativeFunction(exp('il2cpp_domain_get'), 'pointer', []),
        domain_get_assemblies: new NativeFunction(exp('il2cpp_domain_get_assemblies'), 'pointer', ['pointer', 'pointer']),
        assembly_get_image: new NativeFunction(exp('il2cpp_assembly_get_image'), 'pointer', ['pointer']),
        image_get_name: new NativeFunction(exp('il2cpp_image_get_name'), 'pointer', ['pointer']),
        class_from_name: new NativeFunction(exp('il2cpp_class_from_name'), 'pointer', ['pointer', 'pointer', 'pointer']),
        class_get_name: new NativeFunction(exp('il2cpp_class_get_name'), 'pointer', ['pointer']),
        class_get_fields: new NativeFunction(exp('il2cpp_class_get_fields'), 'pointer', ['pointer', 'pointer']),
        field_get_name: new NativeFunction(exp('il2cpp_field_get_name'), 'pointer', ['pointer']),
        field_get_offset: new NativeFunction(exp('il2cpp_field_get_offset'), 'uint32', ['pointer']),
        field_get_type: new NativeFunction(exp('il2cpp_field_get_type'), 'pointer', ['pointer']),
        type_get_name: new NativeFunction(exp('il2cpp_type_get_name'), 'pointer', ['pointer']),
        object_get_class: new NativeFunction(exp('il2cpp_object_get_class'), 'pointer', ['pointer']),
        method_get_name: new NativeFunction(exp('il2cpp_method_get_name'), 'pointer', ['pointer']),
        class_get_methods: new NativeFunction(exp('il2cpp_class_get_methods'), 'pointer', ['pointer', 'pointer']),
        method_get_param_count: new NativeFunction(exp('il2cpp_method_get_param_count'), 'uint32', ['pointer']),
    };
}

function cstr(ptr) {
    if (ptr.isNull()) return '(null)';
    try { return ptr.readUtf8String(); } catch (e) { return `(unreadable)`; }
}

// 모든 어셈블리에서 클래스 이름으로 찾기
function findClass(className) {
    const domain = api.domain_get();
    const sizePtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, sizePtr);
    const count = sizePtr.readU32();
    for (let i = 0; i < count; i++) {
        const asm = assemblies.add(i * Process.pointerSize).readPointer();
        const img = api.assembly_get_image(asm);
        // 네임스페이스 "" 로 시도 (대부분 게임 코드는 global namespace 또는 특정 ns)
        const klass = api.class_from_name(img, Memory.allocUtf8String(''), Memory.allocUtf8String(className));
        if (!klass.isNull()) {
            console.log(`[OPINFO] 클래스 발견: ${className} (image: ${cstr(api.image_get_name(img))})`);
            return klass;
        }
    }
    return ptr(0);
}

// 클래스에서 메서드 이름으로 찾기
function findMethod(klass, methodName) {
    const iter = Memory.alloc(Process.pointerSize);
    iter.writePointer(ptr(0));
    while (true) {
        const m = api.class_get_methods(klass, iter);
        if (m.isNull()) break;
        const name = cstr(api.method_get_name(m));
        if (name === methodName) return m;
    }
    return ptr(0);
}

// 객체의 모든 필드 덤프 (이름 + null 여부 + 타입명)
function dumpObjectFields(objPtr, label) {
    try {
        if (objPtr.isNull()) {
            console.log(`[OPINFO_DUMP] ${label}: (null object)`);
            return;
        }
        const klass = api.object_get_class(objPtr);
        const className = cstr(api.class_get_name(klass));
        console.log(`[OPINFO_DUMP] ${label}: class=${className}`);
        const iter = Memory.alloc(Process.pointerSize);
        iter.writePointer(ptr(0));
        let idx = 0;
        while (true) {
            const field = api.class_get_fields(klass, iter);
            if (field.isNull()) break;
            const fname = cstr(api.field_get_name(field));
            const ftype = cstr(api.type_get_name(api.field_get_type(field)));
            const offset = api.field_get_offset(field);
            let valInfo = '';
            try {
                // 참조 타입이면 포인터 읽기 (값 타입은 스킵)
                if (ftype.indexOf('*') >= 0 || ftype.indexOf('string') >= 0 ||
                    ftype.charAt(0) === ftype.charAt(0).toUpperCase()) {
                    const valPtr = objPtr.add(offset).readPointer();
                    valInfo = valPtr.isNull() ? 'null' : `non-null (${valPtr})`;
                } else {
                    valInfo = `(valuetype, offset=${offset})`;
                }
            } catch (e) { valInfo = `(read fail)`; }
            console.log(`[OPINFO_DUMP]   field[${idx}] ${fname} : ${ftype} = ${valInfo}`);
            idx++;
            if (idx > 100) { console.log(`[OPINFO_DUMP]   ... (100개 초과, 중단)`); break; }
        }
        console.log(`[OPINFO_DUMP] ${label}: 총 ${idx}개 필드`);
    } catch (e) {
        console.log(`[OPINFO_DUMP] 덤프 실패: ${e.message}`);
    }
}

function main() {
    initApi();
    console.log('[OPINFO] 시작');

    // DataCenter 클래스 찾기
    const dcClass = findClass('DataCenter');
    if (dcClass.isNull()) {
        console.log('[OPINFO] DataCenter 클래스를 못 찾음. 어셈블리 목록 출력:');
        const domain = api.domain_get();
        const sizePtr = Memory.alloc(Process.pointerSize);
        const assemblies = api.domain_get_assemblies(domain, sizePtr);
        const count = Math.min(sizePtr.readU32(), 30);
        for (let i = 0; i < count; i++) {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            console.log(`[OPINFO]   image: ${cstr(api.image_get_name(img))}`);
        }
        return;
    }

    // ProccessRequestRes 메서드 찾기 (이름 오타 주의: Proccess)
    const method = findMethod(dcClass, 'ProccessRequestRes');
    if (method.isNull()) {
        console.log('[OPINFO] ProccessRequestRes 메서드를 못 찾음. 메서드 목록:');
        const iter = Memory.alloc(Process.pointerSize);
        iter.writePointer(ptr(0));
        let c = 0;
        while (c < 50) {
            const m = api.class_get_methods(dcClass, iter);
            if (m.isNull()) break;
            console.log(`[OPINFO]   method: ${cstr(api.method_get_name(m))} (params=${api.method_get_param_count(m)})`);
            c++;
        }
        return;
    }
    console.log('[OPINFO] ProccessRequestRes 찾음, 후킹');

    Interceptor.attach(method, {
        onEnter(args) {
            // args[0]=this, args[1]=첫 번째 인자(OpInfo로 추정)
            try {
                const paramCount = api.method_get_param_count(method);
                console.log(`[OPINFO] ProccessRequestRes 호출됨 (params=${paramCount})`);
                if (paramCount >= 1) {
                    const opInfo = args[1];
                    dumpObjectFields(opInfo, 'ProccessRequestRes arg');
                }
            } catch (e) {
                console.log(`[OPINFO] 후크 오류: ${e.message}`);
            }
        }
    });
    console.log('[OPINFO] 후킹 완료. 게임에서 로그인하면 덤프됨.');
}

try {
    main();
} catch (e) {
    console.log(`[OPINFO] 초기화 실패: ${e.message}\n${e.stack}`);
}

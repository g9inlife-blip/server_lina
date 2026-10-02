/**
 * OpInfo 필드 덤프 스크립트 (JusticeSchool)
 *
 * 목적: 서버의 multi-tag probe를 받은 뒤 DataCenter.ProccessRequestRes에
 * 전달된 OpInfo 객체의 필드 목록(이름 + null 여부)을 덤프.
 * 서버가 보낸 태그 중 어떤 것이 실제 OpInfo 필드로 인식됐는지 확인용.
 *
 * 사용법 (폰, proot Ubuntu):
 *   frida -H 127.0.0.1:27042 -n Gadget -l research/frida/justice_hook.js -l research/frida/opinfo_dump.js
 *   (justice_hook.js의 URL 리다이렉트와 함께 로드해야 로컬 서버로 연결됨.
 *    IIFE로 감싸서 전역 충돌 없음.)
 *   → 게임에서 로그인 → 서버 probe 수신 → [OPINFO_DUMP] 로그 확인
 *
 * v4.10.1: justice_hook.js v4.10의 검증된 IL2CPP 초기화 블록을 그대로 사용.
 * (이전 버전은 enumerateModules 기반 exp()를 새로 짜서 터졌음 — 2026-10-02)
 */
'use strict';
(function() {

const LIB_NAME = 'libil2cpp.so';

// ---------- ELF-based export resolution (justice_hook.js v4.10에서 그대로 복사) ----------
// Finds the module base via /proc/self/maps and resolves dynamic
// symbols by parsing the ELF file directly.

function findModuleBase(libFileName) {
    const maps = File.readAllText('/proc/self/maps');
    for (const line of maps.split('\n')) {
        if (line.indexOf(libFileName) === -1) continue;
        // format: addr_start-addr_end perms offset dev inode pathname
        const parts = line.trim().split(/\s+/);
        if (parts.length < 6) continue;
        const range = parts[0].split('-');
        const offset = parts[2];
        if (offset === '00000000' && parts[1].indexOf('r') === 0) {
            return { base: ptr('0x' + range[0]), path: parts[5] };
        }
    }
    return null;
}

function resolveElfExport(modulePath, baseAddr, symbolName) {
    const buf = File.readAllBytes(modulePath);
    const dv = new DataView(buf);
    const u8 = new Uint8Array(buf);

    function u16(off) { return dv.getUint16(off, true); }
    function u32(off) { return dv.getUint32(off, true); }
    function u64(off) { return Number(dv.getBigUint64(off, true)); }

    // ELF header
    if (u32(0) !== 0x464C457F) throw new Error('not an ELF file');
    const e_phoff = u64(0x20);
    const e_phnum = u16(0x38);

    // Collect PT_LOAD segments for vaddr -> file offset translation,
    // and locate PT_DYNAMIC.
    const loads = [];
    let dynOff = -1, dynSize = 0;
    for (let i = 0; i < e_phnum; i++) {
        const ph = e_phoff + i * 56;
        const p_type = u32(ph);
        const p_offset = u64(ph + 8);
        const p_vaddr = u64(ph + 16);
        const p_filesz = u64(ph + 32);
        if (p_type === 1) { // PT_LOAD
            loads.push({ vaddr: p_vaddr, offset: p_offset, filesz: p_filesz });
        } else if (p_type === 2) { // PT_DYNAMIC
            dynOff = p_offset;
            dynSize = p_filesz;
        }
    }
    if (dynOff < 0) throw new Error('no PT_DYNAMIC');

    function vaddrToOffset(vaddr) {
        for (const s of loads) {
            if (vaddr >= s.vaddr && vaddr < s.vaddr + s.filesz) {
                return s.offset + (vaddr - s.vaddr);
            }
        }
        return -1;
    }

    // Parse dynamic entries
    let symtabV = 0, strtabV = 0, strsz = 0, syment = 24;
    for (let off = dynOff; off < dynOff + dynSize; off += 16) {
        const tag = dv.getBigInt64(off, true);
        const val = u64(off + 8);
        if (tag === 6n) symtabV = val;          // DT_SYMTAB
        else if (tag === 5n) strtabV = val;     // DT_STRTAB
        else if (tag === 10n) strsz = val;      // DT_STRSZ
        else if (tag === 11n) syment = val;     // DT_SYMENT
        else if (tag === 0n) break;             // DT_NULL
    }
    if (!symtabV || !strtabV || !strsz) throw new Error('missing dynamic info');

    const symtabOff = vaddrToOffset(symtabV);
    const strtabOff = vaddrToOffset(strtabV);
    if (symtabOff < 0 || strtabOff < 0) throw new Error('vaddr translation failed');

    function readCString(off) {
        let end = off;
        while (end < u8.length && u8[end] !== 0) end++;
        let s = '';
        for (let i = off; i < end; i++) s += String.fromCharCode(u8[i]);
        return s;
    }

    // Linear scan of dynamic symbols
    const maxSyms = 200000;
    for (let i = 0; i < maxSyms; i++) {
        const so = symtabOff + i * syment;
        if (so + 24 > u8.length) break;
        const st_name = u32(so);
        const st_value = u64(so + 8);
        if (st_name === 0 || st_value === 0) continue;
        if (st_name >= strsz) continue;
        const name = readCString(strtabOff + st_name);
        if (name === symbolName) {
            return baseAddr.add(st_value);
        }
        // Heuristic stop: after the null-heavy tail begins we keep going a bit
        if (i > 0 && st_name === 0 && st_value === 0 && i > 50000) break;
    }
    return ptr(0);
}

// ---------- raw IL2CPP API (justice_hook.js v4.10 패턴, 필요한 것만 추가) ----------

let api = null;
let il2cppBase = null;

function initApi() {
    const mod = findModuleBase(LIB_NAME);
    if (!mod) throw new Error(LIB_NAME + ' not found in /proc/self/maps');
    il2cppBase = mod.base;
    console.log(`[OPINFO] ${LIB_NAME} base @ ${il2cppBase} (${mod.path})`);

    const exp = (n) => {
        const addr = resolveElfExport(mod.path, mod.base, n);
        if (addr.isNull()) throw new Error('export not found: ' + n);
        return addr;
    };
    api = {
        domain_get: new NativeFunction(exp('il2cpp_domain_get'), 'pointer', []),
        domain_get_assemblies: new NativeFunction(exp('il2cpp_domain_get_assemblies'), 'pointer', ['pointer', 'pointer']),
        assembly_get_image: new NativeFunction(exp('il2cpp_assembly_get_image'), 'pointer', ['pointer']),
        image_get_name: new NativeFunction(exp('il2cpp_image_get_name'), 'pointer', ['pointer']),
        class_from_name: new NativeFunction(exp('il2cpp_class_from_name'), 'pointer', ['pointer', 'pointer', 'pointer']),
        class_get_name: new NativeFunction(exp('il2cpp_class_get_name'), 'pointer', ['pointer']),
        class_get_fields: new NativeFunction(exp('il2cpp_class_get_fields'), 'pointer', ['pointer', 'pointer']),
        class_get_methods: new NativeFunction(exp('il2cpp_class_get_methods'), 'pointer', ['pointer', 'pointer']),
        field_get_name: new NativeFunction(exp('il2cpp_field_get_name'), 'pointer', ['pointer']),
        field_get_offset: new NativeFunction(exp('il2cpp_field_get_offset'), 'uint32', ['pointer']),
        field_get_type: new NativeFunction(exp('il2cpp_field_get_type'), 'pointer', ['pointer']),
        type_get_name: new NativeFunction(exp('il2cpp_type_get_name'), 'pointer', ['pointer']),
        object_get_class: new NativeFunction(exp('il2cpp_object_get_class'), 'pointer', ['pointer']),
        method_get_name: new NativeFunction(exp('il2cpp_method_get_name'), 'pointer', ['pointer']),
        method_get_param_count: new NativeFunction(exp('il2cpp_method_get_param_count'), 'uint32', ['pointer']),
    };
    console.log('[OPINFO] IL2CPP API 초기화 완료');
}

function cstr(ptr) {
    if (ptr.isNull()) return '(null)';
    try { return ptr.readUtf8String(); } catch (e) { return `(unreadable)`; }
}

// 모든 어셈블리에서 클래스 이름으로 찾기
function findClass(className) {
    const domain = api.domain_get();
    if (domain.isNull()) { console.log('[OPINFO] domain이 null'); return ptr(0); }
    const sizePtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, sizePtr);
    const count = sizePtr.readU32();
    console.log(`[OPINFO] 어셈블리 ${count}개 검색 중...`);
    for (let i = 0; i < count; i++) {
        const asm = assemblies.add(i * Process.pointerSize).readPointer();
        if (asm.isNull()) continue;
        const img = api.assembly_get_image(asm);
        if (img.isNull()) continue;
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
            if (asm.isNull()) continue;
            const img = api.assembly_get_image(asm);
            if (img.isNull()) continue;
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

})();

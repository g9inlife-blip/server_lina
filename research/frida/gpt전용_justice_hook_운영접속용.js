/**
 * JusticeSchool (com.Alioth.JusticeSchool.cn) - Login Hook Script v4.22
 *
 * v4.9: NetworkCenter/DataCenter response-path observation added.\n * v4.8: ProtoChapter BoxStatus runtime read/write observation added.\n * v4.7: UploadHandlerRaw / UnityWebRequest setter / HttpRequest body 생성 경로 추적 + token 저장/재사용 fingerprint 비교
 *
 * NO frida-il2cpp-bridge, NO frida-compile needed.
 * Resolves IL2CPP exports by parsing /proc/self/maps + ELF directly,
 * because Frida's module enumeration misses Houdini-translated ARM libs
 * on x86_64 emulators.
 *
 * Hooks:
 *  - ProtocolGame_HttpRequest.V4_POST_Login(app_key, content, apiName)
 *  - ProtocolGame_HttpRequest.Sign(content, apiName)
 *  - ProtocolGame_HttpRequest.GetDefaultParams()
 *  - ProtocolGame_HttpRequest.V3_POST_AllInOne(app_key)
 *  - UnityEngine.Networking.UnityWebRequest constructor / SetRequestHeader / SendWebRequest
 *  - UnityEngine.Networking.UploadHandler.get_data (Send 시 POST body 확인)
 *  - UnityEngine.Networking.UploadHandlerRaw(byte[]) (실제 POST body 생성 시점)
 *  - UnityEngine.Networking.UnityWebRequest.set_uploadHandler / set_method
 *  - AliothEngine.Net.HttpRequest method inventory (body/request 생성 경로 확인)
 *
 * Usage:
 *   frida -U -p <PID> -l justice_hook.js
 *   (attach AFTER the game has loaded the Unity engine)
 *
 * Output: [SIGN_DATA] lines carry Sign input/output pairs for
 *         reverse-engineering the signature algorithm.
 */

'use strict';

// Parameter names (from static analysis, NEWVERSION-003)
const PARAMS = {
    'V4_POST_Login': ['app_key', 'content', 'apiName'],
    'Sign': ['content', 'apiName'],
    'GetDefaultParams': [],
    'V3_POST_AllInOne': ['app_key'],
};
const CLASS_NAME = 'ProtocolGame_HttpRequest';
const LIB_NAME = 'libil2cpp.so';

// ---------- helpers ----------

// Log reduction: suppress unchanged state and aggregate high-frequency callbacks.
const _logStateCache = Object.create(null);
const _logRateState = Object.create(null);

function logOnChange(key, value, message) {
    const normalized = String(value);
    if (_logStateCache[key] === normalized) return false;
    _logStateCache[key] = normalized;
    console.log(message);
    return true;
}

function logThrottled(key, intervalMs, message) {
    const now = Date.now();
    let state = _logRateState[key];
    if (!state) state = _logRateState[key] = { last: 0, suppressed: 0 };
    if (now - state.last >= intervalMs) {
        const suffix = state.suppressed ? ' (+' + state.suppressed + ' repeats suppressed)' : '';
        console.log(message + suffix);
        state.last = now;
        state.suppressed = 0;
    } else {
        state.suppressed++;
    }
}


function readIl2cppString(ptr) {
    if (ptr.isNull()) return '(null)';
    try {
        // Validate pointer is readable
        const klass = ptr.readPointer();
        if (klass.isNull()) return '(invalid klass)';
        // Il2CppString (64-bit): [klass(8)][monitor(8)][length(4)][chars...]
        const length = ptr.add(16).readU32();
        if (length > 10000) {
            // Dump first bytes for diagnosis
            let hex = '';
            try {
                for (let i = 0; i < 32; i++) {
                    hex += ptr.add(i).readU8().toString(16).padStart(2, '0') + ' ';
                }
            } catch (e) { hex = 'unreadable'; }
            return `(invalid string, length=${length}, ptr=${ptr}, hex=[${hex}])`;
        }
        return ptr.add(20).readUtf16String(length);
    } catch (e) {
        return `<unreadable:${e.message}>`;
    }
}

function trunc(s, maxLen) {
    maxLen = maxLen || 500;
    if (s === null || s === undefined) return '(null)';
    s = String(s);
    if (s.length > maxLen) {
        return s.substring(0, maxLen) + `...[truncated ${s.length} chars total]`;
    }
    return s;
}

// Token fingerprint: never print authentication token plaintext.
// Uses length + FNV-1a over UTF-16 code units for runtime correlation.
// This is a correlation aid, not a cryptographic identity.
function tokenFingerprint(value) {
    if (value === null || value === undefined) return '(null)';
    const s = String(value);
    if (s === '(null)' || s.startsWith('<')) return s;
    let hash = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) {
        hash ^= s.charCodeAt(i);
        hash = Math.imul(hash, 0x01000193);
    }
    return 'len=' + s.length + ',fnv1a32=' + (hash >>> 0).toString(16).padStart(8, '0');
}

function readIl2cppArrayStrings(arrPtr, maxItems) {
    const out = [];
    try {
        if (arrPtr.isNull()) return out;
        const len = arrPtr.add(24).readU32();
        const n = Math.min(len, maxItems || 100);
        for (let i = 0; i < n; i++) {
            const itemPtr = arrPtr.add(32 + i * Process.pointerSize).readPointer();
            out.push(itemPtr.isNull() ? '(null)' : readIl2cppString(itemPtr));
        }
        if (len > n) out.push('(truncated ' + len + ' items total)');
    } catch (e) { out.push('<array read failed: ' + e.message + '>'); }
    return out;
}

// ---------- ELF-based export resolution ----------
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

// ---------- raw IL2CPP API (no bridge) ----------

let api = null;
let il2cppBase = null;
// Token flow correlation: last token passed to SaveLoginToken(arg[1]).
let lastSavedLoginTokenFingerprint = null;

function initApi() {
    const mod = findModuleBase(LIB_NAME);
    if (!mod) throw new Error(LIB_NAME + ' not found in /proc/self/maps');
    il2cppBase = mod.base;
    console.log(`[*] ${LIB_NAME} base @ ${il2cppBase} (${mod.path})`);

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
        class_get_methods: new NativeFunction(exp('il2cpp_class_get_methods'), 'pointer', ['pointer', 'pointer']),
        method_get_name: new NativeFunction(exp('il2cpp_method_get_name'), 'pointer', ['pointer']),
        method_get_param_count: new NativeFunction(exp('il2cpp_method_get_param_count'), 'uint32', ['pointer']),
        method_get_param: new NativeFunction(exp('il2cpp_method_get_param'), 'pointer', ['pointer', 'uint32']),
        method_get_return_type: new NativeFunction(exp('il2cpp_method_get_return_type'), 'pointer', ['pointer']),
        type_get_name: new NativeFunction(exp('il2cpp_type_get_name'), 'pointer', ['pointer']),
        class_get_field_from_name: new NativeFunction(exp('il2cpp_class_get_field_from_name'), 'pointer', ['pointer', 'pointer']),
        class_get_fields: new NativeFunction(exp('il2cpp_class_get_fields'), 'pointer', ['pointer', 'pointer']),
        field_get_name: new NativeFunction(exp('il2cpp_field_get_name'), 'pointer', ['pointer']),
        field_get_type: new NativeFunction(exp('il2cpp_field_get_type'), 'pointer', ['pointer']),
        field_get_offset: new NativeFunction(exp('il2cpp_field_get_offset'), 'uint32', ['pointer']),
        object_get_class: new NativeFunction(exp('il2cpp_object_get_class'), 'pointer', ['pointer']),
        class_get_name: new NativeFunction(exp('il2cpp_class_get_name'), 'pointer', ['pointer']),
    };
}

// Parse Dictionary<string,string> by reading its _entries array
// v4.1 fix: array max_length is at offset 24 (not 16). Scan for valid entry.
function readDictionary(dictPtr) {
    try {
        if (dictPtr.isNull()) return '(null dictionary)';
        const klass = api.object_get_class(dictPtr);
        const entriesField = api.class_get_field_from_name(klass, Memory.allocUtf8String('_entries'));
        if (entriesField.isNull()) return `(no _entries field)`;
        const entriesOffset = api.field_get_offset(entriesField);
        const entriesArr = dictPtr.add(entriesOffset).readPointer();
        if (entriesArr.isNull()) return '(null entries)';
        // Il2CppArray layout: klass(8) + monitor(8) + bounds(8) + max_length(8) + data
        // bounds=NULL at +16, max_length at +24 (confirmed from v4 debug: len@24=7)
        const maxLen = entriesArr.add(24).readU32();
        if (maxLen > 1000) return `(suspicious maxLen ${maxLen})`;
        // Dictionary._count (actual used entries) - try offset right after _entries ptr
        let dictCount = maxLen;
        try {
            const countField = api.class_get_field_from_name(klass, Memory.allocUtf8String('_count'));
            if (!countField.isNull()) {
                dictCount = dictPtr.add(api.field_get_offset(countField)).readU32();
            }
        } catch (e) {}
        const result = {};
        const ENTRY_SIZE = 24; // hashCode(4) + next(4) + key(8) + value(8)
        const dataStart = 32;  // after klass(8)+monitor(8)+bounds(8)+max_length(8)
        // Find first occupied entry to validate (don't assume index 0 is used)
        let validIdx = -1;
        for (let i = 0; i < Math.min(maxLen, 20); i++) {
            try {
                const e = entriesArr.add(dataStart + i * ENTRY_SIZE);
                const keyPtr = e.add(8).readPointer();
                if (keyPtr.isNull()) continue;
                const ks = readIl2cppString(keyPtr);
                if (ks && !ks.startsWith('(') && ks.length > 0 && ks.length < 200) {
                    validIdx = i;
                    break;
                }
            } catch (e) { continue; }
        }
        if (validIdx < 0) return `(no valid entries found, maxLen=${maxLen})`;
        // Enumerate all slots, skip empty (null key)
        for (let i = 0; i < maxLen; i++) {
            try {
                const e = entriesArr.add(dataStart + i * ENTRY_SIZE);
                const keyPtr = e.add(8).readPointer();
                if (keyPtr.isNull()) continue;
                const k = readIl2cppString(keyPtr);
                if (!k || k.startsWith('(')) continue;
                const valPtr = e.add(16).readPointer();
                const v = valPtr.isNull() ? '(null)' : readIl2cppString(valPtr);
                result[k] = v;
            } catch (e) { continue; }
        }
        return result;
    } catch (e) {
        return `(dict error: ${e.message})`;
    }
}
function findMethodImpl(className, methodName, paramCount) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();

    let image = ptr(0);
    const emptyNs = Memory.allocUtf8String('');
    for (let i = 0; i < count; i++) {
        const asm = assemblies.add(i * Process.pointerSize).readPointer();
        const img = api.assembly_get_image(asm);
        const name = api.image_get_name(img).readCString();
        if (name === 'Assembly-CSharp' || name === 'Assembly-CSharp.dll') { image = img; break; }
    }
    if (image.isNull()) {
        console.log('[!] Assembly-CSharp not found');
        return ptr(0);
    }

    const klass = api.class_from_name(image, emptyNs, Memory.allocUtf8String(className));
    if (klass.isNull()) {
        console.log(`[!] Class not found: ${className}`);
        return ptr(0);
    }

    const iter = Memory.alloc(Process.pointerSize);
    iter.writePointer(ptr(0));
    const candidates = [];
    while (true) {
        const method = api.class_get_methods(klass, iter);
        if (method.isNull()) break;
        const mName = api.method_get_name(method).readCString();
        if (mName !== methodName) continue;
        const pCount = api.method_get_param_count(method);
        // Get parameter type names
        const typeNames = [];
        for (let pi = 0; pi < pCount; pi++) {
            try {
                const t = api.method_get_param(method, pi);
                const tn = api.type_get_name(t).readCString();
                typeNames.push(tn);
            } catch (e) {
                typeNames.push('?');
            }
        }
        console.log(`[?] ${className}.${methodName} overload: (${typeNames.join(', ')}) @ ${method.readPointer()}`);
        if (pCount === paramCount) {
            let retName = '?';
            try { retName = api.type_get_name(api.method_get_return_type(method)).readCString(); } catch (e) {}
            candidates.push({ method, typeNames, fnPtr: method.readPointer(), retName });
        }
    }
    if (candidates.length === 0) {
        console.log(`[!] Method not found: ${className}.${methodName} (${paramCount} params)`);
        return null;
    }
    // Prefer the overload where all params are System.String
    for (const c of candidates) {
        if (c.typeNames.every(t => t === 'System.String')) {
            console.log(`[+] Found ${className}.${methodName}(${c.typeNames.join(', ')}) -> ${c.retName} @ ${c.fnPtr}`);
            return c;
        }
    }
    // Fallback: first candidate
    const c = candidates[0];
    console.log(`[+] Found ${className}.${methodName}(${c.typeNames.join(', ')}) -> ${c.retName} @ ${c.fnPtr} (first match)`);
    return c;
}

// Safely describe a return value: klass name + raw bytes, no string assumption
function describeRetval(rv) {
    try {
        if (rv === null || rv === undefined) return '(null/undefined)';
        // Value-type return (int, bool, etc.) comes as a JS number, not a pointer
        if (typeof rv === 'number') return `(number: ${rv} / 0x${rv.toString(16)})`;
        if (typeof rv !== 'object' || typeof rv.isNull !== 'function')
            return `(${typeof rv}: ${String(rv).substring(0, 100)})`;
        if (rv.isNull()) return '(null pointer)';
        const klass = api.object_get_class(rv);
        if (klass.isNull()) return `(no klass @ ${rv})`;
        const kname = api.class_get_name(klass).readCString();
        let hex = '';
        try {
            for (let i = 0; i < 32; i++) hex += rv.add(i).readU8().toString(16).padStart(2, '0') + ' ';
        } catch (e) { hex = 'unreadable'; }
        let asStr = '';
        if (kname === 'String') {
            asStr = ` str="${trunc(readIl2cppString(rv), 200)}"`;
        }
        return `klass=${kname} @ ${rv} hex=[${hex}]${asStr}`;
    } catch (e) {
        return `(describe failed: ${e.message})`;
    }
}

// Find a method in any loaded assembly (for System.Convert etc.)
function findMethodAnywhere(className, methodName, paramCount) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();
    const dot = className.lastIndexOf('.');
    const namespaceName = dot >= 0 ? className.substring(0, dot) : '';
    const shortClassName = dot >= 0 ? className.substring(dot + 1) : className;
    const nsPtr = Memory.allocUtf8String(namespaceName);
    const classPtr = Memory.allocUtf8String(shortClassName);
    for (let i = 0; i < count; i++) {
        try {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            const klass = api.class_from_name(img, nsPtr, classPtr);
            if (klass.isNull()) continue;
            const iter = Memory.alloc(Process.pointerSize);
            iter.writePointer(ptr(0));
            while (true) {
                const method = api.class_get_methods(klass, iter);
                if (method.isNull()) break;
                if (api.method_get_name(method).readCString() !== methodName) continue;
                if (api.method_get_param_count(method) !== paramCount) continue;
                return method.readPointer();
            }
        } catch (e) { continue; }
    }
    return ptr(0);
}


function findMethodsAnywhereByName(className, methodName) {
    const out = [];
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();
    const dot = className.lastIndexOf('.');
    const namespaceName = dot >= 0 ? className.substring(0, dot) : '';
    const shortClassName = dot >= 0 ? className.substring(dot + 1) : className;
    const nsPtr = Memory.allocUtf8String(namespaceName);
    const classPtr = Memory.allocUtf8String(shortClassName);
    for (let i = 0; i < count; i++) {
        try {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            const klass = api.class_from_name(img, nsPtr, classPtr);
            if (klass.isNull()) continue;
            const iter = Memory.alloc(Process.pointerSize);
            iter.writePointer(ptr(0));
            while (true) {
                const method = api.class_get_methods(klass, iter);
                if (method.isNull()) break;
                if (api.method_get_name(method).readCString() !== methodName) continue;
                const typeNames = [];
                const pc = api.method_get_param_count(method);
                for (let pi = 0; pi < pc; pi++) {
                    try { typeNames.push(api.type_get_name(api.method_get_param(method, pi)).readCString()); }
                    catch (e) { typeNames.push('?'); }
                }
                out.push({ method, fnPtr: method.readPointer(), typeNames, paramCount: pc });
            }
            if (out.length) return out;
        } catch (e) {}
    }
    return out;
}
function describeObjectPtr(obj) {
    try {
        if (!obj || obj.isNull()) return 'null';
        const klass = api.object_get_class(obj);
        if (klass.isNull()) return 'klass=null';
        return api.class_get_name(klass).readCString() + '@' + obj;
    } catch (e) {
        return 'describe-failed@' + obj;
    }
}

// v4.18: add OpInfo.SerialNumber and mark only Send ret=1 as accepted.\n// v4.17: inspect only the request object's class and opcode-like field.
// Never dump arbitrary request fields, serialized buffers, tokens, or payload bytes.
function describeKcpSendRequest(obj) {
    try {
        if (!obj || obj.isNull()) return 'request=null';
        const klass = api.object_get_class(obj);
        if (klass.isNull()) return 'request=klass-null@' + obj;
        const className = api.class_get_name(klass).readCString();
        let out = 'request=' + className + '@' + obj;
        if (className === 'OpInfo') {
            try { out += ' SerialNumber=' + obj.add(0x10).readU32(); } catch (e) {}
            try { out += ' OpCode=' + obj.add(0x14).readS32(); } catch (e) {}
            try { out += ' ReturnCode=' + obj.add(0x18).readS32(); } catch (e) {}
            return out;
        }
        const iter = Memory.alloc(Process.pointerSize);
        iter.writePointer(ptr(0));
        let scanned = 0;
        while (scanned++ < 128) {
            const field = api.class_get_fields(klass, iter);
            if (field.isNull()) break;
            const name = api.field_get_name(field).readCString();
            if (!/opcode|operationcode/i.test(name)) continue;
            const offset = api.field_get_offset(field);
            let typeName = '?';
            try { typeName = api.type_get_name(api.field_get_type(field)).readCString(); } catch (e) {}
            out += ' ' + name + '@+' + offset.toString(16) + ':' + typeName;
            if (/Int32|OperationCode|Enum/i.test(typeName)) {
                try { out += '=' + obj.add(offset).readS32(); } catch (e) {}
            }
        }
        return out;
    } catch (e) {
        return 'request-inspect-failed:' + e.message;
    }
}

function findMethodAnywhereTyped(className, methodName, paramCount, preferredSecondType) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();
    const dot = className.lastIndexOf('.');
    const namespaceName = dot >= 0 ? className.substring(0, dot) : '';
    const shortClassName = dot >= 0 ? className.substring(dot + 1) : className;
    const nsPtr = Memory.allocUtf8String(namespaceName);
    const classPtr = Memory.allocUtf8String(shortClassName);
    for (let i = 0; i < count; i++) {
        try {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            const klass = api.class_from_name(img, nsPtr, classPtr);
            if (klass.isNull()) continue;
            const iter = Memory.alloc(Process.pointerSize);
            iter.writePointer(ptr(0));
            while (true) {
                const method = api.class_get_methods(klass, iter);
                if (method.isNull()) break;
                if (api.method_get_name(method).readCString() !== methodName) continue;
                if (api.method_get_param_count(method) !== paramCount) continue;
                const typeNames = [];
                for (let pi = 0; pi < paramCount; pi++) {
                    try { typeNames.push(api.type_get_name(api.method_get_param(method, pi)).readCString()); }
                    catch (e) { typeNames.push('?'); }
                }
                let retName = '?';
                try { retName = api.type_get_name(api.method_get_return_type(method)).readCString(); } catch (e) {}
                console.log('[?] ' + className + '.' + methodName + ' overload: (' + typeNames.join(', ') + ') -> ' + retName + ' @ ' + method.readPointer());
                if (!preferredSecondType || typeNames[1] === preferredSecondType ||
                    (preferredSecondType === 'System.Object[]' && typeNames[1].indexOf('System.Object[]') >= 0)) {
                    return { fnPtr: method.readPointer(), typeNames: typeNames, retName: retName };
                }
            }
        } catch (e) { continue; }
    }
    return null;
}

function findMethodAnywhereExact(className, methodName, expectedTypes) {
    const domain=api.domain_get(), cp=Memory.alloc(Process.pointerSize);
    const assemblies=api.domain_get_assemblies(domain,cp), count=cp.readU32();
    const dot=className.lastIndexOf('.'), ns=dot>=0?className.substring(0,dot):'', cn=dot>=0?className.substring(dot+1):className;
    const nsp=Memory.allocUtf8String(ns), cnp=Memory.allocUtf8String(cn);
    for(let i=0;i<count;i++) try {
        const img=api.assembly_get_image(assemblies.add(i*Process.pointerSize).readPointer());
        const klass=api.class_from_name(img,nsp,cnp); if(klass.isNull()) continue;
        const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
        while(true){ const m=api.class_get_methods(klass,it); if(m.isNull()) break;
            if(api.method_get_name(m).readCString()!==methodName || api.method_get_param_count(m)!==expectedTypes.length) continue;
            let exact=true, types=[]; for(let p=0;p<expectedTypes.length;p++){let t='?';try{t=api.type_get_name(api.method_get_param(m,p)).readCString();}catch(e){} types.push(t);if(t!==expectedTypes[p])exact=false;}
            if(!exact)continue; let ret='?';try{ret=api.type_get_name(api.method_get_return_type(m)).readCString();}catch(e){}
            console.log('[+] Found '+className+'.'+methodName+'('+types.join(', ')+') -> '+ret+' @ '+m.readPointer());
            return {fnPtr:m.readPointer(),typeNames:types,retName:ret};
        }
    } catch(e){}
    return null;
}
function findMethodAnywhereNoParams(className,methodName){return findMethodAnywhereExact(className,methodName,[]);}
function readIl2cppByteArray(arrPtr,maxBytes){
    if(arrPtr.isNull())return{length:0,text:'',hex:''};
    try{const len=arrPtr.add(24).readU32(),n=Math.min(len,maxBytes||65536);let hex='',bytes=[];
        for(let i=0;i<n;i++){const b=arrPtr.add(32+i).readU8();bytes.push(b);hex+=b.toString(16).padStart(2,'0');}
        let textValue='';try{textValue=Memory.readUtf8String(arrPtr.add(32),n)||'';}catch(e){try{textValue=String.fromCharCode.apply(null,bytes);}catch(e2){}}
        return{length:len,text:textValue,hex,truncated:len>n};
    }catch(e){return{length:-1,text:'<byte[] read failed: '+e.message+'>',hex:''};}
}
function waitForIl2cpp() {
    return new Promise((resolve) => {
        const timer = setInterval(() => {
            try {
                const mod = findModuleBase(LIB_NAME);
                if (!mod) return; // not loaded yet
                initApi();
                const domain = api.domain_get();
                if (!domain.isNull()) {
                    clearInterval(timer);
                    resolve();
                } else {
                    console.log('[*] libil2cpp loaded, waiting for domain...');
                }
            } catch (e) {
                console.log(`[*] waiting for il2cpp... (${e.message})`);
            }
        }, 2000);
    });
}

function waitForAssembly() {
    return new Promise((resolve) => {
        console.log('[*] Waiting for Assembly-CSharp (enter the game world on the phone)...');
        let listed = false;
        const timer = setInterval(() => {
            try {
                const domain = api.domain_get();
                const countPtr = Memory.alloc(Process.pointerSize);
                const assemblies = api.domain_get_assemblies(domain, countPtr);
                const count = countPtr.readU32();
                let found = false;
                const names = [];
                for (let i = 0; i < count; i++) {
                    const asm = assemblies.add(i * Process.pointerSize).readPointer();
                    const img = api.assembly_get_image(asm);
                    const name = api.image_get_name(img).readCString();
                    names.push(name);
                    if (name === 'Assembly-CSharp' || name === 'Assembly-CSharp.dll') {
                        found = true;
                    }
                }
                if (found) {
                    clearInterval(timer);
                    console.log(`[*] Assembly-CSharp found (${count} assemblies loaded).`);
                    resolve();
                    return;
                }
                if (!listed && count > 5) {
                    listed = true;
                    console.log(`[*] Loaded assemblies (${count}): ${names.join(', ')}`);
                }
            } catch (e) {
                console.log(`[*] waiting for assembly... (${e.message})`);
            }
        }, 3000);
    });
}

// ---------- hooks ----------

async function main() {
    console.log('[*] justice_hook v4.22 starting...');
    await waitForIl2cpp();
    console.log('[*] IL2CPP domain ready.');
    await waitForAssembly();
    console.log('[*] Installing hooks...\n');

    let hookCount = 0;

    // Login HTTP trace state.
    let loginTraceUntil=0, loginTraceSeq=0;
    const requestMeta=new Map();
    let uwrGetUrl=null, uwrGetMethod=null, uwrGetUploadHandler=null, uploadGetData=null;
    const loginTraceActive=()=>Date.now()<=loginTraceUntil;
    function describeUnityWebRequest(req){
        const out={url:'',method:'',body:null};
        try{if(uwrGetUrl)out.url=readIl2cppString(uwrGetUrl(req));}catch(e){out.url='<url read failed: '+e.message+'>';}
        try{if(uwrGetMethod)out.method=readIl2cppString(uwrGetMethod(req));}catch(e){out.method='<method read failed: '+e.message+'>';}
        try{if(uwrGetUploadHandler){const uh=uwrGetUploadHandler(req);if(!uh.isNull()&&uploadGetData)out.body=readIl2cppByteArray(uploadGetData(uh),65536);}}catch(e){out.body={length:-1,text:'<body read failed: '+e.message+'>',hex:''};}
        return out;
    }
    try{
        const U='UnityEngine.Networking.UnityWebRequest',H='UnityEngine.Networking.UploadHandler';
        const u=findMethodAnywhereNoParams(U,'get_url'),m=findMethodAnywhereNoParams(U,'get_method'),h=findMethodAnywhereNoParams(U,'get_uploadHandler'),d=findMethodAnywhereNoParams(H,'get_data');
        if(u)uwrGetUrl=new NativeFunction(u.fnPtr,'pointer',['pointer']);
        if(m)uwrGetMethod=new NativeFunction(m.fnPtr,'pointer',['pointer']);
        if(h)uwrGetUploadHandler=new NativeFunction(h.fnPtr,'pointer',['pointer']);
        if(d)uploadGetData=new NativeFunction(d.fnPtr,'pointer',['pointer']);
        console.log('[*] UnityWebRequest accessors ready.');
    }catch(e){console.log('[!] UnityWebRequest accessor resolution failed: '+e.message);}
    try{
        const ctor=findMethodAnywhereExact('UnityEngine.Networking.UnityWebRequest','.ctor',['System.String','System.String']);
        if(ctor){Interceptor.attach(ctor.fnPtr,{onEnter(args){if(!loginTraceActive())return;const id=++loginTraceSeq,url=readIl2cppString(args[1]),method=readIl2cppString(args[2]);requestMeta.set(String(args[0]),{id,url,method,headers:[]});console.log('\n[HTTP_CREATE] UnityWebRequest #'+id);console.log('  url: '+JSON.stringify(trunc(url,4000)));console.log('  method: '+JSON.stringify(method));console.log('  request_ptr: '+args[0]);}});hookCount++;}else console.log('[!] UnityWebRequest .ctor(string,string) not found');
    }catch(e){console.log('[!] UnityWebRequest ctor hook failed: '+e.message);}
    try{
        const sh=findMethodAnywhereExact('UnityEngine.Networking.UnityWebRequest','SetRequestHeader',['System.String','System.String']);
        if(sh){Interceptor.attach(sh.fnPtr,{onEnter(args){if(!loginTraceActive())return;const meta=requestMeta.get(String(args[0]));if(!meta)return;const name=readIl2cppString(args[1]),value=readIl2cppString(args[2]);meta.headers.push({name,value});console.log('[HTTP_HEADER] #'+meta.id+' '+name+': '+trunc(value,2000));}});hookCount++;}else console.log('[!] UnityWebRequest.SetRequestHeader(string,string) not found');
    }catch(e){console.log('[!] SetRequestHeader hook failed: '+e.message);}
    // v4.6: capture the actual upload payload at UploadHandlerRaw(byte[]) construction.
    // This is more reliable than UploadHandler.get_data() at Send time.
    try{
        const raw=findMethodAnywhereExact('UnityEngine.Networking.UploadHandlerRaw','.ctor',['System.Byte[]']);
        if(raw){
            Interceptor.attach(raw.fnPtr,{onEnter(args){
                if(!loginTraceActive())return;
                try{
                    const b=readIl2cppByteArray(args[1],65536);
                    this.body=b;
                    console.log('\n[HTTP_UPLOAD] UploadHandlerRaw(byte[])');
                    console.log('  body_len: '+b.length+(b.truncated?' (truncated)':''));
                    console.log('  body_utf8: '+JSON.stringify(trunc(b.text,20000)));
                    console.log('  body_hex: '+trunc(b.hex,4000));
                }catch(e){console.log('[HTTP_UPLOAD] read failed: '+e.message);}
            },onLeave(retval){
                if(!loginTraceActive()||!this.body)return;
                this.uploadHandler=retval;
                console.log('  upload_handler: '+retval);
                console.log('[HTTP_UPLOAD END]\n');
            }});
            hookCount++;
        }else console.log('[!] UploadHandlerRaw(byte[]) not found');
    }catch(e){console.log('[!] UploadHandlerRaw hook failed: '+e.message);}

    // v4.6: capture when HttpRequest assigns the body/method to UnityWebRequest.
    try{
        const su=findMethodAnywhereExact('UnityEngine.Networking.UnityWebRequest','set_uploadHandler',['UnityEngine.Networking.UploadHandler']);
        if(su){
            Interceptor.attach(su.fnPtr,{onEnter(args){
                if(!loginTraceActive())return;
                const meta=requestMeta.get(String(args[0]));
                if(!meta)return;
                const uh=args[1];
                console.log('[HTTP_UPLOAD_SET] #'+meta.id+' uploadHandler='+uh);
                try{
                    if(!uh.isNull()&&uploadGetData){
                        const b=readIl2cppByteArray(uploadGetData(uh),65536);
                        console.log('  body_len: '+b.length);
                        console.log('  body_utf8: '+JSON.stringify(trunc(b.text,20000)));
                    }
                }catch(e){console.log('  body read: '+e.message);}
            }});
            hookCount++;
        }else console.log('[!] UnityWebRequest.set_uploadHandler not found');
    }catch(e){console.log('[!] set_uploadHandler hook failed: '+e.message);}

    try{
        const sm=findMethodAnywhereExact('UnityEngine.Networking.UnityWebRequest','set_method',['System.String']);
        if(sm){
            Interceptor.attach(sm.fnPtr,{onEnter(args){
                if(!loginTraceActive())return;
                const meta=requestMeta.get(String(args[0]));
                if(!meta)return;
                const method=readIl2cppString(args[1]);
                meta.methodSetter=method;
                console.log('[HTTP_METHOD_SET] #'+meta.id+' method='+JSON.stringify(method));
            }});
            hookCount++;
        }else console.log('[!] UnityWebRequest.set_method(string) not found');
    }catch(e){console.log('[!] set_method hook failed: '+e.message);}

    // v4.6: enumerate AliothEngine.Net.HttpRequest methods so the next run
    // tells us exactly where request body serialization is implemented.
    try{
        const domain=api.domain_get(), cp=Memory.alloc(Process.pointerSize);
        const assemblies=api.domain_get_assemblies(domain,cp), count=cp.readU32();
        const ns=Memory.allocUtf8String('AliothEngine.Net'), cn=Memory.allocUtf8String('HttpRequest');
        let printed=false;
        for(let ai=0;ai<count;ai++){
            try{
                const img=api.assembly_get_image(assemblies.add(ai*Process.pointerSize).readPointer());
                const klass=api.class_from_name(img,ns,cn); if(klass.isNull())continue;
                console.log('[HTTPREQUEST] AliothEngine.Net.HttpRequest methods:');
                const it=Memory.alloc(Process.pointerSize);it.writePointer(ptr(0));
                while(true){
                    const m=api.class_get_methods(klass,it);if(m.isNull())break;
                    const name=api.method_get_name(m).readCString();
                    const pc=api.method_get_param_count(m), types=[];
                    for(let pi=0;pi<pc;pi++){try{types.push(api.type_get_name(api.method_get_param(m,pi)).readCString());}catch(e){types.push('?');}}
                    let ret='?';try{ret=api.type_get_name(api.method_get_return_type(m)).readCString();}catch(e){}
                    console.log('  '+name+'('+types.join(', ')+') -> '+ret+' @ '+m.readPointer());
                }
                printed=true;break;
            }catch(e){}
        }
        if(!printed)console.log('[!] AliothEngine.Net.HttpRequest class not found');
    }catch(e){console.log('[!] HttpRequest method inventory failed: '+e.message);}
    
    try{
        const send=findMethodAnywhereNoParams('UnityEngine.Networking.UnityWebRequest','SendWebRequest');
        if(send){Interceptor.attach(send.fnPtr,{onEnter(args){if(!loginTraceActive())return;const meta=requestMeta.get(String(args[0])),snap=describeUnityWebRequest(args[0]);console.log('\n[HTTP_SEND] '+(meta?'UnityWebRequest #'+meta.id:'UnityWebRequest'));console.log('  url: '+JSON.stringify(trunc(snap.url,4000)));console.log('  method: '+JSON.stringify(snap.method));if(meta)console.log('  headers: '+JSON.stringify(meta.headers));if(snap.body){console.log('  body_len: '+snap.body.length+(snap.body.truncated?' (truncated)':''));console.log('  body_utf8: '+JSON.stringify(trunc(snap.body.text,20000)));console.log('  body_hex: '+trunc(snap.body.hex,4000));}else console.log('  body: <none>');console.log('  request_ptr: '+args[0]);console.log('[HTTP_SEND END]\n');}});hookCount++;}else console.log('[!] UnityWebRequest.SendWebRequest() not found');
    }catch(e){console.log('[!] SendWebRequest hook failed: '+e.message);}


    // V4_POST_Login (static, 3 params)
    try {
        const v4Login = findMethodImpl(CLASS_NAME, 'V4_POST_Login', 3);
        if (v4Login) {
            Interceptor.attach(v4Login.fnPtr, {
                onEnter(args) {
                    console.log('\n========== V4_POST_Login called ==========');
                    const names = PARAMS['V4_POST_Login'];
                    for (let i = 0; i < 3; i++) {
                        console.log(`  ${names[i]}: ${trunc(readIl2cppString(args[i]))}`);
                    }
                    this.callTime = Date.now();
                    loginTraceUntil = Date.now() + 10000;
                    console.log('  [HTTP_TRACE] login request trace window opened (10s)');
                },
                onLeave(retval) {
                    console.log(`  [return after ${Date.now() - this.callTime}ms]`);
                    console.log('========================================\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] V4_POST_Login hook failed: ${e.message}`); }

    // Sign (static, 2 params) — THE MOST IMPORTANT ONE
    // Actual signature: Sign(System.String, Dictionary<String,String>)
    const signThreads = new Set();
    try {
        const sign = findMethodImpl(CLASS_NAME, 'Sign', 2);
        if (sign) {
            console.log(`[*] Sign return type: ${sign.retName}`);
            Interceptor.attach(sign.fnPtr, {
                onEnter(args) {
                    signThreads.add(Process.getCurrentThreadId());
                    console.log('\n---------- Sign called ----------');
                    const contentVal = readIl2cppString(args[0]);
                    this.inputs = { content: contentVal };
                    this.dictPtr = args[1];  // store for onLeave re-read
                    console.log(`  content: ${trunc(contentVal)}`);
                    const dictVal = readDictionary(args[1]);
                    this.inputs.dict = dictVal;
                    console.log(`  dict: ${JSON.stringify(dictVal)}`);
                    this.startTime = Date.now();
                },
                onLeave(retval) {
                    signThreads.delete(Process.getCurrentThreadId());
                    const elapsed = Date.now() - this.startTime;
                    // Sign returns void - check if dict was modified in-place
                    let afterDict = '';
                    try {
                        // args[1] not available in onLeave, use stored pointer
                        afterDict = JSON.stringify(readDictionary(this.dictPtr));
                    } catch (e) { afterDict = `(re-read failed: ${e.message})`; }
                    console.log(`  => SIGN OUTPUT: void (dict modified in-place?)`);
                    console.log(`  => dict after: ${afterDict}`);
                    console.log(`  (${elapsed}ms)`);
                    console.log('----------------------------------\n');
                    console.log(`[SIGN_DATA] input_content=${JSON.stringify(trunc(this.inputs.content, 2000))} input_dict=${JSON.stringify(this.inputs.dict)} dict_after=${afterDict}`);
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] Sign hook failed: ${e.message}`); }

    // GetDefaultParams (static, 0 params) — returns Dictionary<string,string>
    try {
        const getDefault = findMethodImpl(CLASS_NAME, 'GetDefaultParams', 0);
        if (getDefault) {
            Interceptor.attach(getDefault.fnPtr, {
                onEnter(args) {
                    console.log('\n---------- GetDefaultParams called ----------');
                },
                onLeave(retval) {
                    const dict = readDictionary(retval);
                    console.log(`  [return] ${JSON.stringify(dict)}`);
                    console.log('----------------------------------\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] GetDefaultParams hook failed: ${e.message}`); }

    // V3_POST_AllInOne (static, 1 param)
    try {
        const allInOne = findMethodImpl(CLASS_NAME, 'V3_POST_AllInOne', 1);
        if (allInOne) {
            Interceptor.attach(allInOne.fnPtr, {
                onEnter(args) {
                    console.log('\n========== V3_POST_AllInOne called ==========');
                    console.log(`  app_key: ${trunc(readIl2cppString(args[0]))}`);
                },
                onLeave(retval) {
                    console.log('============================================\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] V3_POST_AllInOne hook failed: ${e.message}`); }

    // Login token flow: compare SaveLoginToken(arg[1]) with ProtocolGame_HttpRequest.get_Token().
    // IMPORTANT: authentication token plaintext is never printed or retained.
    // Static analysis: OnGetLoginToken -> Response_GetLoginToken -> SaveLoginToken.
    try {
        const save = findMethodAnywhereTyped('LoginManager', 'SaveLoginToken', 5, null);
        if (save) {
            console.log('[+] Hooking LoginManager.SaveLoginToken(' + save.typeNames.join(', ') + ') @ ' + save.fnPtr);
            Interceptor.attach(save.fnPtr, {
                onEnter(args) {
                    console.log('\\n[TOKEN_SAVE] LoginManager.SaveLoginToken');
                    for (let i = 0; i < save.typeNames.length; i++) {
                        const type = save.typeNames[i] || '';
                        let value = '<unreadable>';
                        try {
                            if (type.indexOf('System.String') >= 0) value = readIl2cppString(args[i + 1]);
                            else if (type.indexOf('Boolean') >= 0) value = args[i + 1].toInt32() !== 0;
                            else if (type.indexOf('Int32') >= 0) value = args[i + 1].toInt32();
                            else if (type.indexOf('Int64') >= 0) value = args[i + 1].toString();
                            else value = args[i + 1];
                        } catch (e) { value = '<read failed: ' + e.message + '>'; }

                        // SaveLoginToken's second parameter is the authentication token.
                        if (i === 1 && type.indexOf('System.String') >= 0) {
                            const fp = tokenFingerprint(value);
                            lastSavedLoginTokenFingerprint = fp;
                            console.log('  arg[' + i + '] ' + type + ': <TOKEN_REDACTED> [' + fp + ']');
                        } else {
                            console.log('  arg[' + i + '] ' + type + ': ' + JSON.stringify(trunc(value, 1000)));
                        }
                    }
                    console.log('  [TOKEN_SAVE END]');
                }
            });
            hookCount++;
        } else console.log('[!] LoginManager.SaveLoginToken not found');
    } catch (e) { console.log('[!] SaveLoginToken hook failed: ' + e.message); }

    try {
        const getToken = findMethodAnywhereNoParams('ProtocolGame_HttpRequest', 'get_Token');
        if (getToken) {
            console.log('[+] Hooking ProtocolGame_HttpRequest.get_Token() @ ' + getToken.fnPtr);
            Interceptor.attach(getToken.fnPtr, {
                onEnter(args) { this.thisPtr = args[0]; },
                onLeave(retval) {
                    let value = '<null>';
                    try { value = readIl2cppString(retval); } catch (e) { value = '<read failed: ' + e.message + '>'; }
                    const fp = tokenFingerprint(value);
                    console.log('[TOKEN_GET] ProtocolGame_HttpRequest.get_Token -> <TOKEN_REDACTED> [' + fp + ']');
                    if (lastSavedLoginTokenFingerprint !== null &&
                        fp !== '(null)' && !String(fp).startsWith('<')) {
                        console.log('[TOKEN_COMPARE] get_Token == last SaveLoginToken(arg[1]) : ' +
                            (fp === lastSavedLoginTokenFingerprint ? 'MATCH' : 'MISMATCH'));
                    }
                }
            });
            hookCount++;
        } else console.log('[!] ProtocolGame_HttpRequest.get_Token not found');
    } catch (e) { console.log('[!] get_Token hook failed: ' + e.message); }

    // System.String.Join(string, string[]) — Sign이 MD5에 넘기는 실제 Join 배열 추적용
    try {
        const join = findMethodAnywhereTyped('System.String', 'Join', 2, 'System.String[]');
        if (join) {
            console.log('[+] Hooking System.String.Join(' + join.typeNames.join(', ') + ') @ ' + join.fnPtr);
            Interceptor.attach(join.fnPtr, {
                onEnter(args) {
                    if (!signThreads.has(Process.getCurrentThreadId())) return;
                    this.inSign = true;
                    const separator = readIl2cppString(args[0]);
                    const values = readIl2cppArrayStrings(args[1], 100);
                    console.log('\n[JOIN_DATA] String.Join called inside Sign');
                    console.log('  separator: ' + JSON.stringify(separator));
                    console.log('  count: ' + values.length);
                    for (let i = 0; i < values.length; i++) console.log('  value[' + i + ']: ' + JSON.stringify(trunc(values[i], 2000)));
                    console.log('  joined_preview: ' + JSON.stringify(trunc(values.join(separator), 10000)));
                },
                onLeave(retval) {
                    if (!this.inSign) return;
                    console.log('  joined_actual: ' + JSON.stringify(trunc(readIl2cppString(retval), 10000)));
                    console.log('  [JOIN_DATA END]');
                }
            });
            hookCount++;
        } else console.log('[!] System.String.Join(string, string[]) not found');
    } catch (e) { console.log('[!] String.Join hook failed: ' + e.message); }

    // AliothEngine.Encrypt.MD5HashString(string) — Sign 최종 입력/출력 확인
    try {
        const md5 = findMethodAnywhereTyped('AliothEngine.Encrypt', 'MD5HashString', 1, null);
        if (md5) {
            console.log('[+] Hooking AliothEngine.Encrypt.MD5HashString(' + md5.typeNames.join(', ') + ') @ ' + md5.fnPtr);
            Interceptor.attach(md5.fnPtr, {
                onEnter(args) {
                    if (!signThreads.has(Process.getCurrentThreadId())) return;
                    this.inSign = true;
                    this.input = readIl2cppString(args[0]);
                    console.log('[MD5_DATA] input: ' + JSON.stringify(trunc(this.input, 10000)));
                },
                onLeave(retval) {
                    if (!this.inSign) return;
                    console.log('[MD5_DATA] output: ' + JSON.stringify(readIl2cppString(retval)));
                }
            });
            hookCount++;
        } else console.log('[!] AliothEngine.Encrypt.MD5HashString not found');
    } catch (e) { console.log('[!] MD5HashString hook failed: ' + e.message); }

    // System.Convert.ToBase64String(byte[]) — t 생성 추적용
    try {
        const b64 = findMethodAnywhere('System.Convert', 'ToBase64String', 1);
        if (!b64.isNull()) {
            console.log(`[+] Hooking System.Convert.ToBase64String @ ${b64}`);
            Interceptor.attach(b64, {
                onEnter(args) {
                    try {
                        const arr = args[0];
                        if (!arr.isNull()) {
                            const len = arr.add(24).readU32();
                            let hex = '';
                            const n = Math.min(len, 16);
                            for (let i = 0; i < n; i++)
                                hex += arr.add(32 + i).readU8().toString(16).padStart(2, '0');
                            console.log(`[B64] ToBase64String input: len=${len} head=[${hex}]`);
                            this.inLen = len;
                        }
                    } catch (e) {}
                },
                onLeave(retval) {
                    try {
                        const value = readIl2cppString(retval);
                        if (value && value.length > 100)
                            console.log(`[B64] => output len=${value.length} head=${value.substring(0, 40)}...`);
                    } catch (e) {}
                }
            });
            hookCount++;
        } else {
            console.log('[!] System.Convert.ToBase64String not found');
        }
    } catch (e) { console.log(`[!] ToBase64String hook failed: ${e.message}`); }

    
// v4.12: runtime response object inspection.
// Uses the same IL2CPP resolver/API as the main hook; no separate ELF parser.
// Dumps the concrete response class and its instance fields once per class.
const inspectedResponseClasses = new Set();

function safeReadResponseField(obj, off, typeName) {
    try {
        const p = obj.add(off);
        if (typeName.indexOf('System.Int32') >= 0) return String(p.readS32());
        if (typeName.indexOf('System.UInt32') >= 0) return String(p.readU32());
        if (typeName.indexOf('System.Int64') >= 0) return String(p.readS64());
        if (typeName.indexOf('System.UInt64') >= 0) return String(p.readU64());
        if (typeName.indexOf('System.Boolean') >= 0) return String(p.readU8() !== 0);
        if (typeName === 'System.Single') return String(p.readFloat());
        if (typeName === 'System.Double') return String(p.readDouble());
        const q = p.readPointer();
        if (q.isNull()) return 'null';
        return q.toString();
    } catch (e) {
        return '<read-failed>';
    }
}

function inspectResponseObject(response) {
    try {
        if (!response || response.isNull()) {
            console.log('[RESP_CLASS] response=null');
            return;
        }
        const klass = api.object_get_class(response);
        if (klass.isNull()) {
            console.log('[RESP_CLASS] obj=' + response + ' class=<null>');
            return;
        }
        const className = api.class_get_name(klass).readCString();
        console.log('[RESP_CLASS] obj=' + response + ' class=' + className);

        // Avoid dumping the same class on every response.
        if (inspectedResponseClasses.has(className)) return;
        inspectedResponseClasses.add(className);

        const iter = Memory.alloc(Process.pointerSize);
        iter.writePointer(ptr(0));
        let count = 0;
        while (count < 200) {
            const field = api.class_get_fields(klass, iter);
            if (field.isNull()) break;
            const name = api.field_get_name(field).readCString();
            const off = api.field_get_offset(field);
            let typeName = '?';
            try {
                typeName = api.type_get_name(api.field_get_type(field)).readCString();
            } catch (e) {}
            // Skip static/special fields; report plausible instance fields.
            if (name && off < 0x1000) {
                console.log('[RESP_FIELD] ' + name +
                    ' @+0x' + off.toString(16) +
                    ' type=' + typeName +
                    ' value=' + safeReadResponseField(response, off, typeName));
            }
            count++;
        }
        console.log('[RESP_FIELD_END] class=' + className + ' count=' + count);
    } catch (e) {
        console.log('[RESP_INSPECT_ERR] ' + e.message);
    }
}


// v4.13: inspect Chapters Dictionary<int, ProtoChapter> entries.
// Entry layout is validated against runtime Dictionary metadata before reading.
// IL2CPP Dictionary Entry<int,T>: hashCode(4), next(4), key(4), padding(4), value(8).
function inspectChaptersDictionary(dictPtr) {
    try {
        if (!dictPtr || dictPtr.isNull()) {
            console.log('[CHAPTERS_ENUM] dict=null');
            return;
        }
        const dklass = api.object_get_class(dictPtr);
        const dname = api.class_get_name(dklass).readCString();
        console.log('[CHAPTERS_ENUM] type=' + dname + ' ptr=' + dictPtr);

        const countField = api.class_get_field_from_name(dklass, Memory.allocUtf8String('_count'));
        const entriesField = api.class_get_field_from_name(dklass, Memory.allocUtf8String('_entries'));
        if (countField.isNull() || entriesField.isNull()) {
            console.log('[CHAPTERS_ENUM] missing _count/_entries');
            return;
        }

        const countOff = api.field_get_offset(countField);
        const entriesOff = api.field_get_offset(entriesField);
        const count = dictPtr.add(countOff).readS32();
        const entries = dictPtr.add(entriesOff).readPointer();

        console.log('[CHAPTERS_ENUM] _count@+0x' + countOff.toString(16) + '=' + count +
            ' _entries@+0x' + entriesOff.toString(16) + '=' + entries);

        if (entries.isNull() || count <= 0 || count > 100000) {
            console.log('[CHAPTERS_ENUM] no usable entries');
            return;
        }

        const len = entries.add(24).readU32();
        console.log('[CHAPTERS_ENUM] entries.length=' + len);

        // Entry<int, ProtoChapter> is 24 bytes on this 64-bit IL2CPP build.
        const ENTRY_SIZE = 24;
        const DATA_START = 32;
        const limit = Math.min(len, 5000);
        let found = 0;

        for (let i = 0; i < limit; i++) {
            try {
                const e = entries.add(DATA_START + i * ENTRY_SIZE);
                const hash = e.readS32();
                if (hash < 0) continue;

                const key = e.add(8).readS32();
                const value = e.add(16).readPointer();
                if (value.isNull()) continue;

                let cls = '<unknown>';
                try {
                    const k = api.object_get_class(value);
                    if (!k.isNull()) cls = api.class_get_name(k).readCString();
                } catch (e) {}

                if (key === 20000000 || cls === 'ProtoChapter') {
                    let chapterId = '<read-failed>';
                    let boxStatus = '<read-failed>';
                    try { chapterId = String(value.add(0x10).readS32()); } catch (e) {}
                    try { boxStatus = String(value.add(0x1c).readS32()); } catch (e) {}
                    console.log('[CHAPTER_ENTRY] idx=' + i +
                        ' key=' + key +
                        ' hash=' + hash +
                        ' value=' + value +
                        ' class=' + cls +
                        ' ChapterId=' + chapterId +
                        ' BoxStatus=' + boxStatus);
                    found++;
                }
            } catch (e) {}
        }

        console.log('[CHAPTERS_ENUM_END] scanned=' + limit + ' matches=' + found);
    } catch (e) {
        console.log('[CHAPTERS_ENUM_ERR] ' + e.message);
    }
}

// v4.17: identify KCPTube.Send request class and opcode without dumping payloads.\n// v4.16: identify the actual transport used by post-login/in-game responses.
    // Observation only: no packet contents or authentication material are printed.
    try {
        const transportSpecs = [
            ['Alioth.S1.Net.TCPTube', 'TryRead'],
            ['Alioth.S1.Net.TCPTube', 'TryOutput'],
            ['Alioth.S1.Net.TCPTube', 'Update'],
            ['Alioth.S1.Net.KCPTube', 'TryRead'],
            ['Alioth.S1.Net.KCPTube', 'TryOutput'],
            ['Alioth.S1.Net.KCPTube', 'Update'],
            ['Alioth.S1.Net.KCPTube', 'Send'],
            ['Alioth.S1.Net.KCPTube', 'Receive']
        ];
        for (const spec of transportSpecs) {
            const ms = findMethodsAnywhereByName(spec[0], spec[1]);
            for (const m of ms) {
                console.log('[+] Hooking TRANSPORT ' + spec[0] + '.' + spec[1] + '(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
                Interceptor.attach(m.fnPtr, {
                    onEnter(args) {
                        this.t0 = Date.now();
                        this.transport = spec[0].split('.').pop();
                        this.method = spec[1];
                        const transportLine = '[TRANSPORT] ' + this.transport + '.' + this.method + ' enter this=' + describeObjectPtr(args[0]);
                        if (this.transport === 'KCPTube' && this.method === 'Send') console.log(transportLine);
                        else logThrottled('transport-enter:' + this.transport + ':' + this.method, 2000, transportLine);
                        if (this.transport === 'KCPTube' && this.method === 'Send') {
                            this.kcpRequest = args[1];
                            this.kcpRequestInfo = describeKcpSendRequest(args[1]);
                            console.log('[KCP_SEND_ARGS] signature=(' + m.typeNames.join(', ') + ')' +
                                ' arg1=' + this.kcpRequestInfo +
                                ' arg2=' + describeObjectPtr(args[2]) +
                                ' arg3=' + describeObjectPtr(args[3]));
                        }
                    },
                    onLeave(retval) {
                        try {
                            let rv = '?';
                            if (retval && typeof retval.toInt32 === 'function') rv = retval.toInt32();
                            const transportLine = '[TRANSPORT] ' + this.transport + '.' + this.method + ' leave ret=' + rv + ' ' + (Date.now() - this.t0) + 'ms';
                            if (this.transport === 'KCPTube' && this.method === 'Send') console.log(transportLine);
                            else logThrottled('transport-leave:' + this.transport + ':' + this.method, 2000, transportLine);
                            if (this.transport === 'KCPTube' && this.method === 'Send' && rv === 1) {
                                console.log('[KCP_SEND_ACCEPTED] ' + (this.kcpRequestInfo || 'request=unknown'));
                            }
                        } catch (e) {}
                    }
                });
                hookCount++;
            }
        }
    } catch (e) {
        console.log('[!] Transport hook setup failed: ' + e.message);
    }

// v4.9: network response processing observation.
    // TryHandleResponse owns the queued response object locally; its invocation
    // proves the response-processing path is active. ProccessRequestRes receives
    // the response object as arg[1] (confirmed by static Listing @ 015b41e0).
    try {
        const thrs = findMethodsAnywhereByName('Alioth.S1.Net.NetworkCenter', 'TryHandleResponse');
        for (const m of thrs) {
            console.log('[+] Hooking NetworkCenter.TryHandleResponse(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
            Interceptor.attach(m.fnPtr, {
                onEnter(args) {
                    this.t = Date.now();
                    logThrottled('net-resp-try-enter', 1500, '[NET_RESP] TryHandleResponse enter this=' + describeObjectPtr(args[0]));
                },
                onLeave(retval) {
                    logThrottled('net-resp-try-leave', 1500, '[NET_RESP] TryHandleResponse leave ' + (Date.now() - this.t) + 'ms');
                }
            });
            // TryHandleResponse static branch: +0x238 loads sp+0x44,
            // and status >= 5 skips DataCenter.ProccessRequestRes.
            try {
                const statusPc = m.fnPtr.add(0x238);
                Interceptor.attach(statusPc, {
                    onEnter() {
                        try {
                            const status = this.context.sp.add(0x44).readU8();
                            console.log('[NET_RESP_STATUS] status=' + status +
                                ' route=' + (status < 5 ? 'ProccessRequestRes' : 'skip'));
                        } catch (e) {
                            console.log('[NET_RESP_STATUS] read failed: ' + e.message);
                        }
                    }
                });
                console.log('[+] Hooking TryHandleResponse status branch @ ' + statusPc);
                hookCount++;
            } catch (e) {
                console.log('[!] TryHandleResponse status hook failed: ' + e.message);
            }
            hookCount++;
        }
        if (!thrs.length) console.log('[!] NetworkCenter.TryHandleResponse not found');
    } catch (e) {
        console.log('[!] TryHandleResponse hook failed: ' + e.message);
    }

    try {
        const prs = findMethodsAnywhereByName('DataCenter', 'ProccessRequestRes');
        for (const m of prs) {
            console.log('[+] Hooking DataCenter.ProccessRequestRes(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
            Interceptor.attach(m.fnPtr, {
                onEnter(args) {
                    const response = args[1];
                    logThrottled('net-resp-process-enter', 1000, '[NET_RESP] ProccessRequestRes enter' +
                        ' this=' + describeObjectPtr(args[0]) +
                        ' response=' + describeObjectPtr(response) +
                        ' arg2=' + (args[2] || ptr(0)));
                    inspectResponseObject(response);
                    try {
                        const raw = response.add(0xc0).readPointer();
                        console.log('[CHAPTERS_RAW] response=' + response + ' +0xc0=' + (raw.isNull() ? 'null' : describeObjectPtr(raw)));
                        if (!raw.isNull()) inspectChaptersDictionary(raw);
                    } catch (e) { console.log('[CHAPTERS_RAW] read failed: ' + e.message); }
                },
                onLeave(retval) {
                    logThrottled('net-resp-process-leave', 1000, '[NET_RESP] ProccessRequestRes leave');
                }
            });
            hookCount++;
        }
        if (!prs.length) console.log('[!] DataCenter.ProccessRequestRes not found');
    } catch (e) {
        console.log('[!] ProccessRequestRes hook failed: ' + e.message);
    }

    // v4.15: inspect only the first Login(OpCode=2) bootstrap dictionaries.\n    let bootstrapDumped = false;\n    function dumpBootstrapDict(dictPtr, tag) {\n        try {\n            if (!dictPtr || dictPtr.isNull()) { console.log('[BOOT_DICT] '+tag+'=null'); return; }\n            const klass=api.object_get_class(dictPtr);\n            const name=api.class_get_name(klass).readCString();\n            const cf=api.class_get_field_from_name(klass,Memory.allocUtf8String('_count'));\n            const ef=api.class_get_field_from_name(klass,Memory.allocUtf8String('_entries'));\n            if(cf.isNull()||ef.isNull()){console.log('[BOOT_DICT] '+tag+' type='+name+' fields=missing');return;}\n            const countOff=api.field_get_offset(cf), entriesOff=api.field_get_offset(ef);\n            const count=dictPtr.add(countOff).readS32(), entries=dictPtr.add(entriesOff).readPointer();\n            console.log('[BOOT_DICT] '+tag+' type='+name+' count='+count);\n            if(entries.isNull()||count<=0||count>100000)return;\n            const len=entries.add(24).readU32(), limit=Math.min(len,100);\n            for(let i=0;i<limit;i++){try{const e=entries.add(32+i*24),hash=e.readS32();if(hash<0)continue;const key=e.add(8).readS32(),value=e.add(16).readPointer();if(value.isNull())continue;let cls='<unknown>';try{const k=api.object_get_class(value);if(!k.isNull())cls=api.class_get_name(k).readCString();}catch(x){}\n                if(tag==='Chapters' && cls==='ProtoChapter'){let id='?',st='?',pr='?',box='?';try{id=String(value.add(0x10).readS32());}catch(x){}try{st=String(value.add(0x14).readS32());}catch(x){}try{pr=String(value.add(0x18).readS32());}catch(x){}try{box=String(value.add(0x1c).readS32());}catch(x){}console.log('[BOOT_CHAPTER] key='+key+' Id='+id+' Status='+st+' Progress='+pr+' BoxStatus='+box+' ptr='+value);}\n                else if(tag==='Items'){console.log('[BOOT_ITEM] key='+key+' class='+cls+' ptr='+value);}\n            }catch(x){}}\n            console.log('[BOOT_DICT_END] '+tag+' scanned='+limit);\n        }catch(e){console.log('[BOOT_DICT_ERR] '+tag+' '+e.message);}\n    }\n\n    // v4.14: login->main bootstrap response correlation.
    // OpInfo layout: +0x14=OpCode. Dump response sequence and key state pointers
    // at ProccessRequestRes entry so the first post-login response can be identified.
    let responseSeq = 0;
    let bootstrapDumped = false;
    try {
        const prs = findMethodsAnywhereByName('DataCenter', 'ProccessRequestRes');
        for (const m of prs) {
            Interceptor.attach(m.fnPtr, {
                onEnter(args) {
                    try {
                        const response = args[1];
                        responseSeq++;
                        let opcode = '<read-failed>';
                        let returnCode = '<read-failed>';
                        try { opcode = String(response.add(0x14).readU16()); } catch (e) {}
                        try { returnCode = String(response.add(0x18).readS32()); } catch (e) {}
                        console.log('[BOOT_RESP] seq=' + responseSeq +
                            ' response=' + response +
                            ' class=' + describeObjectPtr(response) +
                            ' OpCode=' + opcode +
                            ' ReturnCode=' + returnCode);
                        try {
                            const user = response.add(0x88).readPointer();
                            console.log('[BOOT_STATE] User@+0x88=' + (user.isNull() ? 'null' : describeObjectPtr(user)));
                            if (!user.isNull()) {
                                try { console.log('[BOOT_USER] Id=' + user.add(0x10).readU64() +
                                    ' Level=' + user.add(0x1c).readU32() +
                                    ' Exp=' + user.add(0x20).readU32()); } catch (e) {}
                            }
                        } catch (e) {}
                        try {
                            const items = response.add(0x98).readPointer();
                            console.log('[BOOT_STATE] Items@+0x98=' + (items.isNull() ? 'null' : describeObjectPtr(items)));
                        } catch (e) {}
                        try {
                            const heros = response.add(0x90).readPointer();
                            console.log('[BOOT_STATE] Heros@+0x90=' + (heros.isNull() ? 'null' : describeObjectPtr(heros)));
                        } catch (e) {}
                        try {
                            const chapters = response.add(0xc0).readPointer();
                            console.log('[BOOT_STATE] Chapters@+0xc0=' + (chapters.isNull() ? 'null' : describeObjectPtr(chapters)));
                        } catch (e) {}
                        if(responseSeq===1 && opcode==='2' && !bootstrapDumped){
                            bootstrapDumped=true;
                            try { dumpBootstrapDict(items,'Items'); } catch(e) {}
                            try { dumpBootstrapDict(chapters,'Chapters'); } catch(e) {}
                        }
                    } catch (e) {
                        console.log('[BOOT_RESP] read failed: ' + e.message);
                    }
                }
            });
            hookCount++;
        }
    } catch (e) { console.log('[!] Bootstrap response hook failed: ' + e.message); }

    // UserInfo getters are useful after DataCenter state merge to capture the
    // actual main-screen values without exposing authentication tokens.
    try {
        const getterSpecs = [
            ['Coins', []],
            ['Energy', []],
            ['Exp', []],
            ['Level', []]
        ];
        for (const spec of getterSpecs) {
            const ms = findMethodsAnywhereByName('UserInfo', 'get_' + spec[0]);
            for (const m of ms) {
                console.log('[+] Hooking UserInfo.get_' + spec[0] + ' @ ' + m.fnPtr);
                Interceptor.attach(m.fnPtr, {
                    onEnter(args) { this.obj = args[0]; },
                    onLeave(retval) {
                        try {
                            const v = typeof retval === 'number' ? retval : retval.toInt32();
                            logOnChange('main-currency:' + spec[0] + ':' + this.obj, v, '[MAIN_CURRENCY] ' + spec[0] + '=' + v + ' UserInfo=' + this.obj);
                        } catch (e) {}
                    }
                });
                hookCount++;
            }
        }
    } catch (e) { console.log('[!] Main currency getter hook failed: ' + e.message); }

    // v4.22: HeroInfo.InitHero + getter correlation for Bootstrap Hero fields.
    // Goal: correlate the source Hero object passed to InitHero with the
    // HeroInfo values actually consumed by Hero/Main UI.
    function describeManagedFields(obj, tag, maxFields) {
        try {
            if (!obj || obj.isNull()) { console.log('[HERO_FIELDS] ' + tag + '=null'); return; }
            const klass = api.object_get_class(obj);
            if (klass.isNull()) return;
            const className = api.class_get_name(klass).readCString();
            const iter = Memory.alloc(Process.pointerSize); iter.writePointer(ptr(0));
            let n = 0;
            console.log('[HERO_FIELDS] ' + tag + ' class=' + className + ' ptr=' + obj);
            while (n < (maxFields || 80)) {
                const f = api.class_get_fields(klass, iter);
                if (f.isNull()) break;
                let name='?', off='?', type='?';
                try { name=api.field_get_name(f).readCString(); } catch(e) {}
                try { off='0x'+api.field_get_offset(f).toString(16); } catch(e) {}
                try { type=api.type_get_name(api.field_get_type(f)).readCString(); } catch(e) {}
                let val='';
                try {
                    const fo=api.field_get_offset(f);
                    if (type.indexOf('System.Int32')>=0) val=' value='+obj.add(fo).readS32();
                    else if (type.indexOf('System.UInt32')>=0) val=' value='+obj.add(fo).readU32();
                    else if (type.indexOf('System.Int64')>=0) val=' value='+obj.add(fo).readS64();
                    else if (type.indexOf('System.UInt64')>=0) val=' value='+obj.add(fo).readU64();
                    else if (type.indexOf('System.Boolean')>=0) val=' value='+(obj.add(fo).readU8()!==0);
                    else if (type.indexOf('System.Single')>=0) val=' value='+obj.add(fo).readFloat();
                    else if (type.indexOf('System.Double')>=0) val=' value='+obj.add(fo).readDouble();
                    else if (type.indexOf('System.String')>=0) { const p=obj.add(fo).readPointer(); val=' value='+readIl2cppString(p); }
                    else if (type.indexOf('System.')<0) { const p=obj.add(fo).readPointer(); val=' ref='+(p.isNull()?'null':describeObjectPtr(p)); }
                } catch(e) {}
                console.log('  ' + name + ' @' + off + ' type=' + type + val);
                n++;
            }
        } catch(e) { console.log('[HERO_FIELDS_ERR] '+tag+' '+e.message); }
    }
    try {
        const init = findMethodAnywhereExact('HeroInfo', 'InitHero', ['System.Object','System.Object']);
        if (init) {
            console.log('[+] Hooking HeroInfo.InitHero @ ' + init.fnPtr);
            Interceptor.attach(init.fnPtr, {
                onEnter(args) {
                    this.heroInfo=args[0]; this.source=args[1];
                    console.log('[HERO_INIT] this=' + describeObjectPtr(args[0]) +
                        ' source=' + describeObjectPtr(args[1]) +
                        ' arg2=' + describeObjectPtr(args[2]));
                    try { describeManagedFields(args[1], 'InitHero.source', 60); } catch(e) {}
                },
                onLeave(retval) {
                    try { describeManagedFields(this.heroInfo, 'InitHero.result', 80); } catch(e) {}
                }
            });
            hookCount++;
        } else {
            // Fallback: resolve by name/parameter count if generated type names differ.
            const ms=findMethodsAnywhereByName('HeroInfo','InitHero');
            for(const m of ms) {
                console.log('[+] Hooking HeroInfo.InitHero(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
                Interceptor.attach(m.fnPtr, {
                    onEnter(args) {
                        this.heroInfo=args[0]; this.source=args[1];
                        console.log('[HERO_INIT] this=' + describeObjectPtr(args[0]) +
                            ' source=' + describeObjectPtr(args[1]) +
                            ' arg2=' + describeObjectPtr(args[2]));
                        try { describeManagedFields(args[1], 'InitHero.source', 60); } catch(e) {}
                    },
                    onLeave(retval) {
                        try { describeManagedFields(this.heroInfo, 'InitHero.result', 80); } catch(e) {}
                    }
                });
                hookCount++;
            }
        }
    } catch(e) { console.log('[!] HeroInfo.InitHero hook failed: '+e.message); }

    try {
        const heroGetterSpecs=['Level','Star','State','FashionId','Weapon','WeaponInfomation'];
        for(const name of heroGetterSpecs) {
            const ms=findMethodsAnywhereByName('HeroInfo','get_'+name);
            for(const m of ms) {
                console.log('[+] Hooking HeroInfo.get_'+name+' @ '+m.fnPtr);
                Interceptor.attach(m.fnPtr,{
                    onEnter(args){this.obj=args[0];},
                    onLeave(retval){
                        try {
                            let out='';
                            if (name==='Weapon' || name==='WeaponInfomation') {
                                out=describeRetval(retval);
                            } else {
                                out=String(retval.toInt32());
                            }
                            logOnChange('hero-get:'+name+':'+this.obj,out,
                                '[HERO_GET] '+name+'='+out+' HeroInfo='+this.obj);
                        } catch(e) {}
                    }
                });
                hookCount++;
            }
        }
    } catch(e) { console.log('[!] HeroInfo getter hook failed: '+e.message); }

    // v4.20: trace the warehouse's cached-list binding path.
    // Only log object classes, known collection counts, and ProtoItem's documented scalar fields.
    function describeWarehouseCollection(obj) {
        try {
            if (!obj || obj.isNull()) return 'null';
            const klass = api.object_get_class(obj);
            if (klass.isNull()) return 'klass=null@' + obj;
            const name = api.class_get_name(klass).readCString();
            if (name.indexOf('Dictionary') >= 0) {
                let count = '?';
                try { count = String(obj.add(0x20).readS32()); } catch (e) {}
                return name + '@' + obj + ' count=' + count;
            }
            if (name.indexOf('List') >= 0) {
                let count = '?';
                try { count = String(obj.add(0x18).readS32()); } catch (e) {}
                return name + '@' + obj + ' count=' + count;
            }
            return name + '@' + obj;
        } catch (e) {
            return 'collection-inspect-failed@' + obj;
        }
    }
    function describeWarehousePanel(panel) {
        try {
            if (!panel || panel.isNull()) return 'panel=null';
            let mode = '?';
            try { mode = String(panel.add(0xd4).readS32()); } catch (e) {}
            const fields = [0xd8, 0xe0, 0xe8, 0xf0, 0xf8];
            const names = ['list_d8', 'list_e0', 'list_e8', 'list_f0', 'selected_f8'];
            const parts = ['mode=' + mode];
            for (let i = 0; i < fields.length; i++) {
                try {
                    const p = panel.add(fields[i]).readPointer();
                    parts.push(names[i] + '=' + describeWarehouseCollection(p));
                } catch (e) { parts.push(names[i] + '=<read-failed>'); }
            }
            return parts.join(' ');
        } catch (e) {
            return 'panel-state-failed:' + e.message;
        }
    }
    function describeWarehouseArg(obj) {
        try {
            if (!obj || obj.isNull()) return 'null';
            const klass = api.object_get_class(obj);
            if (klass.isNull()) return 'klass=null@' + obj;
            const name = api.class_get_name(klass).readCString();
            let out = name + '@' + obj;
            if (name === 'ProtoItem') {
                try { out += ' Id=' + obj.add(0x10).readS32(); } catch (e) {}
                try { out += ' Status=' + obj.add(0x14).readS32(); } catch (e) {}
                try { out += ' Count=' + obj.add(0x18).readS32(); } catch (e) {}
            }
            return out;
        } catch (e) {
            return 'arg-inspect-failed@' + obj;
        }
    }
    try {
        const warehouseSpecs = [
            'DemandOpen', 'RefreshWareHouse', 'InitData',
            'ShowGoods', 'RefreshScroll', 'SetGoodsItemByInfo',
            'RefreshEquipItem'
        ];
        for (const methodName of warehouseSpecs) {
            const ms = findMethodsAnywhereByName('WareHousePanelMono', methodName);
            for (const m of ms) {
                console.log('[+] Hooking WAREHOUSE ' + methodName + '(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
                Interceptor.attach(m.fnPtr, {
                    onEnter(args) {
                        this.t0 = Date.now();
                        this.methodName = methodName;
                        this.panel = args[0];
                        if (methodName === 'SetGoodsItemByInfo') {
                            console.log('[WAREHOUSE_ITEM] enter panel=' + describeObjectPtr(args[0]) +
                                ' arg1=' + describeWarehouseArg(args[1]) +
                                ' arg2=' + describeWarehouseArg(args[2]));
                        } else {
                            logThrottled('warehouse-enter:' + methodName + ':' + args[0], 1500,
                                '[WAREHOUSE] ' + methodName + ' enter this=' + describeObjectPtr(args[0]));
                            if (methodName === 'InitData' || methodName === 'ShowGoods' || methodName === 'RefreshScroll') {
                                console.log('[WAREHOUSE_STATE] ' + methodName + ' ' + describeWarehousePanel(args[0]));
                            }
                        }
                    },
                    onLeave(retval) {
                        try {
                            if (methodName === 'InitData' || methodName === 'RefreshWareHouse' || methodName === 'ShowGoods') {
                                console.log('[WAREHOUSE_STATE] ' + methodName + ' leave ' + describeWarehousePanel(this.panel));
                            }
                            logThrottled('warehouse-leave:' + methodName + ':' + this.panel, 1500,
                                '[WAREHOUSE] ' + methodName + ' leave ' + (Date.now() - this.t0) + 'ms');
                        } catch (e) {}
                    }
                });
                hookCount++;
            }
        }
    } catch (e) {
        console.log('[!] Warehouse hook setup failed: ' + e.message);
    }

    // MergeItem receives Bootstrap/OpInfo item dictionaries and updates DataCenter's cache.
    try {
        const mergeMethods = findMethodsAnywhereByName('DataCenter', 'MergeItem');
        for (const m of mergeMethods) {
            console.log('[+] Hooking DataCenter.MergeItem(' + m.typeNames.join(', ') + ') @ ' + m.fnPtr);
            Interceptor.attach(m.fnPtr, {
                onEnter(args) {
                    this.t0 = Date.now();
                    logThrottled('item-merge-enter:' + args[0], 1500,
                        '[ITEM_MERGE] enter this=' + describeObjectPtr(args[0]) +
                        ' incoming=' + describeWarehouseCollection(args[1]));
                },
                onLeave(retval) {
                    logThrottled('item-merge-leave', 1500, '[ITEM_MERGE] leave ' + (Date.now() - this.t0) + 'ms');
                }
            });
            hookCount++;
        }
        if (!mergeMethods.length) console.log('[!] DataCenter.MergeItem not found');
    } catch (e) {
        console.log('[!] DataCenter.MergeItem hook failed: ' + e.message);
    }

    // v4.8: ProtoChapter BoxStatus runtime observation.
    // The setter itself is only a 2-instruction backing-field write, so this
    // hook is a control observation point, not proof that protobuf-net calls it.
    try {
        const bsGet = findMethodAnywhereExact('Alioth.S1.Common.ProtoChapter', 'get_BoxStatus', []);
        const bsSet = findMethodAnywhereExact('Alioth.S1.Common.ProtoChapter', 'set_BoxStatus', ['System.Int32']);
        if (bsGet) {
            Interceptor.attach(bsGet.fnPtr, {
                onEnter(args) { this.obj = args[0]; },
                onLeave(retval) {
                    try {
                        const v = retval.toInt32();
                        const raw = this.obj.add(0x1c).readU32();
                        logOnChange('boxstatus-get:' + this.obj, v + ':' + raw, '[BOXSTATUS_GET] obj=' + this.obj + ' ret=' + v + ' raw+0x1c=' + raw);
                    } catch (e) { console.log('[BOXSTATUS_GET] read failed: ' + e.message); }
                }
            });
            hookCount++;
            console.log('[+] Hooking ProtoChapter.get_BoxStatus @ ' + bsGet.fnPtr);
        } else console.log('[!] ProtoChapter.get_BoxStatus not found');
        if (bsSet) {
            Interceptor.attach(bsSet.fnPtr, {
                onEnter(args) {
                    this.obj = args[0];
                    try {
                        console.log('[BOXSTATUS_SET] obj=' + args[0] + ' arg=' + args[1].toInt32() +
                            ' old+0x1c=' + args[0].add(0x1c).readU32());
                    } catch (e) { console.log('[BOXSTATUS_SET] read failed: ' + e.message); }
                },
                onLeave(retval) {
                    try {
                        const obj = this.obj;
                        if (obj && !obj.isNull())
                            console.log('[BOXSTATUS_SET_END] obj=' + obj + ' new+0x1c=' + obj.add(0x1c).readU32());
                    } catch (e) {}
                }
            });
            hookCount++;
            console.log('[+] Hooking ProtoChapter.set_BoxStatus @ ' + bsSet.fnPtr);
        } else console.log('[!] ProtoChapter.set_BoxStatus not found');
    } catch (e) { console.log('[!] ProtoChapter BoxStatus hook failed: ' + e.message); }

    // v4.10: observe OpInfo.Chapters directly through the accessor.
    try {
        const chGet = findMethodAnywhereExact('Alioth.S1.Common.OpInfo', 'get_Chapters', []);
        if (chGet) {
            Interceptor.attach(chGet.fnPtr, {
                onEnter(args) { this.obj = args[0]; },
                onLeave(retval) {
                    try {
                        const chaptersRet = retval.isNull() ? 'null' : describeObjectPtr(retval);
                        logOnChange('chapters-get:' + this.obj, chaptersRet,
                            '[CHAPTERS_GET] OpInfo=' + this.obj + ' ret=' + chaptersRet);
                        if (!retval.isNull()) {
                            try {
                                const klass = api.object_get_class(retval);
                                const kname = api.class_get_name(klass).readCString();
                                console.log('[CHAPTERS_DICT] type=' + kname + ' ptr=' + retval);
                                const countField = api.class_get_field_from_name(klass, Memory.allocUtf8String('_count'));
                                if (!countField.isNull()) {
                                    const off = api.field_get_offset(countField);
                                    console.log('[CHAPTERS_DICT] _count@+0x' + off.toString(16) + '=' + retval.add(off).readU32());
                                }
                            } catch (e) { console.log('[CHAPTERS_DICT] inspect failed: ' + e.message); }
                        }
                    } catch (e) { console.log('[CHAPTERS_GET] read failed: ' + e.message); }
                }
            });
            hookCount++;
            console.log('[+] Hooking OpInfo.get_Chapters @ ' + chGet.fnPtr);
        } else console.log('[!] OpInfo.get_Chapters not found');
    } catch (e) { console.log('[!] OpInfo.Chapters hook failed: ' + e.message); }

    console.log('[*] justice_hook v4.21');
    console.log(`\n[*] ${hookCount} hooks installed.`);
    console.log('[*] Trigger login, then make a real game API request after login.');
    console.log('[*] Look for [TOKEN_SAVE], [TOKEN_GET], [TOKEN_COMPARE], [SIGN_DATA], [JOIN_DATA], [MD5_DATA], [B64], [HTTP_CREATE], [HTTP_HEADER], and [HTTP_SEND] lines.\n');
}

main();
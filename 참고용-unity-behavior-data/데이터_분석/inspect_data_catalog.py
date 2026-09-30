#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정규화된 Local Data의 실제 Record 구조를 통계적으로 요약한다."""

from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

DEFAULT_INPUT = Path(__file__).resolve().parent / 'output' / 'normalized' / 'all_records.ndjson'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'output' / 'data_catalog'

def iter_ndjson(path: Path) -> Iterable[dict]:
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj

def value_type(v: Any) -> str:
    if v is None: return 'null'
    if isinstance(v, bool): return 'bool'
    if isinstance(v, int): return 'int'
    if isinstance(v, float): return 'float'
    if isinstance(v, str): return 'string'
    if isinstance(v, list): return 'list'
    if isinstance(v, dict): return 'object'
    return type(v).__name__

def schema_signature(record: dict) -> str:
    return '|'.join(sorted(record.keys()))

def compact(v: Any, max_string=180, max_items=8):
    if isinstance(v, str): return v if len(v) <= max_string else v[:max_string] + '…'
    if isinstance(v, list): return [compact(x, max_string, max_items) for x in v[:max_items]]
    if isinstance(v, dict):
        out = {k: compact(v[k], max_string, max_items) for k in list(v)[:max_items]}
        if len(v) > max_items: out['__truncated__'] = True
        return out
    return v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument('--top-schemas', type=int, default=100)
    ap.add_argument('--top-fields', type=int, default=200)
    ap.add_argument('--samples-per-system', type=int, default=8)
    ap.add_argument('--samples-per-schema', type=int, default=3)
    args = ap.parse_args()
    if not args.input.exists(): raise SystemExit(f'입력 파일이 없습니다: {args.input}')
    args.output.mkdir(parents=True, exist_ok=True)
    record_count = 0
    schemas = Counter(); fields = Counter(); systems = Counter()
    by_system = defaultdict(Counter); types = defaultdict(Counter)
    samples_system = defaultdict(list); samples_schema = defaultdict(list)
    for obj in iter_ndjson(args.input):
        record = obj.get('record') if isinstance(obj.get('record'), dict) else obj
        record_count += 1
        sig = schema_signature(record); schemas[sig] += 1
        cs = obj.get('system_candidates') or ['other']
        if not isinstance(cs, list): cs = [str(cs)]
        for system in cs:
            system = str(system); systems[system] += 1
            for k in record: by_system[system][k] += 1
            if len(samples_system[system]) < args.samples_per_system:
                samples_system[system].append({'record_id': obj.get('record_id'), 'source_file': obj.get('source_file'), 'source_path': obj.get('source_path'), 'record': compact(record)})
        for k, v in record.items(): fields[k] += 1; types[k][value_type(v)] += 1
        if len(samples_schema[sig]) < args.samples_per_schema:
            samples_schema[sig].append({'record_id': obj.get('record_id'), 'source_file': obj.get('source_file'), 'system_candidates': cs, 'record': compact(record)})
    def dump(name, data):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    top_schema = [{'count': n, 'field_count': len(sig.split('|')) if sig else 0, 'fields': sig.split('|') if sig else []} for sig,n in schemas.most_common(args.top_schemas)]
    dump('06_schema_signatures.json', {'record_count': record_count, 'unique_schema_signatures': len(schemas), 'top_schema_signatures': top_schema})
    dump('07_field_by_system.json', {'record_count': record_count, 'systems': {s: [{'field':k,'count':n} for k,n in c.most_common(args.top_fields)] for s,c in by_system.items()}})
    dump('08_field_types.json', {'record_count': record_count, 'fields': {k: dict(c) for k,c in types.items()}})
    dump('09_record_samples.json', {'samples_per_system': args.samples_per_system, 'samples_per_schema': args.samples_per_schema, 'by_system': dict(samples_system), 'by_schema': dict(samples_schema)})
    lines=['# Data Catalog Structural Overview','','정규화된 Local Data의 실제 Record 구조를 통계적으로 요약한 결과이다.','',f'- Record: {record_count:,}',f'- 고유 schema signature: {len(schemas):,}','']
    lines += ['## System candidate'] + [f'- {s}: {n:,}' for s,n in systems.most_common()] + ['', '## 상위 Schema Signature']
    for i,x in enumerate(top_schema[:30],1):
        fs=', '.join(x['fields'][:20]) + (', …' if len(x['fields'])>20 else '')
        lines.append(f'{i}. {x["count"]:,} records / {x["field_count"]} fields — {fs}')
    lines += ['', '## 상위 Field'] + [f'- {k}: {n:,}' for k,n in fields.most_common(50)]
    lines += ['', '## 원칙', '- Schema signature는 구조 묶음 확인용이다.', '- system candidate는 의미 확정값이 아니다.', '- Field type은 자료형만 기록한다.', '- 샘플은 사실 확인용으로 제한한다.', '- Unknown / Server Candidate는 별도로 유지한다.']
    (args.output/'catalog_overview.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f'Record: {record_count:,}')
    print(f'Unique schema signatures: {len(schemas):,}')
    print(f'System candidates: {len(systems):,}')
    print(f'Output: {args.output}')
    for x in ['06_schema_signatures.json','07_field_by_system.json','08_field_types.json','09_record_samples.json','catalog_overview.md']: print('  '+x)

if __name__ == '__main__': main()
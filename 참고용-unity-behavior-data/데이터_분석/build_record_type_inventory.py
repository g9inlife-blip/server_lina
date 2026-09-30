#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정규화 Record를 원본 source_file/구조 단위로 집계한다. 의미 추론은 하지 않는다."""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parent
IN=BASE/'output'/'normalized'/'all_records.ndjson'
OUT=BASE/'output'/'data_catalog'

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,default=IN); ap.add_argument('--output',type=Path,default=OUT); a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 files=defaultdict(lambda:{'count':0,'systems':Counter(),'schemas':Counter(),'fields':Counter(),'ids':[]})
 for line in a.input.open(encoding='utf-8'):
  try:o=json.loads(line)
  except:continue
  r=o.get('record',o); sf=o.get('source_file','unknown'); d=files[sf]; d['count']+=1
  cs=o.get('system_candidates') or ['other']
  for s in cs:d['systems'][str(s)]+=1
  sig='|'.join(sorted(r.keys())); d['schemas'][sig]+=1
  for k in r:d['fields'][k]+=1
  if len(d['ids'])<5:d['ids'].append(o.get('record_id'))
 result={}
 for sf,d in sorted(files.items()):
  result[sf]={'record_count':d['count'],'system_candidates':dict(d['systems'].most_common()),'schema_signatures':[{'count':n,'fields':sig.split('|') if sig else []} for sig,n in d['schemas'].most_common()],'top_fields':[{'field':k,'count':n} for k,n in d['fields'].most_common(80)],'sample_record_ids':d['ids']}
 (a.output/'10_record_type_inventory.json').write_text(json.dumps({'source_file_count':len(result),'files':result},ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# Record Type Inventory','',f'- source files: {len(result):,}','- 의미 추론 없음: source_file과 실제 구조/필드 반복만 집계','']
 for sf,d in sorted(result.items(),key=lambda x:-x[1]['record_count']):
  systems=', '.join(f'{k}:{v}' for k,v in d['system_candidates'].items())
  sig=d['schema_signatures'][0]; lines.append(f'## {sf} — {d["record_count"]:,} records'); lines.append(f'- candidate: {systems}'); lines.append(f'- schema fields: {len(sig["fields"])}'); lines.append(f'- fields: {", ".join(sig["fields"])}'); lines.append('')
 (a.output/'10_record_type_inventory.md').write_text('\n'.join(lines),encoding='utf-8')
 print(f'Record: {sum(x["record_count"] for x in result.values()):,}'); print(f'Source files: {len(result):,}'); print(f'Output: {a.output}')
if __name__=='__main__':main()
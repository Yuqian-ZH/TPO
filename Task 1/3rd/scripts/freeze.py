from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,shutil
from frozen_common import BASE,ROOT,read,save,binding,check_source

def main():
 assert not (ROOT/'protocol.json').exists(),'Protocol already frozen'
 assert read(ROOT/'preflight/generation_status.json')['state']=='complete'
 assert read(ROOT/'preflight/replay_verification.json')['state']=='PASS'
 annotations=read(ROOT/'preflight/eval_out/step2/annotations.json')
 assert len(annotations)==3 and all(1<=r['preference']<=2 for r in annotations)
 assert any(abs(r['preference']-1.5)>1e-8 for r in annotations)
 check_source()
 import guard_data
 shutil.copy2(ROOT/'protocol.draft.json',ROOT/'protocol.json')
 record={'binding':binding(),'frozen_at':datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),'protocol_sha256':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),'scripts':{str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((BASE/'scripts').glob('*')) if p.is_file()},'preflight':'PASS','formal_runs_authorized':{'TPO':1,'bon15':1}}
 save(ROOT/'freeze.json',record)
 config=read(ROOT/'run_config.json');config.update(state='frozen',freeze=record);save(ROOT/'run_config.json',config)
 print('PROTOCOL_FROZEN',record['binding'])
if __name__=='__main__':main()

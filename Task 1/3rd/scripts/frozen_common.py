from pathlib import Path
import hashlib, json, os, threading, time
BASE=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('FROZEN_RUN_DIR',BASE/(BASE/'LATEST.txt').read_text().strip())).resolve()
SOURCE=ROOT/'source/TPO'
LOCK=threading.Lock()
def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n');temp.replace(p)
def event(path,row):
 with LOCK,Path(path).open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def seed(bid,stage,iteration,index):
 return int.from_bytes(hashlib.sha256(f'task1_frozen_v1|7|{bid}|{stage}|{iteration}|{index}'.encode()).digest()[:4],'big')&0x7fffffff
def retryable(e):return type(e).__name__ in ['APIConnectionError','APITimeoutError','ConnectError','ReadTimeout','ConnectionError'] or getattr(e,'status_code',None) in [429,500,502,503,504]
def binding():
 protocol=ROOT/('protocol.json' if (ROOT/'protocol.json').exists() else 'protocol.draft.json')
 return sha({'protocol':read(protocol),'source':read(ROOT/'source_hashes.json'),'data':read(ROOT/'data_hashes.json'),'scripts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'scripts'/name for name in ['frozen_common.py','frozen_engine.py','generate.py']]}})
def check_source():
 for p,h in read(ROOT/'source_hashes.json').items():assert hashlib.sha256((SOURCE/p).read_bytes()).hexdigest()==h,p

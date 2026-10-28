"""Call unchanged official algorithms with a persistent pool and replayable requests."""
import argparse, concurrent.futures, fcntl, hashlib, json, os, sys, time
from types import SimpleNamespace
from pathlib import Path
from frozen_common import BASE,ROOT,SOURCE,read,save,binding,check_source
sys.dont_write_bytecode=True
sys.path[:0]=[str(SOURCE/'textgrad-main'),str(SOURCE)]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');a=ap.parse_args()
 root=ROOT/'preflight' if a.preflight else ROOT
 os.chdir(root);os.environ['XDG_CACHE_HOME']=str(root/'cache');os.environ['PYTHONDONTWRITEBYTECODE']='1'
 lock=(root/'generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 check_source();bind=binding()
 if not a.preflight:
  assert (ROOT/'freeze.json').exists(),'Not frozen'
  assert read(ROOT/'freeze.json')['binding']==bind,'Frozen code/config mismatch'
 old=read(root/'generation_status.json') if (root/'generation_status.json').exists() else None
 if old:assert old['binding']==bind,'Resume binding mismatch'
 from frozen_engine import FrozenEngine,RecordedRM,LOCAL
 from reward_model import TPORewardModel
 from tpo_utils import run_test_time_training_tpo,run_test_time_training_bon
 import textgrad
 assert Path(textgrad.__file__).is_relative_to(SOURCE)
 config=read(ROOT/'run_config.json');engine=FrozenEngine(root,bind,int(os.environ.get('FROZEN_POLICY_PORT',config['policy_port'])))
 print('Loading official FsfairX reward model',flush=True)
 start=time.monotonic()
 revision=config['protocol']['revisions']['reward_model']
 cache=Path(os.environ.get('HF_HUB_CACHE',Path.home()/'.cache/huggingface/hub'))
 model_path=cache/'models--sfairXC--FsfairX-LLaMA3-RM-v0.1/snapshots'/revision
 assert model_path.exists()
 rm=RecordedRM(TPORewardModel(str(model_path)),root,bind)
 status={'binding':bind,'state':'running','rm_load_seconds':time.monotonic()-start,'phases':old['phases'] if old else {}}
 queries=read(ROOT/'data/alpaca100.json');ids=read(ROOT/'data/slice_ids.json')
 dataset=list(zip(ids,queries))[:3] if a.preflight else list(zip(ids,queries))
 save(root/'generation_status.json',status)
 def run_one(mode,bid,q):
  LOCAL.current=SimpleNamespace(bid=bid,mode=mode,request_index=0,rm_index=0)
  path=root/'checkpoints'/f'{mode}-{bid}.json'
  if path.exists():
   checkpoint=read(path);assert checkpoint['binding']==bind;return checkpoint['result']
  fn=run_test_time_training_tpo if mode=='run100' else run_test_time_training_bon
  started=time.monotonic()
  result=fn(q,engine,rm,gen_params={'n':5 if mode=='run100' else 15,'temperature':0.7,'top_p':0.95,'seed':7,'max_tokens':2048},tpo_mode='tpo',max_iters=2)
  assert LOCAL.current.request_index==(7 if mode=='run100' else 1)
  save(path,{'binding':bind,'benchmark_id':bid,'instruction':q,'result':result,'elapsed_seconds':time.monotonic()-started})
  return result
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   for mode in ['run100','bon15']:
    start=time.monotonic();status['phases'][mode]={'state':'running','target':len(dataset),'completed':0};save(root/'generation_status.json',status)
    futures={pool.submit(run_one,mode,bid,q):(bid,q) for bid,q in dataset}
    results={};errors=[]
    for f in concurrent.futures.as_completed(futures):
     bid,q=futures[f]
     try:results[bid]=f.result()
     except Exception as exc:
      errors.append({'benchmark_id':bid,'error_type':type(exc).__name__,'error':str(exc)[:300]});save(root/'errors.json',errors)
      for other in futures:other.cancel()
     status['phases'][mode].update(completed=len(results),errors=len(errors),elapsed_seconds=time.monotonic()-start)
     save(root/'generation_status.json',status)
     print(f'{mode}: {len(results)}/{len(dataset)}, errors {len(errors)}',flush=True)
    if errors:raise RuntimeError('Generation incomplete; see errors.json')
    save(root/mode/'results.json',[results[bid] for bid,_ in dataset]);status['phases'][mode]['state']='complete'
    save(root/'generation_status.json',status)
  status['state']='complete';save(root/'generation_status.json',status)
 except BaseException:
  status['state']='incomplete';save(root/'generation_status.json',status);raise
 print('GENERATION_PASS',flush=True)
if __name__=='__main__':main()

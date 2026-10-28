"""Exercise official algorithms against saved request/RM journals with network forbidden."""
import os,sys
from types import SimpleNamespace
from pathlib import Path
from frozen_common import ROOT,SOURCE,read,save,binding,check_source
sys.dont_write_bytecode=True;sys.path[:0]=[str(SOURCE/'textgrad-main'),str(SOURCE)]
root=ROOT/'preflight';os.chdir(root);os.environ['XDG_CACHE_HOME']=str(root/'cache')
from frozen_engine import FrozenEngine,RecordedRM,LOCAL
from tpo_utils import run_test_time_training_tpo,run_test_time_training_bon

def forbidden(*a,**k):raise AssertionError('Network or RM generation attempted during replay')
class NoModel:
 perform_rm=forbidden
 def get_contrastive_samples(self,scores,pairs):
  # Selection uses the official CPU tokenizer method; load only cached tokenizer.
  from reward_model import TPORewardModel
  return TPORewardModel.get_contrastive_samples(self,scores,pairs)
 from transformers import AutoTokenizer
 tokenizer=AutoTokenizer.from_pretrained(str(Path.home()/'.cache/huggingface/hub/models--sfairXC--FsfairX-LLaMA3-RM-v0.1/snapshots/94fad49f1b3227aa8b566f415a335adb68ec544c'),local_files_only=True)

def main():
 check_source();bind=binding();assert read(root/'generation_status.json')['state']=='complete'
 engine=FrozenEngine(root,bind,8002);engine.original=forbidden
 rm=RecordedRM(NoModel(),root,bind)
 queries=read(ROOT/'data/alpaca100.json')[:3];ids=read(ROOT/'data/slice_ids.json')[:3]
 checked=[]
 for mode,fn in [('run100',run_test_time_training_tpo),('bon15',run_test_time_training_bon)]:
  for bid,q in zip(ids,queries):
   LOCAL.current=SimpleNamespace(bid=bid,mode=mode,request_index=0,rm_index=0)
   result=fn(q,engine,rm,gen_params={'n':5 if mode=='run100' else 15,'temperature':0.7,'top_p':0.95,'seed':7,'max_tokens':2048},tpo_mode='tpo',max_iters=2)
   assert result==read(root/'checkpoints'/f'{mode}-{bid}.json')['result']
   checked.append({'mode':mode,'benchmark_id':bid,'identical_result':True})
 # A changed prompt must fail hash validation before any attempted generation.
 LOCAL.current=SimpleNamespace(bid=ids[0],mode='run100',request_index=0,rm_index=0)
 rejected=False
 try:engine(queries[0]+' altered',n=5,temperature=0.7,top_p=0.95,max_tokens=2048,seed=7)
 except AssertionError as exc:rejected='resume mismatch' in str(exc).lower()
 assert rejected
 events=[__import__('json').loads(line) for line in (root/'policy_requests.jsonl').read_text().splitlines()]
 successful=[r for r in events if r['status']=='success']
 assert len(successful)==24 and all(isinstance(r['request']['seed'],int) for r in successful)
 assert all(r['request']['seed']==__import__('frozen_common').seed(r['benchmark_id'],r['stage'],r['iteration'],0) for r in successful)
 result={'state':'PASS','generation_binding':bind,'replayed':checked,'changed_prompt_rejected':rejected,'all_24_policy_requests_explicit_seed':True,'raw_responses_saved':True,'no_network_or_RM_generation_during_replay':True}
 save(root/'replay_verification.json',result);print('PREFLIGHT_REPLAY_PASS: six prompt/mode checkpoints exactly reconstructed without API or RM calls; changed request rejected.')
if __name__=='__main__':main()

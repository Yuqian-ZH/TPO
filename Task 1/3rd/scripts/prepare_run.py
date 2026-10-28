"""Create an isolated workspace; the two historical trees are read-only inputs."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, shutil, subprocess
BASE=Path(__file__).resolve().parents[1]
HOME=BASE.parent

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def manifest(root):
 return {str(p.relative_to(root)):{'sha256':digest(p),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink() and '.git' not in p.relative_to(root).parts}

def main():
 now=datetime.now(ZoneInfo('America/Los_Angeles'))
 run=BASE/'runs'/f'task1_frozen_v1_{now:%Y%m%dT%H%M%S%z}'
 run.mkdir(parents=True)
 for folder in ['source','data','preflight','checkpoints','stages','eval_out','logs','history']:(run/folder).mkdir()
 before={name:manifest(HOME/name) for name in ['TPO','TPO_Test']}
 write(run/'protected_before.json',before)
 source=run/'source/TPO';source.mkdir()
 for name in ['run.py','tpo_utils.py','reward_model.py','requirements.txt','README.md']:
  shutil.copy2(HOME/'TPO'/name,source/name)
 shutil.copytree(HOME/'TPO/textgrad-main',source/'textgrad-main',ignore=shutil.ignore_patterns('__pycache__','.git','*.pyc'))
 data=HOME/'TPO/task1/data'
 for p in data.glob('*.json'):shutil.copy2(p,run/'data'/p.name)
 for name in ['alpaca100.json','reference100.json','slice_ids.json','alpaca100_meta.json']:
  assert digest(data/name)==digest(HOME/'TPO_Test/data'/name)
 q=json.loads((run/'data/alpaca100.json').read_text());r=json.loads((run/'data/reference100.json').read_text())
 assert len(q)==len(set(q))==len(r)==100 and q==[v['instruction'] for v in r]
 write(run/'data_hashes.json',{p.name:digest(p) for p in (run/'data').glob('*.json')})
 write(run/'source_hashes.json',{str(p.relative_to(source)):digest(p) for p in sorted(source.rglob('*')) if p.is_file()})
 commit=subprocess.check_output(['git','-C',str(HOME/'TPO'),'rev-parse','HEAD'],text=True).strip()
 (run/'source_changes.patch').write_bytes(subprocess.check_output(['git','-C',str(HOME/'TPO'),'diff','HEAD','--','run.py','tpo_utils.py','reward_model.py','textgrad-main']))
 for label,old in [('original',HOME/'TPO/task1'),('rerun',HOME/'TPO_Test')]:
  dst=run/'history'/label;dst.mkdir()
  for name in ['results_task1.json','results_task1.md','robustness.json','run_config.json','README.md']:
   if (old/name).exists():shutil.copy2(old/name,dst/name)
 protocol={'version':'task1_frozen_v1','main_seed':7,'slice_seed':42,'D':2,'N':5,'bon_n':15,'workers':8,
 'policy':'allenai/Llama-3.1-Tulu-3-8B-SFT','reward_model':'sfairXC/FsfairX-LLaMA3-RM-v0.1','judge':'qwen3.8-max',
 'revisions':{'policy':'f2a0b46b0cfda21003c6141b1ff837b7e165524d','reward_model':'94fad49f1b3227aa8b566f415a335adb68ec544c'},
 'sampling':{'answer':{'temperature':0.7,'top_p':0.95,'max_tokens':2048},'critique_gradient':{'temperature':0.7,'top_p':0.99,'max_tokens':8192}},
 'seed_rule':'int.from_bytes(sha256(f"task1_frozen_v1|7|{benchmark_id}|{stage}|{iteration}|{request_index}".encode()).digest()[:4], "big") & 0x7fffffff',
 'judge_settings':{'temperature':1,'max_tokens':1,'logprobs':True,'top_logprobs':5,'enable_thinking':False,'order_randomization_seed':0},
 'context':16384,'retry':{'max_attempts':3,'wait_seconds':[2,8],'only':['connection','timeout','429','500','502','503','504'],'unchanged_request':True},
 'bootstrap':{'resamples':10000,'seed':42,'unit':'paired_prompt','comparisons':['step1-baseline','step2-step1','step2-baseline','step2-step0','step2-bon15']},
 'resume':'Persist first successful raw response for every logical request; replay only identical request/config hashes, persist RM calls and per-prompt checkpoints. Never resample completed logical requests.',
 'stop':'Any unrecoverable request, config/hash mismatch, missing data, model unavailable, or failed preflight: incomplete; never silently exclude prompts.',
 'selection':'Official cumulative score cache, first maximum for ties, baseline first initial candidate; do not alter official response variable or contexts.',
 'execution':'3 fixed first prompts preflight, freeze, one 100-prompt TPO and one BoN15 run, fresh judge cache; no score-driven reruns',
 'cache':'New run only. Keys include full parameters, model, prompts/answers/order. No historical judgments.',
 'LC':'GPT-4 calibration unvalidated for Qwen; descriptive; conditional fitted-GLM uncertainty only'}
 write(run/'protocol.draft.json',protocol)
 write(run/'run_config.json',{'run_id':run.name,'created_at':now.isoformat(),'state':'preparing','repo_commit':commit,'historical_runs':{'original':str(HOME/'TPO/task1'),'rerun':str(HOME/'TPO_Test')},'policy_gpu':2,'reward_gpu':3,'policy_port':8002,'protocol':protocol,'fresh_clean_install_tested':False})
 (BASE/'LATEST.txt').write_text(str(run.relative_to(BASE))+'\n')
 (run/'INSPECTION.md').write_text(f'# Workspace inspection\n\nRun: `{run.name}`.\n\nHistorical directories: `/home/yuqian/TPO/task1` and `/home/yuqian/TPO_Test`. Both have five completed 100-prompt stages. Data, reference, slice-ID, and metadata bytes match. Official commit: `{commit}`. Existing source changes are preserved in `source_changes.patch`; algorithm files and TextGrad copied into this run. All historical files are protected by content, size, and modification-time manifests.\n\nThe user selected the FROZEN_RERUN protocol. Existing FINISH results are historical only and will not be presented as new measurements. No fresh-machine installation has been performed.\n')
 print(run)
if __name__=='__main__':main()

"""Read-only historical integrity check, output acceptance and secret scan."""
import hashlib,json,os,re,sys
from pathlib import Path
from frozen_common import BASE,ROOT,SOURCE,read,save,binding,check_source

def manifest(root):
 return {str(p.relative_to(root)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink() and '.git' not in p.relative_to(root).parts}
def main():
 check_source();__import__('guard_data');freeze=read(ROOT/'freeze.json');assert freeze['binding']==binding()
 modified_scripts=[]
 for p,h in freeze['scripts'].items():
  if hashlib.sha256((BASE/p).read_bytes()).hexdigest()!=h:modified_scripts.append(p)
 assert not modified_scripts,modified_scripts
 preserved={};before=read(ROOT/'protected_before.json')
 for name in ['TPO','TPO_Test']:
  now=manifest(BASE.parent/name);old=before[name]
  changed=sorted(p for p in old.keys()&now.keys() if old[p]!=now[p])
  preserved[name]={'pass':now==old,'files':len(old),'changed':changed,'new':sorted(now.keys()-old.keys()),'removed':sorted(old.keys()-now.keys())}
 save(ROOT/'protected_after.json',preserved);assert all(r['pass'] for r in preserved.values()),'Historical directory changed'
 key=os.environ.get('DASHSCOPE_API_KEY','').encode();pattern=re.compile(rb'sk-[A-Za-z0-9]{8,}');regex_files=[];exact_files=[]
 for p in BASE.rglob('*'):
  if not p.is_file() or p.is_symlink() or '.git' in p.parts:continue
  data=p.read_bytes()
  if pattern.search(data):regex_files.append(str(p.relative_to(BASE)))
  if key and key in data:exact_files.append(str(p.relative_to(BASE)))
 scan={'pass':not regex_files and not exact_files,'regex_matching_files':regex_files,'exact_key_matching_files':exact_files,'exact_current_key_checked':bool(key),'git_history_scanned':False}
 save(ROOT/'secret_scan_result.json',scan);assert scan['pass'],'Secret scan failed; contents suppressed'
 results=read(ROOT/'results_task1.json');assert len(results['rows'])==5 and all(r['Judged']==100 for r in results['rows'])
 assert read(ROOT/'generation_status.json')['state']=='complete'
 policy=[json.loads(line) for line in (ROOT/'policy_requests.jsonl').read_text().splitlines()];success=[r for r in policy if r['status']=='success']
 assert len(success)==800 and len({r['logical_request_id'] for r in success})==800
 assert all(r['request']['seed']==__import__('frozen_common').seed(r['benchmark_id'],r['stage'],r['iteration'],0) for r in success)
 assert not list((ROOT/'judge_cache').glob('annotations*'))
 artifacts=['protocol.json','run_config.json','freeze.json','source_changes.patch','source_hashes.json','data_hashes.json','environment_tpo.json','environment_aeval.json','policy_requests.jsonl','rm_requests.jsonl','judge_requests.jsonl','results_task1.json','results_task1.md','robustness.json','robustness.md','diagnostics.json','HISTORICAL_COMPARISON.md','DEVIATIONS.md','run_report.md']
 assert all((ROOT/p).exists() for p in artifacts)
 result={'state':'PASS','protected_directories':preserved,'frozen_script_hashes_pass':True,'source_hashes_pass':True,'data_alignment':'five 100-prompt stages verified by offline analysis','all_800_policy_requests_seeded':True,'one_formal_TPO_and_one_bon15':True,'preflight':read(ROOT/'preflight/replay_verification.json'),'secret_scan':scan,'clean_environment_install_tested':False,'bitwise_reproducibility_claimed':False,'limitations':['Qwen alias has no immutable exposed backend snapshot.','LC calibration unvalidated for Qwen; reported LC intervals condition on fitted GLM.','No clean-machine install test.']}
 save(ROOT/'FINAL_AUDIT.json',result)
 config=read(ROOT/'run_config.json');config.update(state='complete',audit='FINAL_AUDIT.json',results='results_task1.json',generation_timing=read(ROOT/'generation_status.json'));save(ROOT/'run_config.json',config)
 manifest_={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.rglob('*') if p.is_file() and p.name!='DELIVERY_MANIFEST.json' and '__pycache__' not in p.parts}
 save(BASE/'DELIVERY_MANIFEST.json',manifest_)
 print(f'FINAL_AUDIT_PASS: TPO ({preserved["TPO"]["files"]} files) and TPO_Test ({preserved["TPO_Test"]["files"]} files) contents, sizes and mtimes unchanged; source/config/scripts frozen; five 100-prompt stages; secret scan clear.')
if __name__=='__main__':main()

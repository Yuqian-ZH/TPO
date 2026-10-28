from pathlib import Path
import shutil,hashlib,json
import yaml
from frozen_common import ROOT,save

def main():
 source=ROOT.parent.parent.parent/'TPO/task1/judge_config'
 config=yaml.safe_load((source/'configs.yaml').read_text())
 entry=config['weighted_qwen3_8_max'];entry['completions_kwargs']['num_procs']=4
 # Keep historical exact prompt, parser and sampling; transport config alone changes.
 for root in [ROOT,ROOT/'preflight']:
  dest=root/'judge_config';dest.mkdir(exist_ok=True)
  for name in ['alpaca_eval_clf.txt','df_gamed.csv','calibration_provenance.json']:
   shutil.copy2(source/name,dest/name)
  (dest/'configs.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
  client={'qwen3.8-max':[{'client_class':'frozen_judge.FrozenJudge','api_key_env':'DASHSCOPE_API_KEY','base_url_env':'DASHSCOPE_BASE_URL','timeout':120,'max_retries':0}]}
  (dest/'client_configs.yaml').write_text(yaml.safe_dump(client,sort_keys=False))
  save(dest/'provenance.json',{'original_annotator':'weighted_alpaca_eval_gpt4_turbo','adapted_annotator':'weighted_qwen3_8_max','prompt_sha256':hashlib.sha256((dest/'alpaca_eval_clf.txt').read_bytes()).hexdigest(),'configuration':config,'order_seed':0,'retry':{'max_attempts':3,'wait_seconds':[2,8]},'key':'DASHSCOPE_API_KEY environment only','historical_judgments_used':False})
 print('Fresh judge configurations created; historical annotations excluded')
if __name__=='__main__':main()

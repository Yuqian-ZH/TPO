import argparse,collections,statistics
from frozen_common import ROOT,read,save

def export(root,n):
 reference=read(ROOT/'data/reference100.json')[:n];queries=[r['instruction'] for r in reference]
 stages={s:[] for s in ['baseline','step0','step1','step2','bon15']};rewards={s:[] for s in stages};candidate_rewards=collections.defaultdict(list)
 bon_scores={};counts={};per_prompt_means=collections.defaultdict(list)
 raw={}
 for mode in ['run100','bon15']:
  rows=read(root/mode/'results.json');assert len(rows)==n
  byq={}
  for row in rows:
   for key,score in row.items():
    iteration,q,answer=key.split('<SEP>',2);byq.setdefault(q,[]).append((int(iteration[5:]),answer,score))
  assert set(byq)==set(queries);raw[mode]=byq
 for ref in reference:
  q=ref['instruction'];items=raw['run100'][q];init=[r for r in items if r[0]==-1]
  chosen={'baseline':init[0],'step0':max(init,key=lambda r:r[2])}
  for stage,last in [('step1',0),('step2',1)]:chosen[stage]=max((r for r in items if r[0]<=last),key=lambda r:r[2])
  chosen['bon15']=max(raw['bon15'][q],key=lambda r:r[2]);bon_scores[q]=chosen['bon15'][2];counts[q]=len(raw['bon15'][q])
  for s,(_,ans,score) in chosen.items():
   assert ans.strip(),f'Empty selected answer: {s}'
   stages[s].append({'instruction':q,'output':ans,'generator':f'tulu3-8b-sft-{s}','dataset':ref['dataset']});rewards[s].append(score)
  for i,name in [(-1,'init'),(0,'iter1'),(1,'iter2')]:
   scores=[r[2] for r in items if r[0]==i];candidate_rewards[name].extend(scores)
   if scores:per_prompt_means[name].append(statistics.mean(scores))
 for s,rows in stages.items():save(root/'stages'/f'{s}.json',rows)
 save(root/'stages/rm_summary.json',{'n_prompts':n,'rm_of_selected_response':{s:statistics.mean(v) for s,v in rewards.items()},'mean_rm_of_all_samples_per_iter':{i:statistics.mean(v) for i,v in candidate_rewards.items()},'equal_prompt_weight_rm_per_iter':{i:statistics.mean(v) for i,v in per_prompt_means.items()}})
 save(root/'stages/bon15_rm_summary.json',{'n_prompts':n,'requested_candidates_per_prompt':15,'mean_selected_rm_score':statistics.mean(bon_scores.values()),'prompts_with_fewer_than_15_stored_samples':sum(c<15 for c in counts.values()),'selected_rm_by_instruction':bon_scores,'stored_sample_counts_by_instruction':counts})
 save(root/'data/reference100.json',reference)
 print(f'EXPORT_PASS: {n} aligned nonempty outputs in each of five stages')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');a=p.parse_args();export(ROOT/'preflight' if a.preflight else ROOT,3 if a.preflight else 100)

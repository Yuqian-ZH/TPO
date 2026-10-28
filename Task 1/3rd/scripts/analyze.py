"""CPU analysis of saved generations/judgments only; no model or network clients."""
import collections,hashlib,json,math,re,statistics
from pathlib import Path
import numpy as np
from frozen_common import ROOT,read,save
STAGES=['baseline','step0','step1','step2','bon15']
PAIRS=[('step1','baseline'),('step2','step1'),('step2','baseline'),('step2','step0'),('step2','bon15')]
FLAG=re.compile(r'\b(?:chosen response|rejected response|strengths and weaknesses|improved response|as an evaluator)\b',re.I)

def table(rows,columns):
 out=['| '+' | '.join(columns)+' |','|'+'|'.join('---' for c in columns)+'|']
 for row in rows:
  out.append('| '+' | '.join(f'{row[c]:.4f}' if isinstance(row[c],float) else str(row[c]) for c in columns)+' |')
 return '\n'.join(out)
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def paired(values):
 values=np.array(values,dtype=float);assert values.shape==(100,) and np.isfinite(values).all()
 indices=np.random.default_rng(42).integers(0,100,(10000,100));ci=np.quantile(values[indices].mean(1),[.025,.975])
 se=float(values.std(ddof=1)/10)
 return {'n_prompts':100,'mean_difference':float(values.mean()),'paired_se':se,'exceeds_one_paired_se':bool(abs(values.mean())>se),'percent_prompts_improved':float((values>0).mean()*100),'percent_prompts_unchanged':float((values==0).mean()*100),'bootstrap_95_ci':ci.tolist()}
def raw_by_query(path):
 rows=read(path);assert len(rows)==100;out={}
 for row in rows:
  for key,score in row.items():
   iteration,q,answer=key.split('<SEP>',2);out.setdefault(q,[]).append((int(iteration[5:]),answer,score))
 assert len(out)==100;return out

def main():
 refs=read(ROOT/'data/reference100.json');qs=[r['instruction'] for r in refs];ids=read(ROOT/'data/slice_ids.json');idq=dict(zip(qs,ids))
 raw={m:raw_by_query(ROOT/m/'results.json') for m in ['run100','bon15']}
 assert all(set(v)==set(qs) for v in raw.values())
 chosen={s:{} for s in STAGES};stages={};annotations={};scores={};lc={}
 for q in qs:
  init=[r for r in raw['run100'][q] if r[0]==-1]
  chosen['baseline'][q]=init[0];chosen['step0'][q]=max(init,key=lambda r:r[2])
  for s,last in [('step1',0),('step2',1)]:chosen[s][q]=max((r for r in raw['run100'][q] if r[0]<=last),key=lambda r:r[2])
  chosen['bon15'][q]=max(raw['bon15'][q],key=lambda r:r[2])
 rows=[];usage={}
 for s in STAGES:
  stage=read(ROOT/'stages'/f'{s}.json');ann=read(ROOT/'eval_out'/s/'annotations.json')
  assert len(stage)==len(ann)==100
  stages[s]={r['instruction']:r for r in stage};annotations[s]={r['instruction']:r for r in ann}
  assert set(stages[s])==set(annotations[s])==set(qs)
  for q in qs:
   assert stages[s][q]['output'].strip() and stages[s][q]['output']==chosen[s][q][1]
   assert annotations[s][q]['output_2']==stages[s][q]['output']
   assert annotations[s][q]['output_1']==refs[qs.index(q)]['output']
   assert 1<=annotations[s][q]['preference']<=2
  scores[s]=np.array([annotations[s][q]['preference']-1 for q in qs]);lc[s]=np.array([annotations[s][q]['glm_preference'] for q in qs]);assert np.isfinite(lc[s]).all()
  events=lines(ROOT/'eval_out'/s/'usage.jsonl')
  usage[s]={'successful_api_requests':len(events),**{k:sum(e['usage'].get(k) or 0 for e in events) for k in ['prompt_tokens','completion_tokens','total_tokens']}}
  rows.append({'Stage':s,'WR (%)':float(scores[s].mean()*100),'LC (%)':float(lc[s].mean()*100),'WR SE (pp)':float(scores[s].std(ddof=1)*10),'LC conditional SE (pp)':float(lc[s].std(ddof=1)*10),'Selected RM':statistics.mean(chosen[s][q][2] for q in qs),'Avg chars':statistics.mean(len(stages[s][q]['output']) for q in qs),'Judged':100})
  import csv
  with (ROOT/'eval_out'/s/'leaderboard.csv').open() as f:leader=next(csv.DictReader(f))
  assert math.isclose(float(leader['win_rate']),rows[-1]['WR (%)'],abs_tol=1e-7)
  assert math.isclose(float(leader['length_controlled_winrate']),rows[-1]['LC (%)'],abs_tol=1e-7)
 ordered=['baseline','step1','step2']
 monotonic={metric:all(v[a]<=v[b] for a,b in zip(ordered,ordered[1:])) for metric,v in [('WR',{s:float(scores[s].mean()) for s in STAGES}),('LC',{s:float(lc[s].mean()) for s in STAGES})]}
 comparisons={}
 for a,b in PAIRS:
  comparisons[f'{a} - {b}']={'WR_pp':paired((scores[a]-scores[b])*100),'LC_pp_conditional_on_fitted_GLM':paired((lc[a]-lc[b])*100),'RM':paired([chosen[a][q][2]-chosen[b][q][2] for q in qs])}
 results={'rows':rows,'judge_model':'qwen3.8-max','annotator':'weighted_qwen3_8_max','monotonic_baseline_step1_step2':monotonic,'paired_comparisons':comparisons,'judge_usage':usage,'bootstrap':{'resamples':10000,'seed':42,'unit':'paired prompt','LC_uncertainty':'Conditional on fitted GLM; excludes model fitting uncertainty; GPT-4 calibration unvalidated for Qwen.'}}
 save(ROOT/'results_task1.json',results)
 complete=[q for q in qs if all(sum(r[0]==i for r in raw['run100'][q])==5 for i in [-1,0,1])]
 survival=[]
 for subset,queries in [('All prompts',qs),('5 unique candidates in every round',complete)]:
  row={'Subset':subset,'Prompts':len(queries)}
  for i,name in [(-1,'init'),(0,'iter1'),(1,'iter2')]:row[name]=statistics.mean(r[2] for q in queries for r in raw['run100'][q] if r[0]==i) if queries else None
  survival.append(row)
 process=[]
 for i,name in [(-1,'init'),(0,'iter1'),(1,'iter2')]:
  groups=[[r[2] for r in raw['run100'][q] if r[0]==i] for q in qs]
  process.append({'Iteration':name,'Stored unique':sum(map(len,groups)),'Prompts with candidates':sum(bool(g) for g in groups),'Candidate weighted mean RM':statistics.mean(x for g in groups for x in g),'Equal prompt mean RM':statistics.mean(statistics.mean(g) for g in groups if g)})
 policy=[r for r in lines(ROOT/'policy_requests.jsonl') if r['status']=='success'];rm=lines(ROOT/'rm_requests.jsonl');parsing=lines(ROOT/'parsing.jsonl')
 diagnostics=[]
 for kind in ['initial','critique','gradient','refinement','bon15']:
  iterations=[-1] if kind in ['initial','bon15'] else [0,1]
  for i in iterations:
   events=[r for r in policy if r['stage']==kind and r['iteration']==i];choices=[c for r in events for c in r['response']['choices']]
   parsed=[r for r in parsing if r['iteration']==i] if kind=='refinement' else []
   valid=[r['parsed_answer'] for r in parsed if r['parse_status']!='missing_response_tags'] if parsed else [c['message']['content'] for c in choices] if kind in ['initial','bon15'] else []
   phase='bon15' if kind=='bon15' else 'run100'
   stored=sum(sum(r[0]==i for r in raw[phase][q]) for q in qs) if kind in ['initial','refinement','bon15'] else None
   diagnostics.append({'Stage':kind,'Iteration':i,'Requests':len(events),'Requested choices':sum(r['request']['n'] for r in events),'Returned':len(choices),'Parsed':len(valid) if stored is not None else None,'Missing tags':sum(r['parse_status']=='missing_response_tags' for r in parsed) if parsed else 0,'Duplicate merges':len(valid)-stored if stored is not None else None,'Empty':sum(not (v or '').strip() for v in valid) if stored is not None else sum(not (c['message']['content'] or '').strip() for c in choices),'Raw finish=length':sum(c['finish_reason']=='length' for c in choices),'Raw metadata flags':sum(bool(FLAG.search(c['message']['content'] or '')) for c in choices)})
 selected_diagnostics=[]
 for s in STAGES:
  capped=0;matched=0
  for q in qs:
   it,ans,_=chosen[s][q];bid=idq[q];kind='bon15' if s=='bon15' else 'initial' if it==-1 else 'refinement'
   candidates=[r for r in policy if r['benchmark_id']==bid and r['stage']==kind and r['iteration']==it]
   hits=[]
   for event_ in candidates:
    for c in event_['response']['choices']:
     content=c['message']['content']
     if kind=='refinement':
      try:content=content.split('<IMPROVED_VARIABLE>')[1].split('</IMPROVED_VARIABLE>')[0].strip()
      except (IndexError,AttributeError):continue
     if content==ans:hits.append(c)
   assert hits,f'Missing response provenance {s} {bid}'
   matched+=1;capped+=hits[0]['finish_reason']=='length'
  selected_diagnostics.append({'Stage':s,'Selected with response provenance':matched,'Selected raw finish=length':capped,'Selected metadata flags':sum(bool(FLAG.search(stages[s][q]['output'])) for q in qs)})
 unchanged=sum(stages['step0'][q]['output']==stages['step2'][q]['output'] for q in qs)
 robust={'survivorship':survival,'complete_case_ids':[idq[q] for q in complete],'paired_comparisons':comparisons,'step2_identical_to_step0_count':unchanged,'discarded_refinements':[r for r in diagnostics if r['Stage'] in ['initial','refinement']],'bootstrap':results['bootstrap'],'judge_comparison_note':'Differences between saved soft preferences against the same reference; not direct head-to-head stage match win rates.'}
 save(ROOT/'robustness.json',robust)
 timing=read(ROOT/'generation_status.json')
 totals={'policy_requests':len(policy),'policy_tokens':{k:sum((r['response'].get('usage') or {}).get(k) or 0 for r in policy) for k in ['prompt_tokens','completion_tokens','total_tokens']},'policy_request_seconds_sum':sum(r['elapsed_seconds'] for r in policy),'rm_call_seconds_sum_including_queue':sum(r['elapsed_seconds_including_queue'] for r in rm),'generation':timing,'judge_usage':usage}
 diagnostic_result={'process':process,'request_diagnostics':diagnostics,'selected_diagnostics':selected_diagnostics,'timing':totals,'notes':['Raw finish_reason=length is a length cap flag and does not prove semantically incomplete text.','Metadata phrase counts are screening heuristics, not proven failures.','Candidate duplicate merging uses the official within-iteration cache key; identical text in different rounds remains separate.','Generation phase wall time excludes RM loading; policy request sums overlap across workers; RM sums include queue wait.']}
 save(ROOT/'diagnostics.json',diagnostic_result)
 history=[];historical_differences={}
 for label in ['original','rerun']:
  old=read(ROOT/'history'/label/'results_task1.json');oldrows=old['rows']
  for row in oldrows:
   history.append({'Run':label,'Stage':row['Stage'],'WR (%)':row['WR (%)'],'LC (%)':row['LC (%)']})
  historical_differences[label]={}
  for s in ['baseline','step1','step2']:
   anns=read(ROOT/'history'/label/'eval_out'/s/'annotations.json');byq={r['instruction']:r for r in anns};assert set(byq)==set(qs)
   historical_differences[label][s]=paired([(annotations[s][q]['preference']-byq[q]['preference'])*100 for q in qs])
 for row in rows:history.append({'Run':'task1_frozen_v1','Stage':row['Stage'],'WR (%)':row['WR (%)'],'LC (%)':row['LC (%)']})
 save(ROOT/'historical_comparison.json',{'rows':history,'new_minus_historical_WR_pp':historical_differences,'note':'Historical runs have unseeded critique/gradient calls. Differences include regeneration, revised seed/execution rules and fresh judging. These are not interchangeable seeds from one frozen protocol; no causal attribution or best-run selection.'})
 note='The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; they measure relative change across stages of this run only.'
 result_text=['# Frozen Task 1 results','', '> '+note,'',table(rows,['Stage','WR (%)','LC (%)','WR SE (pp)','Selected RM','Avg chars','Judged']),'',f'Unrounded baseline → step1 → step2 monotonicity: WR **{monotonic["WR"]}**, LC **{monotonic["LC"]}**. RM selection alone cannot establish judge improvement.','', 'Qwen-adapted AlpacaEval uses the historical weighted GPT-4-Turbo prompt and soft logprob parser; temperature 1, max_tokens 1, top_logprobs 5, thinking disabled, output-order seed 0. LC uses GPT-4 calibration unvalidated for Qwen and is descriptive. The judge alias does not expose a dated immutable backend snapshot.','']
 paired_rows=[]
 for name,c in comparisons.items():
  x=c['WR_pp'];lo,hi=x['bootstrap_95_ci']
  paired_rows.append({'Comparison':name,'WR Δ (pp)':x['mean_difference'],'Paired SE':x['paired_se'],'|Δ| > SE':x['exceeds_one_paired_se'],'95% paired CI':f'[{lo:.4f}, {hi:.4f}]'})
 result_text +=[table(paired_rows,['Comparison','WR Δ (pp)','Paired SE','|Δ| > SE','95% paired CI']),'','Intervals use 10,000 paired prompt resamples, seed 42, percentile limits. Exceeding one SE is not a 95% significance test. LC intervals in JSON condition on fitted GLMs and omit fitting uncertainty. No score-driven additional run was performed.','']
 (ROOT/'results_task1.md').write_text('\n'.join(result_text))
 robustness_rows=[]
 for name in ['step2 - step0','step2 - bon15']:
  for metric in ['RM','WR_pp']:
   x=comparisons[name][metric];lo,hi=x['bootstrap_95_ci']
   robustness_rows.append({'Metric':metric,'Comparison':name,'Mean Δ':x['mean_difference'],'Improved prompts (%)':x['percent_prompts_improved'],'95% paired CI':f'[{lo:.4f}, {hi:.4f}]'})
 robust_text=['# Robustness','',table(survival,['Subset','Prompts','init','iter1','iter2']),'',table(robustness_rows,['Metric','Comparison','Mean Δ','Improved prompts (%)','95% paired CI']),'',f'Step2 answer identical to step0: {unchanged}/100.','',robust['judge_comparison_note'],'','Missing-tag drops are counted directly from raw optimizer responses using the official tag split rule. Duplicate merges equal valid parsed candidates minus new within-iteration unique cache entries; empty parsed text is reported separately and is not resampled.','',table(robust['discarded_refinements'],['Stage','Iteration','Requested choices','Returned','Parsed','Missing tags','Duplicate merges','Empty']),'']
 (ROOT/'robustness.md').write_text('\n'.join(robust_text))
 (ROOT/'diagnostics.md').write_text('# Process diagnostics\n\n'+table(process,['Iteration','Stored unique','Prompts with candidates','Candidate weighted mean RM','Equal prompt mean RM'])+'\n\n'+table(diagnostics,['Stage','Iteration','Requests','Returned','Parsed','Missing tags','Duplicate merges','Empty','Raw finish=length','Raw metadata flags'])+'\n\n'+table(selected_diagnostics,['Stage','Selected with response provenance','Selected raw finish=length','Selected metadata flags'])+'\n\n'+'\n\n'.join(diagnostic_result['notes'])+'\n')
 (ROOT/'HISTORICAL_COMPARISON.md').write_text('# Historical comparison\n\n'+table(history,['Run','Stage','WR (%)','LC (%)'])+'\n\n'+read(ROOT/'historical_comparison.json')['note']+'\n\nPer-prompt paired WR differences and intervals for each new stage versus each history are saved in `historical_comparison.json`.\n')
 paper=(ROOT/'paper_comparison.md').read_text()
 (ROOT/'run_report.md').write_text('\n'.join(result_text)+'\n'+'\n'.join(robust_text[2:])+'\n\n# Process\n\n'+(ROOT/'diagnostics.md').read_text()+'\n\n'+paper+'\n\n# Reproducibility limits\n\nModel/software versions, revisions, source/data hashes, retries and sampling are saved. Clean-machine installation has not been tested. Explicit request seeds improve control but do not promise bitwise reproducibility across GPU kernels, batching or machines. Qwen alias backend versions cannot be pinned. See `DEVIATIONS.md`, `freeze.json`, `run_config.json`, and `FINAL_AUDIT.json`.\n')
 print(table(rows,['Stage','WR (%)','LC (%)','WR SE (pp)','Selected RM','Avg chars','Judged']))
 print('OFFLINE_ANALYSIS_PASS: five aligned 100-prompt stages, selection provenance and saved metrics verified.')
if __name__=='__main__':main()

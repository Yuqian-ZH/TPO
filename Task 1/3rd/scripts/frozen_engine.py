"""Use the official engine, optimizer, prompts and RM with journaled transport only."""
import contextlib, json, threading, time
from types import SimpleNamespace
from frozen_common import ROOT, SOURCE, read, save, sha, seed, event, retryable
import textgrad as tg
from textgrad.engine.openai import VllmServer
from openai import OpenAI
LOCAL=threading.local()

def context():return LOCAL.current
class FrozenEngine(VllmServer):
 def __init__(self,root,bind,port):
  # Official constructor, own unused TextGrad disk cache isolated in this run by XDG_CACHE_HOME.
  super().__init__('server-allenai/Llama-3.1-Tulu-3-8B-SFT',base_url=f'http://127.0.0.1:{port}/v1',api_key='token-abc123',max_tokens=8192)
  self.root=root;self.bind=bind
  self.client=OpenAI(base_url=f'http://127.0.0.1:{port}/v1',api_key='token-abc123',max_retries=0,timeout=180)
  self.original=self.client.chat.completions.create
  self.client.chat.completions.create=self.recorded
 def generate(self,content,system_prompt=None,**kwargs):
  # Bypass the official five-attempt blanket decorator; retry only transport here.
  return VllmServer.generate.__wrapped__(self,content,system_prompt=system_prompt,**kwargs)
 def recorded(self,**request):
  c=context();i=c.request_index;c.request_index+=1
  if c.mode=='bon15':kind,iteration='bon15',-1
  elif i==0:kind,iteration='initial',-1
  else:
   iteration=(i-1)//3
   kind=['critique','gradient','refinement'][(i-1)%3]
  expected_n=15 if kind=='bon15' else 5 if kind in ['initial','refinement'] else 1
  assert request.get('n',1)==expected_n,(i,kind,request.get('n'))
  assert iteration<2
  request['seed']=seed(c.bid,kind,iteration,0)
  assert request['temperature']==0.7 and request['top_p']==(0.95 if expected_n>1 else 0.99)
  assert request['max_tokens']==(2048 if expected_n>1 else 8192)
  logical=f'{c.mode}-{c.bid}-{kind}-{iteration}-0'
  h=sha(request);path=self.root/'request_cache'/f'{logical}.json'
  meta={'run_id':ROOT.name,'benchmark_id':c.bid,'phase':c.mode,'stage':kind,'iteration':iteration,'logical_request_id':logical,'binding':self.bind,'request_sha256':h,'request':request}
  if path.exists():
   cached=read(path);assert cached['binding']==self.bind and cached['request_sha256']==h,'Request resume mismatch'
   event(self.root/'policy_replays.jsonl',{**meta,'reused':True})
   from openai.types.chat import ChatCompletion
   return ChatCompletion.model_validate(cached['response'])
  attempts=self.root/'attempts'/f'{logical}.json'
  history=read(attempts) if attempts.exists() else []
  for attempt in range(len(history)+1,4):
   if attempt>1:time.sleep([2,8][attempt-2])
   start=time.monotonic()
   try:
    response=self.original(**request)
   except Exception as exc:
    row={**meta,'attempt':attempt,'status':'error','error_type':type(exc).__name__,'http_status':getattr(exc,'status_code',None),'retryable':retryable(exc),'elapsed_seconds':time.monotonic()-start}
    history.append(row);save(attempts,history);event(self.root/'policy_requests.jsonl',row)
    if not retryable(exc) or attempt==3:raise RuntimeError(f'Policy request failed: {logical}, {type(exc).__name__}') from None
    continue
   row={**meta,'attempt':attempt,'status':'success','elapsed_seconds':time.monotonic()-start,'response':response.model_dump(mode='json')}
   assert len(response.choices)==expected_n
   save(path,row);history.append({'attempt':attempt,'status':'success'});save(attempts,history);event(self.root/'policy_requests.jsonl',row)
   if kind=='refinement':
    tags=['<IMPROVED_VARIABLE>','</IMPROVED_VARIABLE>']
    for choice in response.choices:
     content=choice.message.content or ''
     try:
      answer=content.split(tags[0])[1].split(tags[1])[0].strip();status='success' if answer else 'empty_parsed_answer'
     except IndexError:answer=None;status='missing_response_tags'
     event(self.root/'parsing.jsonl',{'benchmark_id':c.bid,'iteration':iteration,'candidate_index':choice.index,'logical_request_id':logical,'parse_status':status,'parsed_answer':answer,'finish_reason':choice.finish_reason})
   return response
  raise RuntimeError(f'Attempt budget already exhausted: {logical}')

class RecordedRM:
 def __init__(self,model,root,bind):self.model=model;self.root=root;self.bind=bind;self.lock=threading.Lock()
 def perform_rm(self,pairs):
  c=context();i=c.rm_index;c.rm_index+=1
  path=self.root/'rm_cache'/f'{c.mode}-{c.bid}-{i}.json';h=sha(pairs)
  if path.exists():
   row=read(path);assert row['binding']==self.bind and row['input_sha256']==h;return row['scores']
  start=time.monotonic()
  with self.lock:scores=self.model.perform_rm(pairs)
  row={'run_id':ROOT.name,'benchmark_id':c.bid,'phase':c.mode,'iteration':i-1,'pairs':pairs,'scores':scores,'binding':self.bind,'input_sha256':h,'elapsed_seconds_including_queue':time.monotonic()-start}
  save(path,row);event(self.root/'rm_requests.jsonl',row);return scores
 def get_contrastive_samples(self,scores,pairs):
  start=time.monotonic();result=self.model.get_contrastive_samples(scores,pairs)
  event(self.root/'selection.jsonl',{'benchmark_id':context().bid,'phase':context().mode,'rm_call':context().rm_index-1,'scores':scores,'pairs':pairs,'chosen_rejected':result,'elapsed_seconds':time.monotonic()-start})
  return result

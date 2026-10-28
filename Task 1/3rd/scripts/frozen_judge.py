"""Environment credentials, new full-request cache, exact fixed retries, raw logging."""
from datetime import datetime
from zoneinfo import ZoneInfo
import os,threading,time
from pathlib import Path
from openai import OpenAI
from frozen_common import ROOT,read,save,sha,event,retryable
_LOCK=threading.Lock();_KEY_LOCKS={}
class FrozenJudge(OpenAI):
 def __init__(self,api_key_env='DASHSCOPE_API_KEY',base_url_env='DASHSCOPE_BASE_URL',**kwargs):
  kwargs['max_retries']=0
  super().__init__(api_key=os.environ[api_key_env],base_url=os.environ[base_url_env],**kwargs)
  original=self.chat.completions.create
  def create(**request):
   assert request['model']==os.environ['JUDGE_MODEL']=='qwen3.8-max'
   assert request['temperature']==1 and request['max_tokens']==1
   assert request['logprobs'] is True and request['top_logprobs']==5
   assert request['extra_body']['enable_thinking'] is False
   root=Path(os.environ.get('FROZEN_JUDGE_ROOT',ROOT))
   config=read(root/'judge_config/provenance.json');h=sha({'request':request,'configuration':config,'endpoint':os.environ[base_url_env]})
   path=root/'judge_cache'/f'{h}.json'
   with _LOCK:lock=_KEY_LOCKS.setdefault(h,threading.Lock())
   with lock:
    if path.exists():
     cached=read(path);assert cached['cache_key']==h
     from openai.types.chat import ChatCompletion
     event(root/'judge_replays.jsonl',{'stage':os.environ.get('FROZEN_JUDGE_STAGE'),'cache_key':h})
     return ChatCompletion.model_validate(cached['response'])
    if os.environ.get('FROZEN_OFFLINE_ANALYSIS')=='1':raise RuntimeError('Offline recomputation attempted a judge request')
    attempts=root/'judge_attempts'/f'{h}.json';history=read(attempts) if attempts.exists() else []
    for attempt in range(len(history)+1,4):
     if attempt>1:time.sleep([2,8][attempt-2])
     start=time.monotonic();meta={'run_id':ROOT.name,'stage':os.environ.get('FROZEN_JUDGE_STAGE'),'logical_request_id':h,'attempt':attempt,'request':request,'cache_key':h,'date':datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()}
     try:response=original(**request)
     except Exception as exc:
      row={**meta,'status':'error','error_type':type(exc).__name__,'http_status':getattr(exc,'status_code',None),'retryable':retryable(exc),'elapsed_seconds':time.monotonic()-start}
      history.append(row);save(attempts,history);event(root/'judge_requests.jsonl',row)
      if not retryable(exc) or attempt==3:raise RuntimeError(f'Judge failed: {type(exc).__name__}; HTTP {getattr(exc,"status_code",None)}') from None
      continue
     usage=response.usage.model_dump() if response.usage else {}
     reasoning=any(bool(getattr(c.message,'reasoning_content',None)) for c in response.choices)
     reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
     row={**meta,'status':'success','response':response.model_dump(mode='json'),'elapsed_seconds':time.monotonic()-start}
     save(path,row);event(root/'judge_requests.jsonl',row);history.append({'attempt':attempt,'status':'success'});save(attempts,history)
     assert not reasoning and reasoning_tokens in (0,None),'Unexpected judge reasoning'
     for c in response.choices:assert c.logprobs and c.logprobs.content and c.logprobs.content[0].top_logprobs
     usage_path=os.environ.get('JUDGE_USAGE_PATH')
     if usage_path:event(Path(usage_path),{'model':response.model,'usage':usage,'reasoning_content_present':reasoning,'reasoning_tokens':reasoning_tokens,'enable_thinking':False,'temperature':1,'max_tokens':1,'request_sha256':h})
     return response
    raise RuntimeError('Judge attempt budget exhausted')
  self.chat.completions.create=create

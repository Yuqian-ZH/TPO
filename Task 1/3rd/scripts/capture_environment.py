from importlib.metadata import version,distributions
import json,platform,subprocess,sys,os
from pathlib import Path
ROOT=Path(sys.argv[1]);label=sys.argv[2]
record={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{d.metadata['Name']:d.version for d in distributions() if d.metadata.get('Name')}}
if label=='tpo':
 import torch
 record.update(cuda_available=torch.cuda.is_available(),cuda_runtime=torch.version.cuda,cudnn=torch.backends.cudnn.version())
record['huggingface_models']={}
for name in ['allenai--Llama-3.1-Tulu-3-8B-SFT','sfairXC--FsfairX-LLaMA3-RM-v0.1']:
 root=Path.home()/'.cache/huggingface/hub'/f'models--{name}'
 record['huggingface_models'][name]={'snapshots':[p.name for p in (root/'snapshots').glob('*')]}
(ROOT/f'environment_{label}.json').write_text(json.dumps(record,indent=2)+'\n')
print(f'{label} environment captured')

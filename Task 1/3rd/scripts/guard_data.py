from frozen_common import ROOT,read,check_source
import hashlib
check_source()
for name,expected in read(ROOT/'data_hashes.json').items():assert hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()==expected,name
print('Source and fixed data byte hashes match')

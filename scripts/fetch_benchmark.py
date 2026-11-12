"""Fetch pinned abz5 benchmark through TU/e repository paths without redistributing data.

Requires public GitHub access. Verifies content SHA256 against the audited fixture.
"""
from pathlib import Path
from urllib.request import Request, urlopen
import json, hashlib

OWNER='ai-for-decision-making-tue'
REPO='Job_Shop_Scheduling_Benchmark_Environments_and_Instances'
COMMIT='d088a26582f5cb79c6b4f2ad94f68ac7c50878cb'
EXPECTED_SHA256='f0ce946d1135814e3248b7e722d2a87c8868cb301afdc3509a3885d2270b96c2'
root=Path(__file__).resolve().parents[1]
target=root/'fixtures/abz5'
if target.exists():
    value=hashlib.sha256(target.read_bytes()).hexdigest()
    if value != EXPECTED_SHA256:
        raise RuntimeError('Existing abz5 hash mismatch; refusing to overwrite')
    print('Pinned abz5 already verified at:',target)
    raise SystemExit(0)

def get(url):
    req=Request(url,headers={'User-Agent':'adaptive-scheduling-repro/1.0'})
    with urlopen(req,timeout=30) as response:
        return response.read()

tree=json.loads(get(f'https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{COMMIT}?recursive=1'))
paths=[i['path'] for i in tree.get('tree',[]) if i.get('type')=='blob' and Path(i['path']).stem.lower()=='abz5']
if not paths: raise RuntimeError('abz5 not found in pinned upstream tree; download manually and verify SHA256')
for path in paths:
    url=f'https://raw.githubusercontent.com/{OWNER}/{REPO}/{COMMIT}/{path}'
    data=get(url)
    if hashlib.sha256(data).hexdigest()==EXPECTED_SHA256:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        print('Downloaded verified pinned upstream fixture:',path)
        break
else:
    raise RuntimeError('No upstream abz5 candidate matched audited SHA256; fixture not installed')

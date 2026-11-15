"""Freeze project outputs into checksummed release archives, outside Git history."""
import hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
output=ROOT/'artifacts/publication';output.mkdir(parents=True,exist_ok=True)
archives=[]
plans=[(p.name,[str(p.relative_to(ROOT))]) for p in sorted((ROOT/'artifacts/research').iterdir()) if p.is_dir()]
others=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'artifacts').iterdir()) if p.name not in ('research','publication')]
if (ROOT/'logs/g1_nominal').exists():others.append('logs/g1_nominal')
plans.append(('baseline-live-and-training',others))
for name,sources in plans:
    path=output/(name+'.tar.zst');temporary=path.with_suffix('.zst.partial')
    tar=subprocess.Popen(['tar','-cf','-',*sources],cwd=ROOT,stdout=subprocess.PIPE)
    result=subprocess.run(['zstd','-T4','-3','-q','-f','-o',str(temporary)],stdin=tar.stdout)
    tar.stdout.close();tarcode=tar.wait()
    if result.returncode or tarcode:raise RuntimeError((name,result.returncode,tarcode))
    temporary.replace(path)
    subprocess.run(['zstd','-q','-t',str(path)],check=True)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    entry=dict(file=path.name,bytes=path.stat().st_size,sha256=h.hexdigest(),sources=sources)
    archives.append(entry)
    (output/'dataset-index.json').write_text(json.dumps(dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),archives=archives),indent=2)+'\n')
    print(json.dumps(entry),flush=True)
(output/'SHA256SUMS').write_text(''.join(f'{a["sha256"]}  {a["file"]}\n' for a in archives))
print('EXPORT COMPLETE',len(archives),sum(a['bytes'] for a in archives),flush=True)

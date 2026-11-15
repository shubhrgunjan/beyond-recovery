"""Audit saved research records; correct one legacy execution-mode metadata flag with a trail."""
from datetime import datetime,timezone
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
required=('manifest.json','summary.json','trace.npz','telemetry.jsonl','events.jsonl','figures.png','analysis.json','analysis.md')
results=[];corrections=0
for summary in sorted((ROOT/'artifacts/research').rglob('summary.json')):
    path=summary.parent;issues=[]
    missing=[f for f in required if not (path/f).is_file()]
    issues+=['Missing '+f for f in missing]
    try:
        manifest=json.loads((path/'manifest.json').read_text());s=json.loads(summary.read_text())
        if not manifest.get('video_recorded',False) and manifest.get('live') is True:
            manifest.setdefault('metadata_corrections',[]).append(dict(time=datetime.now(timezone.utc).isoformat(),field='live',original=True,corrected=False,reason='capture_video=False batch execution was already labeled accelerated in execution_mode; legacy boolean was incorrectly constant True. Physics/data unchanged.'))
            manifest['live']=False;(path/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');corrections+=1
        trace=np.load(path/'trace.npz');times=trace['time'];q=trace['qpos']
        if not np.isfinite(q).all():issues.append('Non-finite qpos')
        if len(q)!=len(times):issues.append('Trace count mismatch')
        if (np.diff(times)<=0).any():issues.append('Non-increasing trace time')
        if abs(float(times[-1])-s['simulated_seconds'])>.0011:issues.append('Summary/trace duration mismatch')
        telemetry=sum(1 for _ in (path/'telemetry.jsonl').open())
        if telemetry!=len(times):issues.append('Telemetry/trace count mismatch')
        if s['result']=='running':issues.append('Run not finalized')
        if manifest.get('video_recorded') and not (path/'video.mp4').exists():issues.append('Promised video missing')
    except Exception as e:issues.append(repr(e))
    results.append(dict(path=str(path),issues=issues))
report=dict(audited=len(results),passed=sum(not r['issues'] for r in results),metadata_corrections=corrections,
            scope='All research summary records including parents/parity qualifications; source measurements and experiment results not changed.',failed=[r for r in results if r['issues']])
(ROOT/'reports/data/record_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
if report['failed']:raise SystemExit(1)

"""Check whether confinement supplied physical support, including contact costs."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
root=sorted((ROOT/'artifacts/research').glob('impact-*'))[-1]
rows=json.loads((root/'results.json').read_text());lookup={tuple(r[k] for k in ('seed','x','width','strength','sign')):r for r in rows}
text='''# Contact support mechanism check

This analysis is specific to the stronger-impulse experiment. The 1.10 m-high fixed barriers can physically intercept the robot. They are rigid fixtures, not compliant human-safe supports; lower fall rates can coexist with undesirable impacts. Contact-force peaks depend on the simulator/contact model and are not injury predictions.

| Checkpoint | Width | Trials | Barrier body-contact trials | Barrier head-contact trials | Median peak non-foot body force (N) | Maximum peak head force (N) |
|---|---|---|---|---|---|---|
'''
for x in (1.7,2.8):
    for w in (None,.9,1.2):
        g=[r for r in rows if r['x']==x and r['width']==w and not r['initial_barrier_overlap']]
        a=[json.loads((Path(r['path'])/'analysis.json').read_text()) for r in g]
        body=sum(any(c['label']=='Recovery-space barrier' and c['region']=='body' for c in v['hazard_contacts']) for v in a)
        head=sum(any(c['label']=='Recovery-space barrier' and c['region']=='head' for c in v['hazard_contacts']) for v in a)
        text+=f'| {x} m | {"Open" if w is None else str(w)+" m"} | {len(g)} | {body} | {head} | {np.median([v["body_contact_peak_n"] for v in a]):.1f} | {max(v["head_contact_peak_n"] for v in a):.1f} |\n'
selected=None
for r in rows:
    if r['width'] is not None or r['x']!=2.8 or r['strength']!=300 or not r['fell']:continue
    other=lookup.get((r['seed'],r['x'],.9,r['strength'],r['sign']))
    if other and not other['fell'] and other['task_success']:selected=(r,other);break
if selected:
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
    for row,color,label in zip(selected,('#bd7754','#528a77'),('Open','0.90 m barriers')):
        records=[json.loads(l) for l in (Path(row['path'])/'telemetry.jsonl').read_text().splitlines()]
        t=np.array([r['time'] for r in records]);mask=t<=15
        for ax,field in zip(axes,('height','tilt','body_contact_n')):
            ax.plot(t[mask],[r.get(field,0) for r,m in zip(records,mask) if m],color=color,label=label)
        a=json.loads((Path(row['path'])/'analysis.json').read_text())
        contact=next((c['time'] for c in a['hazard_contacts'] if c['label']=='Recovery-space barrier' and c['region']=='body'),None)
        if contact is not None:
            for ax in axes:ax.axvline(contact,color=color,ls=':',alpha=.6)
    axes[0].set_ylabel('Pelvis height (m)');axes[1].set_ylabel('Tilt (degrees)');axes[2].set_ylabel('Body-contact peak (N)');axes[2].set_xlabel('Seconds after checkpoint restoration')
    for ax in axes:ax.grid(alpha=.2);ax.axvspan(.2,.38,color='#d89b54',alpha=.2)
    axes[0].legend();fig.suptitle(f'Illustrative support contact: seed {selected[0]["seed"]}, x=2.8 m, {selected[0]["sign"]*300} N × 0.18 s')
    fig.tight_layout();fig.savefig(ROOT/'reports/figures/support_contact_mechanism.png',dpi=180);plt.close(fig)
    (root/'illustrative-support-pair.json').write_text(json.dumps(selected,indent=2))
    text+='\n![Support contact mechanism](figures/support_contact_mechanism.png)\n\nThe orange band is the force pulse; dotted line is the first measured barrier-body contact. This pair was deliberately selected to illustrate an open-space fall and a constrained-space completion at the same parent state and force. It is not an independent replication or representative effect estimate; aggregate results take precedence. The contact check supports a physical-support explanation, without proving an intentional bracing skill.\n'
(ROOT/'reports/SUPPORT_CONTACT_ANALYSIS.md').write_text(text)
report=ROOT/'reports/WAKE_UP_REPORT.md';current=report.read_text().split('\n\n## Contact-support interpretation')[0]
report.write_text(current+'\n\n## Contact-support interpretation\n\n'+text.replace('# Contact support mechanism check','',1))
print('Contact analysis saved',flush=True)

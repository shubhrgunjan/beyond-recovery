"""Refresh and publish the portable cargo report from completed Thor evidence."""
from __future__ import annotations
import argparse,json,shutil,subprocess,time,urllib.parse,urllib.request
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOST='saidevdhal@agx-thor.taila0fc70.ts.net'
SSH=['ssh','-o','UserKnownHostsFile='+str(ROOT/'.cache/thor_known_hosts'),HOST]
REMOTE='/home/saidevdhal/twinbench-research'
PARENTS=['32dc5deadbc841dd','5add07da420147f5','cb9f3d1a7c0649fe']
CLI=Path('/home/shubhr/.npm/_npx/69f9afb961c37556/node_modules/vercel/dist/index.js')
CACHE=ROOT/'.cache/cargo-publication';CACHE.mkdir(parents=True,exist_ok=True)
STAGING=CACHE/'staging'
URL='https://beyond-recovery.vercel.app/cargo-recovery/'


def remote(command):return subprocess.check_output(SSH+[command],text=True)


class References(HTMLParser):
    def __init__(self):super().__init__();self.refs=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        for key in ('href','src'):
            if key in values and not values[key].startswith(('http:','https:','#','data:','mailto:')):self.refs.append(values[key])


def refresh(publish):
    paths=' '.join('.cache/cargo-missions/'+p for p in PARENTS)
    command=f'cd {REMOTE} && .venv-g1/bin/python engine/tools/build_cargo_recovery_report.py --parents '+ ' '.join('engine/'+p for p in paths.split())+' --campaign engine/.cache/cargo-recovery-campaigns/warehouse_final_v1 --output engine/.cache/cargo-report'
    print(remote(command).strip(),flush=True)
    STAGING.mkdir(parents=True,exist_ok=True)
    subprocess.run(['rsync','-a','-e','ssh -o UserKnownHostsFile='+str(ROOT/'.cache/thor_known_hosts'),HOST+':'+REMOTE+'/engine/.cache/cargo-report/',str(STAGING)+'/'],check=True)
    data=json.loads((STAGING/'report-data.json').read_text());parser=References();parser.feed((STAGING/'index.html').read_text())
    for ref in parser.refs:
        target=(STAGING/urllib.parse.unquote(ref.split('#')[0].split('?')[0])).resolve()
        if not target.is_relative_to(STAGING.resolve()) or not target.is_file():raise ValueError('Nonportable or missing report reference: '+ref)
    for bank in data.get('complete_five_option_banks',[]):
        if not bank.get('checkpoint') or bank.get('cases')!=5:raise ValueError('Recovery bank pools states or has invalid option count')
    shutil.copytree(STAGING,ROOT/'reports/cargo-recovery',dirs_exist_ok=True)
    subprocess.run(['node','scripts/build_publication.mjs'],cwd=ROOT,check=True)
    if publish:
        stamp=time.strftime('%Y%m%d-%H%M%S');log=CACHE/f'deploy-{stamp}.log'
        with log.open('w') as stream:subprocess.run(['node',str(CLI),'deploy','--prod','--yes'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        response=urllib.request.urlopen(URL,timeout=30)
        if response.status!=200:raise ValueError('Public report is not accessible')
        response.close()
        videos=[ref for ref in parser.refs if ref.endswith('.mp4')]
        for ref in videos[:4]:
            request=urllib.request.Request(urllib.parse.urljoin(URL,ref),headers={'Range':'bytes=0-100'})
            with urllib.request.urlopen(request,timeout=30) as result:
                if result.status not in (200,206):raise ValueError('Video verification failed: '+ref)
    snapshot=dict(generated_utc=data['generated_utc'],status=data['status'],public_url=URL,qualified_baselines=data['qualified_baseline_count'],eligible_disturbed_forks=data['eligible_fork_count'],references_checked=len(parser.refs),published=publish)
    (CACHE/'latest-publication.json').write_text(json.dumps(snapshot,indent=2));print(json.dumps(snapshot),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--publish',action='store_true');ap.add_argument('--watch',action='store_true');ap.add_argument('--commit-final',action='store_true');args=ap.parse_args()
    last=-100;last_status=None
    while True:
        try:
            progress=json.loads(remote(f'cat {REMOTE}/engine/.cache/cargo-recovery-campaigns/warehouse_final_v1/progress.json'))
            count=progress.get('complete',0);status=progress.get('status');finished=status in ('complete','incomplete_technical_review')
            if not args.watch or count-last>=25 or finished and status!=last_status:
                refresh(args.publish);last=count;last_status=status
            if not args.watch or finished:
                if args.commit_final and finished:
                    subprocess.run(['git','add','reports/cargo-recovery'],cwd=ROOT,check=True)
                    dirty=subprocess.check_output(['git','diff','--cached','--name-only','--','reports/cargo-recovery'],cwd=ROOT,text=True)
                    if dirty.strip():
                        subprocess.run(['git','commit','--only','-m',f'Update cargo recovery report with {count} archived comparisons','--','reports/cargo-recovery'],cwd=ROOT,check=True)
                        subprocess.run(['git','push','origin','HEAD'],cwd=ROOT,check=True)
                return
        except Exception as error:
            print('Refresh failed; retaining last verified public report:',repr(error),flush=True)
            if not args.watch:raise
        time.sleep(45)


if __name__=='__main__':main()

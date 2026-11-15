"""Stream release assets from Thor. Credential comes through stdin, never a file/argument."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,http.client,json,sys,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    config=json.load(sys.stdin);token=config['token'];release_id=int(config['release_id']);repo=config['repository']
    if repo!='shubhrgunjan/beyond-recovery':raise ValueError('Unexpected upload repository')
    folder=ROOT/'artifacts/publication';index=json.loads((folder/'dataset-index.json').read_text())
    entries=index['archives']+[dict(file=n,bytes=(folder/n).stat().st_size) for n in ('dataset-index.json','SHA256SUMS')]
    uploaded=[]
    def request(method,path):
        r=urllib.request.Request('https://api.github.com'+path,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(r,timeout=60) as response:
            b=response.read();return json.loads(b) if b else None
    def upload(entry):
        p=folder/entry['file']
        if p.stat().st_size!=entry['bytes']:raise ValueError('File size changed '+p.name)
        for attempt in range(3):
            try:
                assets=request('GET',f'/repos/{repo}/releases/{release_id}/assets?per_page=100')
                old=next((a for a in assets if a['name']==p.name),None)
                if old:
                    if old['state']=='uploaded' and old['size']==p.stat().st_size:return dict(name=p.name,size=old['size'],digest=old.get('digest'),already_uploaded=True)
                    request('DELETE',f'/repos/{repo}/releases/assets/{old["id"]}')
                connection=http.client.HTTPSConnection('uploads.github.com',timeout=900)
                uri=f'/repos/{repo}/releases/{release_id}/assets?'+urllib.parse.urlencode({'name':p.name})
                connection.putrequest('POST',uri);connection.putheader('Authorization','Bearer '+token)
                connection.putheader('User-Agent','beyond-recovery-release-uploader');connection.putheader('Accept','application/vnd.github+json')
                connection.putheader('Content-Type','application/octet-stream');connection.putheader('Content-Length',str(p.stat().st_size));connection.endheaders()
                h=hashlib.sha256()
                with p.open('rb') as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk);connection.send(chunk)
                response=connection.getresponse();body=response.read();connection.close()
                if response.status!=201:raise RuntimeError('Upload status '+str(response.status)+' '+body.decode()[:200])
                result=json.loads(body);digest=h.hexdigest()
                if entry.get('sha256') and digest!=entry['sha256']:raise ValueError('Local SHA changed '+p.name)
                if result.get('digest') and result['digest']!='sha256:'+digest:raise ValueError('Remote SHA mismatch '+p.name)
                return dict(name=p.name,size=result['size'],digest=result.get('digest'),url=result['browser_download_url'])
            except Exception as e:
                if attempt==2:raise
                print(json.dumps(dict(retry=p.name,attempt=attempt+1,error=type(e).__name__)),flush=True);time.sleep(2)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(upload,e):e for e in entries}
        for future in as_completed(futures):
            result=future.result();uploaded.append(result)
            (folder/'upload-results.json').write_text(json.dumps(uploaded,indent=2)+'\n')
            print(json.dumps(dict(completed=len(uploaded),total=len(entries),asset=result)),flush=True)
    print('UPLOAD COMPLETE',len(uploaded),flush=True)
if __name__=='__main__':main()

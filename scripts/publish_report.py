"""Publish the checkpointed research report into the live console's static directory."""
import argparse,hashlib,html,shutil,time
from pathlib import Path
import markdown

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');args=parser.parse_args()
last=None
while True:
    source=root/'reports/WAKE_UP_REPORT.md'
    if source.exists():
        raw=source.read_text();digest=hashlib.sha256(raw.encode()).hexdigest()
        if digest!=last:
            output=root/'web/dist';output.mkdir(parents=True,exist_ok=True)
            body=markdown.markdown(raw,extensions=['tables','fenced_code'])
            document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Beyond Recovery · Wake-up report</title><style>
:root{font-family:system-ui,sans-serif;color:#24332f;background:#f3f5f1}body{margin:0}nav{padding:16px 5%;background:#182a24;display:flex;gap:24px;align-items:center}nav a{color:#b5e4cc;font-size:13px}main{max-width:1150px;margin:35px auto;padding:0 28px 60px}h1{font-size:32px;letter-spacing:-.8px}h2{margin-top:35px;font-size:21px;border-bottom:1px solid #cbd5cc;padding-bottom:9px}p,li{font-size:14px;line-height:1.8}table{border-collapse:collapse;width:100%;font-size:12px;display:block;overflow:auto}th,td{text-align:left;border-bottom:1px solid #d5ddd5;padding:10px 12px}th{background:#dce8df}tr:nth-child(even){background:#eaf0e9}video{width:100%;max-height:540px;background:#15231d}img{max-width:100%;background:white;border:1px solid #d3ddd4;border-radius:6px}code{font-size:11px;background:#e4eae4;padding:2px 4px;overflow-wrap:anywhere}a{color:#226848}blockquote{border-left:3px solid #6b9f80;margin-left:0;padding:5px 20px;background:#e3ede5}@media print{nav{display:none}main{padding:0;margin:0}h2{break-after:avoid}table,img{break-inside:avoid}}
</style><nav><a href="/">← Live console</a><a href="WAKE_UP_REPORT.md" download>Download Markdown</a><a href="research-bundle.zip" download>Report + figures + videos (16 MB)</a><a href="#" onclick="window.print();return false">Print / save PDF</a></nav><main>'''+body+'</main></html>'
            temporary=output/'research-report.tmp';temporary.write_text(document);temporary.replace(output/'research-report.html')
            (output/'WAKE_UP_REPORT.md').write_text(raw)
            for folder in ('figures','clips','data'):
                if (root/'reports'/folder).exists():shutil.copytree(root/'reports'/folder,output/folder,dirs_exist_ok=True)
            print('Published report',time.strftime('%H:%M:%S'),flush=True);last=digest
    if not args.watch:break
    time.sleep(30)

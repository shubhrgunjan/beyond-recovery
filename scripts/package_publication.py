"""Make the downloadable report self-contained, with durable public navigation links."""
import json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'deployment/public.json').read_text())
source=ROOT/'public/report'
html=(source/'index.html').read_text().replace('href="/"',f'href="{config["site"]}/"').replace('href="/lab"',f'href="{config["site"]}/lab"')
temporary=ROOT/'reports/research-bundle.tmp'
with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('research-report.html',html)
    z.write(source/'WAKE_UP_REPORT.md','WAKE_UP_REPORT.md')
    z.writestr('README.txt',f'Open research-report.html to read the report offline. Figures, videos and compact data tables are included.\n\nPublic research home: {config["site"]}\nOnline report: {config["site"]}/report/\nShared live simulator: {config["site"]}/lab\nRaw data and checksums: {config["site"]}/downloads/\nSource: {config["repository"]}\n\nThis publication copy updates navigation links; underlying experimental measurements are unchanged. The full raw archives are downloaded separately.\n')
    for folder in ('figures','clips','data'):
        for p in (source/folder).rglob('*'):
            if p.is_file():z.write(p,str(p.relative_to(source)))
temporary.replace(ROOT/'reports/research-bundle.zip')
print('Packaged offline public report with durable navigation links.')

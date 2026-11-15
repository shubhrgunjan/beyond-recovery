import fs from 'node:fs';import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../public');const problems=[];let checked=0;
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)])}
for(const file of walk(root).filter(p=>p.endsWith('.html'))){
 const content=fs.readFileSync(file,'utf8');
 if(/__\w+__|http:\/\/localhost:8080|\/home\/(saidevdhal|shubhr)\//.test(content))problems.push(`${file}: unresolved or local reference`);
 for(const [,ref] of content.matchAll(/(?:href|src)="([^"]+)"/g)){
  if(/^(https?:|#|mailto:)/.test(ref)||ref==='/lab')continue;
  const [url,fragment]=ref.split('#');let target=path.resolve(ref.startsWith('/')?root:path.dirname(file),'.'+(ref.startsWith('/')?url:'/'+url));
  if(!url)target=file;if(fs.existsSync(target)&&fs.statSync(target).isDirectory())target=path.join(target,'index.html');
  if(!fs.existsSync(target))problems.push(`${file}: missing ${ref}`);
  else if(fragment&&target.endsWith('.html')&&!fs.readFileSync(target,'utf8').includes(`id="${fragment}"`))problems.push(`${file}: missing anchor ${ref}`);
  checked++;
 }
}
if(problems.length){console.error(problems.join('\n'));process.exit(1)}console.log(`PASS ${checked} publication links, asset paths and report anchors.`);

import { chromium } from 'playwright'
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path'
const ROOT='D:/hesabdari/desktop', OUT=process.argv[2]
const MIME={'.html':'text/html','.css':'text/css','.woff2':'font/woff2'}
const s=http.createServer((q,r)=>{const p=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));fs.readFile(p,(e,d)=>{if(e){r.writeHead(404);r.end()}else{r.writeHead(200,{'Content-Type':MIME[path.extname(p)]||'x'});r.end(d)}})})
await new Promise(r=>s.listen(0,r)); const url=`http://127.0.0.1:${s.address().port}/_qa.html`
const b=await chromium.launch()
const c=await b.newContext({viewport:{width:390,height:600},deviceScaleFactor:2});const pg=await c.newPage()
await pg.goto(url,{waitUntil:'networkidle'});await pg.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await pg.waitForTimeout(200)
await pg.screenshot({path:OUT+'/quote-actions-mobile.png'});console.log('shot');await b.close();s.close()

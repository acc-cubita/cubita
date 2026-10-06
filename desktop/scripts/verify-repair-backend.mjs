/** Actual React -> HTTP -> FastAPI -> isolated PostgreSQL, supplied by pytest. */
import {chromium} from 'playwright'
import assert from 'node:assert/strict'
const target=new URL(process.env.REPAIR_QA_API_URL??'')
assert.equal(target.hostname,'127.0.0.1')
assert.ok(Number(target.port)>1024)
const base='http://127.0.0.1:5187'
const browser=await chromium.launch({headless:true})
try {
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1000}}),errors=[]
    page.on('pageerror',e=>errors.push(e.message))
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
    // Hot reload is unrelated to this integration test and opens a WebSocket.
    await page.route(base+'/@vite/client',route=>route.fulfill({contentType:'application/javascript',body:`export const createHotContext=()=>({accept(){},prune(){},dispose(){},data:{},invalidate(){},on(){},off(){},send(){}});export const injectQuery=(url,q)=>url+(url.includes('?')?'&':'?')+q;export function updateStyle(id,css){let el=document.querySelector('style[data-vite-id="'+id+'"]');if(!el){el=document.createElement('style');el.dataset.viteId=id;document.head.append(el)}el.textContent=css}export const removeStyle=()=>{};`}))
    // The test DB session is intentionally one transaction: serialize reads
    // here rather than sharing it concurrently across HTTP worker threads.
    let queue=Promise.resolve()
    await page.route('**/api/**',route=>{
      const run=async()=>{
        const req=route.request()
        if(req.method()==='OPTIONS') {await route.fulfill({status:200,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});return}
        const url=new URL(req.url()),destination=new URL(url.pathname+url.search,target)
        const response=await page.request.fetch(destination.href,{method:req.method(),headers:{'Authorization':req.headers()['authorization']??'','Idempotency-Key':req.headers()['idempotency-key']??'','Content-Type':req.headers()['content-type']??'application/json'},data:req.postDataBuffer()??undefined})
        await route.fulfill({response,headers:{...response.headers(),'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'}})
      }
      queue=queue.then(run);return queue
    })
    await page.route(base+'/repair-backend-qa',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
      import React from '/node_modules/.vite/deps/react.js';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      const {RepairPage}=await import('/src/pages/repair/RepairPage.tsx');import '/src/index.css';import '/src/App.css';
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(RepairPage,{token:'isolated-test-principal',me:{permissions:{repair:['view','create','update','approve']}}}));
    </script></html>`}))
    await page.goto(base+'/repair-backend-qa')
    await page.getByRole('button',{name:'پذیرش دستگاه',exact:true}).click()
    await page.getByLabel('مشتری',{exact:true}).selectOption(process.env.REPAIR_QA_CONTACT)
    await page.getByLabel('شعبه',{exact:true}).selectOption(process.env.REPAIR_QA_BRANCH)
    await page.getByLabel('نوع دستگاه',{exact:true}).last().selectOption(process.env.REPAIR_QA_TYPE)
    await page.getByLabel('مدل',{exact:true}).fill('پذیرش واقعی مرورگر '+width)
    await page.getByLabel('ایراد اعلام‌شده',{exact:true}).fill('آزمون رابط و بک‌اند واقعی')
    await page.getByLabel('محل نگهداری',{exact:true}).fill('قفسه آزمایشی')
    await page.getByLabel('شرایط پذیرش',{exact:true}).fill('فقط دیتابیس آزمایشی')
    await page.getByRole('button',{name:'ثبت پذیرش',exact:true}).click()
    await page.getByRole('heading',{name:/پذیرش .* —/}).waitFor()
    await queue
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
    assert.deepEqual(errors,[])
    await page.screenshot({path:`../_deploy/repair-qa/backend-${width}.png`,fullPage:true})
    console.log(`Actual repair backend ${width}: admission and persisted detail OK`)
    await page.close()
  }
} finally {await browser.close()}

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
    let queue=Promise.resolve(), closing=false
    const bodies=new Map()
    await page.route('**/api/**',route=>{
      const run=async()=>{
        const req=route.request()
        if(req.method()==='OPTIONS') {await route.fulfill({status:200,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});return}
        const url=new URL(req.url()),destination=new URL(url.pathname+url.search,target)
        const response=await page.request.fetch(destination.href,{method:req.method(),headers:{'Authorization':req.headers()['authorization']??'','Idempotency-Key':req.headers()['idempotency-key']??'','Content-Type':req.headers()['content-type']??'application/json'},data:req.postDataBuffer()??undefined})
        if(response.status()>=400)errors.push(req.method()+' '+url.pathname+': '+await response.text())
        if(req.method()==='POST'&&['/api/repair/intake-batches','/api/repair/bulk-operations'].includes(url.pathname))bodies.set(url.pathname,await response.json())
        await route.fulfill({response,headers:{...response.headers(),'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'}})
      }
      queue=queue.then(()=>run().catch(error=>{if(!closing)throw error}));return queue
    })
    await page.route(base+'/repair-backend-qa',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
      import React from '/node_modules/.vite/deps/react.js';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      const {RepairPage}=await import('/src/pages/repair/RepairPage.tsx');import '/src/index.css';import '/src/App.css';
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(RepairPage,{token:'isolated-test-principal',me:{permissions:{repair:['view','create','update','approve'],repair_signatures:['view','create']}}}));
    </script></html>`}))
    await page.goto(base+'/repair-backend-qa')
    await page.getByRole('button',{name:'پذیرش دستگاه',exact:true}).click()
    await page.locator('form').getByLabel('مشتری',{exact:true}).selectOption(process.env.REPAIR_QA_CONTACT)
    await page.locator('form').getByLabel('شعبه',{exact:true}).selectOption(process.env.REPAIR_QA_BRANCH)
    await page.locator('form').getByLabel('نوع دستگاه',{exact:true}).last().selectOption(process.env.REPAIR_QA_TYPE)
    await page.locator('form').getByLabel('مدل',{exact:true}).fill('پذیرش واقعی مرورگر '+width)
    await page.locator('form').getByLabel('ایراد اعلام‌شده',{exact:true}).fill('آزمون رابط و بک‌اند واقعی')
    await page.locator('form').getByLabel('محل نگهداری',{exact:true}).fill('قفسه آزمایشی')
    await page.locator('form').getByLabel('شرایط پذیرش',{exact:true}).fill('فقط دیتابیس آزمایشی')
    await page.getByRole('button',{name:'ثبت پذیرش',exact:true}).click()
    await page.getByRole('heading',{name:/پذیرش .* —/}).waitFor()
    await page.getByRole('button',{name:'شروع تایمر من',exact:true}).click()
    await page.getByRole('button',{name:'توقف تایمر',exact:true}).click()
    await page.getByRole('button',{name:'تأیید زمان نهایی',exact:true}).click()
    await page.getByRole('button',{name:'ثبت اصلاح با سابقه',exact:true}).waitFor()
    await page.getByLabel('نام تأییدکننده',{exact:true}).fill('مالک آزمایشی')
    const box=await page.getByLabel('محل رسم امضای تأییدکننده').boundingBox()
    assert.ok(box)
    await page.getByLabel('محل رسم امضای تأییدکننده').scrollIntoViewIfNeeded()
    const visible=await page.getByLabel('محل رسم امضای تأییدکننده').boundingBox()
    await page.mouse.move(visible.x+20,visible.y+20);await page.mouse.down();await page.mouse.move(visible.x+90,visible.y+60,{steps:6});await page.mouse.up()
    const ackResponse=page.waitForResponse(response=>response.url().endsWith('/acknowledgments')&&response.request().method()==='POST')
    await page.getByRole('button',{name:'ثبت تأیید این نسخه',exact:true}).click()
    assert.equal((await ackResponse).status(),201)
    assert.equal(await page.getByRole('alert').count(),0)
    const quick=page.locator('details').filter({has:page.locator('summary').filter({hasText:'پذیرش سریع یک یا چند دستگاه'})}).first()
    await quick.locator('summary').first().click()
    await quick.getByLabel('شعبه',{exact:true}).selectOption(process.env.REPAIR_QA_BRANCH)
    await quick.getByLabel('مشتری یا سازمان',{exact:true}).selectOption(process.env.REPAIR_QA_CONTACT)
    await quick.getByText('تنظیمات پذیرش سریع شعبه',{exact:true}).click()
    await quick.getByLabel('کد شرکت/شعبه',{exact:true}).fill('QA')
    await quick.getByLabel('محل نگهداری پیش‌فرض',{exact:true}).fill('قفسه گروهی')
    await quick.getByLabel('شرایط پذیرش',{exact:true}).fill('شرایط پذیرش گروهی آزمایشی')
    await quick.getByRole('button',{name:'ذخیره تنظیمات شعبه',exact:true}).click()
    await quick.getByText('محل پذیرش: قفسه گروهی',{exact:false}).waitFor()
    await quick.getByLabel('نوع دستگاه',{exact:true}).first().selectOption(process.env.REPAIR_QA_TYPE)
    await quick.getByLabel('مدل',{exact:true}).first().fill('گروهی یک '+width)
    await quick.getByLabel('ایراد اعلام‌شده',{exact:true}).first().fill('آزمون گروهی اول')
    await quick.getByRole('button',{name:'افزودن دستگاه دیگر',exact:true}).click()
    await quick.getByLabel('نوع دستگاه',{exact:true}).last().selectOption(process.env.REPAIR_QA_TYPE)
    await quick.getByLabel('مدل',{exact:true}).last().fill('گروهی دو '+width)
    await quick.getByLabel('ایراد اعلام‌شده',{exact:true}).last().fill('آزمون گروهی دوم')
    const batchResponse=page.waitForResponse(response=>response.url().endsWith('/intake-batches')&&response.request().method()==='POST')
    await quick.getByRole('button',{name:'ثبت پذیرش دستگاه‌ها',exact:true}).click()
    const batch=await batchResponse;assert.equal(batch.status(),201);const group=bodies.get('/api/repair/intake-batches');assert.equal(group.items.length,2)
    const bulk=page.locator('details').filter({has:page.locator('summary').filter({hasText:'اسکن و عملیات گروهی کارتابل'})}).first()
    await bulk.locator('summary').first().click()
    await bulk.locator('input[type="checkbox"]').first().check()
    await bulk.getByLabel('دلیل',{exact:true}).fill('آزمون عملیات گروهی مرورگر')
    const bulkResponse=page.waitForResponse(response=>response.url().endsWith('/bulk-operations')&&response.request().method()==='POST')
    await bulk.getByRole('button',{name:/اجرای عملیات روی/}).click()
    const bulkResult=await bulkResponse;assert.equal(bulkResult.status(),201);assert.equal(bodies.get('/api/repair/bulk-operations').results[0].ok,true)
    await bulk.getByLabel('شماره یا کد اسکن‌شده',{exact:true}).fill('cubita:repair:'+group.items[0].id)
    const scanned=page.waitForResponse(response=>response.url().endsWith('/cases/'+group.items[0].id)&&response.request().method()==='GET')
    await bulk.getByRole('button',{name:'باز کردن پرونده',exact:true}).click();assert.equal((await scanned).status(),200)


    await queue
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
    assert.deepEqual(errors,[])
    await queue
    await page.screenshot({path:`../_deploy/repair-qa/backend-${width}.png`,fullPage:true})
    console.log(`Actual repair backend ${width}: admission and persisted detail OK`)
    closing=true
    await page.unrouteAll({behavior:'ignoreErrors'})
    await page.close()
  }
} finally {await browser.close()}

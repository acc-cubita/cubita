/** UI regression uses HTTP fixtures only; it never connects to a customer database. */
import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'

const base = 'http://127.0.0.1:5187'
const browser = await chromium.launch({ headless: true })
await mkdir('../_deploy/repair-qa', { recursive: true })
try {
  for (const width of [1440,390]) {
    const page = await browser.newPage({ viewport: { width,height:1000 } })
    const errors = []
    page.on('pageerror', e => { errors.push(e.message); console.error(e.message) })
    page.on('console', m => { if(m.type() === 'error') { errors.push(m.text()); console.error(m.text()) } })
    const rows = []
    const requests = []
    const branches = [{ id:'11111111-1111-4111-8111-111111111111',name:'مرکزی',is_active:true }]
    const types = [{ id:'22222222-2222-4222-8222-222222222222',name:'رایانه',is_active:true,fields:['رنگ'],checklist:['شارژر'] }]
    const contacts = [{ id:'33333333-3333-4333-8333-333333333333',name:'مشتری آزمون رابط',phone:'09123456789',is_active:true }]
    await page.route(base + '/@vite/client', route => route.fulfill({ contentType:'application/javascript', body:`export const createHotContext=()=>({accept(){},prune(){},dispose(){},data:{},invalidate(){},on(){},off(){},send(){}});export const injectQuery=(url,q)=>url+(url.includes('?')?'&':'?')+q;export function updateStyle(id,css){let el=document.querySelector('style[data-vite-id="'+id+'"]');if(!el){el=document.createElement('style');el.dataset.viteId=id;document.head.append(el)}el.textContent=css}export const removeStyle=()=>{};` }))
    await page.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url())
      let data
      if(req.method() === 'OPTIONS') data = {}
      else if(url.pathname === '/api/contacts') data = { items:contacts,next_cursor:null }
      else if(url.pathname === '/api/repair/branches') data = branches
      else if(url.pathname === '/api/repair/device-types') data = types
      else if(url.pathname === '/api/repair/members') data = []
      else if(url.pathname === '/api/repair/technicians') data = []
      else if(url.pathname === '/api/repair/warehouses') data = []
      else if(url.pathname === '/api/repair/access-capabilities') data = {encrypted_storage_available:false}
      else if(url.pathname === '/api/repair/message-templates') data = []
      else if(url.pathname.endsWith('/notifications')) data = {sms_available:false,messages:[]}
      else if(url.pathname === '/api/repair/fee-rules') data = []
      else if(url.pathname === '/api/repair/service-requests') data = {items:[],next_cursor:null}
      else if(['/api/repair/maintenance-contracts','/api/repair/maintenance-plans','/api/repair/consolidated-bills'].includes(url.pathname)) data = []
      else if(url.pathname.endsWith('/contract')) data = null
      else if(url.pathname.endsWith('/custody') || url.pathname.endsWith('/loans')) data = []
      else if(url.pathname.endsWith('/technician-fees')) data = []
      else if(url.pathname.endsWith('/warranties')) data = {warranties:[],origin:null,revisits:[]}
      else if(url.pathname.endsWith('/portal-links')) data = []
      else if(url.pathname.endsWith('/customer-messages')) data = []
      else if(url.pathname === '/api/repair/faults') data = []
      else if(url.pathname === '/api/repair/catalog') data = { items:[],next_cursor:null }
      else if(url.pathname.endsWith('/attachments')) data = []
      else if(url.pathname === '/api/repair/cases' && req.method() === 'POST') {
        const body = req.postDataJSON(); requests.push({ body,key:req.headers()['idempotency-key'] })
        data = { ...body,id:'44444444-4444-4444-8444-444444444444',device_id:'55555555-5555-4555-8555-555555555555',number:1,version:1,status:'accepted',owner_snapshot:{ name:contacts[0].name,phone:contacts[0].phone },device_snapshot:{ ...body.device,category:types[0].name },open_case_warnings:[],visits:[],events:[] }; rows.push(data)
      } else if(url.pathname === '/api/repair/cases') data = { items:rows,next_cursor:null }
      else if(url.pathname.startsWith('/api/repair/cases/')) data = rows[0]
      else throw new Error('Unexpected fixture request: ' + req.url())
      await route.fulfill({ json:data,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Authorization,Content-Type,Idempotency-Key','Access-Control-Allow-Methods':'GET,POST,PUT,OPTIONS'} })
    })
    await page.route(base + '/repair-qa', route => route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;
      import React from '/node_modules/.vite/deps/react.js'; import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      const {RepairPage}=await import('/src/pages/repair/RepairPage.tsx'); import '/src/index.css'; import '/src/App.css';
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(RepairPage,{token:'fixture',me:{permissions:{repair:['view','create','update','approve']}}}));
      </script></html>` }))
    await page.goto(base + '/repair-qa')
    await page.getByRole('button',{name:'پذیرش دستگاه',exact:true}).click()
    await page.getByLabel('مشتری',{exact:true}).selectOption(contacts[0].id)
    await page.getByLabel('شعبه',{exact:true}).selectOption(branches[0].id)
    await page.getByLabel('نوع دستگاه',{exact:true}).last().selectOption(types[0].id)
    await page.getByLabel('مدل',{exact:true}).fill('رایانه آزمایشی')
    await page.getByLabel('ایراد اعلام‌شده',{exact:true}).fill('روشن نمی‌شود')
    await page.getByLabel('محل نگهداری',{exact:true}).fill('قفسه الف')
    await page.getByLabel('شرایط پذیرش',{exact:true}).fill('برآورد باید تأیید شود')
    await page.screenshot({ path:`../_deploy/repair-qa/admission-${width}.png`,fullPage:true })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false,'Admission overflows')
    await page.getByRole('button',{name:'ثبت پذیرش',exact:true}).click()
    await page.getByRole('heading',{name:/پذیرش ۱ —/}).waitFor()
    assert.equal(requests.length,1)
    assert.ok(requests[0].key)
    await page.locator('details').evaluateAll(elements=>elements.forEach(element=>{element.open=true}))
    await page.screenshot({ path:`../_deploy/repair-qa/case-${width}.png`,fullPage:true })
    await page.getByRole('heading',{name:/پذیرش ۱ —/}).scrollIntoViewIfNeeded()
    await page.screenshot({path:`../_deploy/repair-qa/case-viewport-${width}.png`})
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false,'Case overflows')
    assert.deepEqual(errors,[])
    console.log(`Repair UI ${width}: admission, idempotency header, detail, no overflow/console errors OK`)
    await page.close()
  }
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1000}})
    const errors=[],decisions=[],messages=[]
    page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
    const row={number:12,version:2,status:'awaiting_customer',status_label:'منتظر مشتری',admission_date:'2026-10-06',due_date:'2026-10-09',device:{brand:'نمونه',model:'دستگاه آزمون'},customer:'مشتری آزمون صفحه عمومی',reported_issue:'خاموش شدن',accessories:'شارژر',terms:'هزینه پس از تأیید',results:[],attachments:[],messages:[],online_payment_available:false,estimate:{id:'77777777-7777-4777-8777-777777777777',version:1,valid_until:'2026-10-09',duration_days:2,currency:'IRR',options:[{title:'تعویض قطعه',total:'12345',lines:[{kind:'part',title:'قطعه آزمون',qty:'1',unit_price:'12345',amount:'12345'}]}],decision:null}}
    const credential='11111111-1111-4111-8111-111111111111.'+'A'.repeat(43)
    await page.route(base+'/@vite/client',route=>route.fulfill({contentType:'application/javascript',body:`export const createHotContext=()=>({accept(){},prune(){},dispose(){},data:{},invalidate(){},on(){},off(){},send(){}});export const injectQuery=(url,q)=>url+(url.includes('?')?'&':'?')+q;export function updateStyle(id,css){let el=document.querySelector('style[data-vite-id="'+id+'"]');if(!el){el=document.createElement('style');el.dataset.viteId=id;document.head.append(el)}el.textContent=css}export const removeStyle=()=>{};`}))
    await page.route('**/api/**',async route=>{
      const req=route.request(),path=new URL(req.url()).pathname
      let data={}
      if(req.method()!=='OPTIONS') {
        assert.equal(req.headers()['authorization'],'RepairPortal '+credential)
        assert.equal(new URL(req.url()).search,'')
        if(path==='/api/repair-portal/case')data=row
        else if(path==='/api/repair-portal/decision'){
          assert.ok(req.headers()['idempotency-key']);const body=req.postDataJSON();decisions.push(body)
          row.estimate.decision={...body,created_at:'2026-10-06T12:00:00Z'};row.version++;data={id:'decision-fixture'}
        } else if(path==='/api/repair-portal/messages'){
          assert.ok(req.headers()['idempotency-key']);const body=req.postDataJSON();messages.push(body)
          row.messages.push({...body,id:'message-fixture',created_at:'2026-10-06T12:00:00Z'});row.version++;data={id:'message-fixture'}
        } else throw new Error('Unexpected public request: '+path)
      }
      await route.fulfill({json:data,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Authorization,Content-Type,Idempotency-Key','Access-Control-Allow-Methods':'GET,POST,OPTIONS'}})
    })
    await page.goto(base+'/repair-track#token='+credential)
    await page.getByRole('heading',{name:'پیگیری تعمیرگاه',exact:true}).waitFor()
    await page.getByRole('button',{name:'تأیید گزینه با همین مبلغ',exact:true}).click()
    await page.getByRole('status').filter({hasText:'تصمیم برای نسخه'}).waitFor()
    assert.equal(decisions.length,1);assert.equal(decisions[0].estimate_id,row.estimate.id)
    await page.getByLabel('متن',{exact:true}).fill('پیگیری مشتری در آزمون رابط')
    await page.getByRole('button',{name:'ثبت پیام',exact:true}).click()
    await page.getByRole('status').filter({hasText:'پیام برای تعمیرگاه ثبت شد'}).waitFor()
    assert.equal(messages.length,1);assert.equal(await page.evaluate(()=>location.hash),'')
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Public portal overflows')
    assert.deepEqual(errors,[])
    await page.screenshot({path:`../_deploy/repair-qa/portal-${width}.png`,fullPage:true})
    console.log(`Repair portal ${width}: real React decision/message, key, token absent from URL, no overflow/errors OK`)
    await page.close()
  }
} finally { await browser.close() }

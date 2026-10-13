import {chromium} from 'playwright'
import assert from 'node:assert/strict'
const target=new URL(process.env.REPAIR_QA_API_URL),caseId=process.env.REPAIR_QA_CASE,warrantyId=process.env.REPAIR_QA_WARRANTY
assert.equal(target.hostname,'127.0.0.1')
const base='http://127.0.0.1:5187',browser=await chromium.launch({headless:true})
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000}}),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  const request=async(path,data)=>{const response=await page.request.fetch(new URL(path,target).href,{method:data?'POST':'GET',headers:{Authorization:'Bearer isolated','Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},...(data?{data}:{})});assert.ok(response.ok(),await response.text());return response.json()}
  const row=await request('/api/repair/cases/'+caseId),device=await request('/api/repair/devices/'+row.device_id)
  const owner=await request('/api/contacts',{name:'مالک مرورگر '+width,type:'customer'})
  const history=await request('/api/repair/devices/'+row.device_id+'/identity-events')
  await request('/api/repair/devices/'+row.device_id+'/ownership',{version:device.version,contact_id:owner.id,previous_ownership_id:history.items.find(e=>e.kind==='ownership')?.id??null,reason:'آزمون انتقال مالکیت',evidence:'مدرک آزمون مستقل'})
  let queue=Promise.resolve()
  await page.route('**/api/**',route=>{queue=queue.then(async()=>{
   const req=route.request(),url=new URL(req.url())
   if(req.method()==='OPTIONS'){await route.fulfill({status:200,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});return}
   const response=await page.request.fetch(new URL(url.pathname+url.search,target).href,{method:req.method(),headers:{Authorization:'Bearer isolated','Content-Type':'application/json','Idempotency-Key':req.headers()['idempotency-key']??''},data:req.postDataBuffer()??undefined})
   if(!response.ok())errors.push(await response.text())
   await route.fulfill({response,headers:{...response.headers(),'Access-Control-Allow-Origin':'*'}})
  });return queue})
  await page.route(base+'/warranty-transfer-qa',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
   import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
   import React from '/node_modules/.vite/deps/react.js';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';import '/src/index.css';import '/src/App.css';import '/src/pages/repair/repair.css';
   const {RepairWarranty}=await import('/src/pages/repair/RepairWarranty.tsx');const {RepairTechnicalSummary}=await import('/src/pages/repair/RepairTechnicalSummary.tsx');const {RepairOwnershipClaims}=await import('/src/pages/repair/RepairOwnershipClaims.tsx');const {RepairRepresentatives}=await import('/src/pages/repair/RepairRepresentatives.tsx');const api=await import('/src/api.ts');
   const me={permissions:{repair:['view','approve','create'],repair_warranty_transfer:['approve'],repair_technical_summary:['approve'],repair_identity:['view','approve'],repair_representation:['view','approve']}};
   function App(){const [row,setRow]=React.useState(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('');const refresh=async()=>setRow(await api.fetchRepairCase('isolated','${caseId}'));React.useEffect(()=>{refresh().catch(e=>setError(e.message))},[]);const run=async action=>{setBusy(true);try{await action()}catch(e){setError(e.message)}finally{setBusy(false)}};return React.createElement('main',{style:{maxWidth:1000,margin:'auto',padding:16}},error&&React.createElement('p',{role:'alert'},error),row&&React.createElement(RepairWarranty,{token:'isolated',me,row,busy,run,refresh,open:async()=>{}}),row&&React.createElement(RepairTechnicalSummary,{token:'isolated',me,row,busy,run,refresh}),row&&React.createElement(RepairOwnershipClaims,{token:'isolated',me,row,busy,run,refresh}),row&&React.createElement(RepairRepresentatives,{token:'isolated',me,row,busy,run,refresh}))};ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
  </script>`}))
  await page.goto(base+'/warranty-transfer-qa')
  await page.getByText('انتقال ضمانت به مالک تأییدشده',{exact:true}).click()
  await page.getByRole('button',{name:'بررسی مالک و ضمانت'}).click()
  await page.getByText('مالک نهایی: مالک مرورگر '+width,{exact:true}).waitFor()
  await page.getByLabel('دلیل تأیید مدیر فنی').fill('تأیید مدارک مالک جدید در آزمون مرورگر')
  await page.screenshot({path:`../_deploy/repair-professional-qa/warranty-transfer-${width}.png`,fullPage:true})
  const refreshed=page.waitForResponse(response=>response.url().endsWith('/warranties')&&response.request().method()==='GET')
  await page.getByRole('button',{name:'تأیید انتقال با همان پوشش و مهلت'}).click()
  await page.getByLabel('دلیل تأیید مدیر فنی').waitFor({state:'hidden'})
  await refreshed
  await queue
  const after=await request('/api/repair/cases/'+caseId+'/warranties')
  assert.equal(after.transfers[0].contact_id,owner.id)
  assert.equal(after.transfers[0].warranty_id,warrantyId)
  await page.getByText('خلاصهٔ فنی قابل انتقال',{exact:true}).click()
  await page.getByRole('button',{name:'آماده‌سازی خلاصه برای مالک فعلی'}).click()
  await page.getByText('گیرندهٔ مجاز: مالک مرورگر '+width,{exact:true}).waitFor()
  await page.getByLabel('وضعیت فنی دستگاه',{exact:true}).fill('دستگاه پس از تنظیم سالم است')
  await page.getByLabel('تعمیرات انجام‌شده',{exact:true}).fill('تنظیم برد کنترل')
  await page.getByLabel('نتایج آزمون',{exact:true}).fill('آزمون عملکرد موفق')
  await page.getByLabel('توصیهٔ نگهداری',{exact:true}).fill('دور از رطوبت نگهداری شود')
  await page.getByLabel('دلیل تأیید',{exact:true}).fill('بازبینی متن فنی بدون اطلاعات مالک قبلی')
  await page.getByRole('checkbox',{name:'متن را بازبینی کردم'}).check()
  await page.screenshot({path:`../_deploy/repair-professional-qa/technical-summary-${width}.png`,fullPage:true})
  await page.getByRole('button',{name:'تأیید و نمایش برای مالک مشخص‌شده'}).click()
  await page.getByText('خلاصه برای مالک مشخص‌شده تأیید شد؛ پرونده و اسناد قبلی تغییر نکردند.',{exact:true}).waitFor()
  await queue
  const current=await request('/api/repair/cases/'+caseId),identity=await request('/api/repair/devices/'+current.device_id)
  await request('/api/repair/cases/'+caseId+'/ownership-claims',{version:current.version,device_version:identity.version,contact_id:owner.id,reason:'ادعای آزمون مرورگر',evidence:'سند آزمایشی قابل بررسی'})
  await page.reload()
  await page.getByText('ادعای مالکیت؛ ثبت و بررسی جداگانه',{exact:true}).click()
  await page.getByRole('button',{name:'دریافت اشخاص و ادعاهای مجاز'}).click()
  await page.getByText('ادعای آزمون مرورگر',{exact:true}).first().waitFor()
  await page.getByRole('button',{name:'بررسی تعارض با مالک فعلی'}).click()
  await page.getByText('مالک تأییدشدهٔ فعلی: مالک مرورگر '+width,{exact:true}).waitFor()
  await page.getByLabel('دلیل ادعا یا تصمیم',{exact:true}).fill('رد ادعای تکراری در آزمون')
  await page.getByLabel('مدرک بررسی‌شده',{exact:true}).fill('همان مدرک مالکیت فعلی')
  await page.screenshot({path:`../_deploy/repair-professional-qa/ownership-claim-${width}.png`,fullPage:true})
  await page.getByRole('button',{name:'رد ادعا و حفظ مالک فعلی'}).click()
  await page.getByText('رد شده',{exact:true}).first().waitFor()
  await queue
  await page.getByText('اختیار نمایندهٔ پذیرش و تحویل',{exact:true}).click()
  await page.getByRole('button',{name:'دریافت نمایندگان و اشخاص'}).click()
  await page.getByLabel('نام نماینده',{exact:true}).fill('نماینده آزمایشی '+width)
  await page.getByLabel('همراه نماینده',{exact:true}).fill('09123456789')
  await page.getByLabel('پایان اعتبار',{exact:true}).click()
  await page.getByRole('button',{name:'امروز',exact:true}).click()
  await page.getByLabel('مدرک اختیار نماینده',{exact:true}).fill('وکالت‌نامه آزمایشی بررسی شد')
  await page.getByRole('button',{name:'تأیید اختیار نماینده',exact:true}).click()
  await page.getByRole('button',{name:'لغو اختیار نماینده آزمایشی '+width,exact:true}).waitFor()
  await page.getByLabel('دلیل لغو اختیار',{exact:true}).fill('لغو آزمایشی از سوی اصیل')
  await page.screenshot({path:`../_deploy/repair-professional-qa/representation-${width}.png`,fullPage:true})
  await page.getByRole('button',{name:'لغو اختیار نماینده آزمایشی '+width,exact:true}).click()
  await page.getByRole('button',{name:'لغو اختیار نماینده آزمایشی '+width,exact:true}).waitFor({state:'hidden'})
  await queue
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  assert.deepEqual(errors,[])
  await page.unrouteAll({behavior:'wait'})
  await page.close()
 }
}finally{await browser.close()}
console.log('Warranty transfer through real API and DB passed at 390 and 1440.')

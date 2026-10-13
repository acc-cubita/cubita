/** Browser -> actual HTTP -> isolated DB, run only by the opt-in pytest fixture. */
import {chromium} from 'playwright'
import assert from 'node:assert/strict'
import {mkdir} from 'node:fs/promises'
const target=new URL(process.env.REPAIR_QA_API_URL)
assert.equal(target.hostname,'127.0.0.1')
const base='http://127.0.0.1:5187'
await mkdir('../_deploy/repair-professional-qa',{recursive:true})
const browser=await chromium.launch({headless:true})
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000}}),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  let queue=Promise.resolve()
  await page.route('**/api/**',route=>{queue=queue.then(async()=>{
   const req=route.request(),url=new URL(req.url())
   if(req.method()==='OPTIONS'){await route.fulfill({status:200,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});return}
   const response=await page.request.fetch(new URL(url.pathname+url.search,target).href,{method:req.method(),headers:{Authorization:'Bearer isolated','Content-Type':'application/json','Idempotency-Key':req.headers()['idempotency-key']??''},data:req.postDataBuffer()??undefined})
   if(response.status()>=400)errors.push(`${req.method()} ${url.pathname}: ${await response.text()}`)
   await route.fulfill({response,headers:{...response.headers(),'Access-Control-Allow-Origin':'*'}})
  });return queue})
  await page.route(base+'/repair-professional-qa',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
   import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
   import React from '/node_modules/.vite/deps/react.js';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';import '/src/index.css';import '/src/App.css';import '/src/pages/repair/repair.css';
   const {RepairConfirmation}=await import('/src/pages/repair/RepairConfirmation.tsx');const {RepairDeviceIdentity}=await import('/src/pages/repair/RepairDeviceIdentity.tsx');const {RepairIntakeEvidence}=await import('/src/pages/repair/RepairIntakeEvidence.tsx');const {RepairPanelActive}=await import('/src/pages/repair/repairPanelActivity.ts');const api=await import('/src/api.ts');
   const me={permissions:{repair:['view','update','approve'],repair_identity:['view','approve']}};
   function App(){const [row,setRow]=React.useState(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState(''),[active,setActive]=React.useState(true);const refresh=async()=>setRow(await api.fetchRepairCase('isolated','${process.env.REPAIR_QA_CASE}'));React.useEffect(()=>{refresh().catch(e=>setError(e.message))},[]);const run=async action=>{setBusy(true);try{await action()}catch(e){setError(e.message)}finally{setBusy(false)}};if(!row)return 'در حال بارگیری';const props={token:'isolated',me,row,busy,run,refresh};return React.createElement('main',{style:{maxWidth:1000,margin:'auto',padding:16}},error&&React.createElement('p',{role:'alert'},error),React.createElement('button',{onClick:()=>setActive(v=>!v)},'تغییر بخش آزمایشی'),React.createElement(RepairPanelActive.Provider,{value:active},React.createElement('div',{hidden:!active},React.createElement(RepairDeviceIdentity,{...props,deviceId:row.device_id}),React.createElement(RepairIntakeEvidence,props),React.createElement(RepairConfirmation,{...props,canOverride:true}))))};ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
  </script>`}))
  await page.goto(base+'/repair-professional-qa')
  await page.getByText('شناسنامه و مالکیت دستگاه',{exact:true}).click()
  await page.getByText('تأییدنشده؛ از پذیرش قبلی حدس زده نمی‌شود',{exact:false}).waitFor()
  await page.getByText('نسخهٔ سخت‌افزار و شناسه‌های فنی',{exact:true}).click()
  await page.getByLabel('نسخهٔ سخت‌افزار',{exact:true}).fill('REV-'+width)
  await page.getByLabel('شمارهٔ برد',{exact:true}).fill('BOARD-'+width)
  await page.getByLabel('دلیل اصلاح مشخصات',{exact:true}).fill('بررسی پلاک فنی دستگاه')
  await page.getByRole('button',{name:'ثبت نسخهٔ مشخصات فنی',exact:true}).click()
  await page.getByText('مشخصات تازه و سابقهٔ اصلاح ثبت شدند.',{exact:true}).waitFor()
  await page.screenshot({path:`../_deploy/repair-professional-qa/device-profile-${width}.png`,fullPage:true})
  await page.getByText('تصاویر، لوازم و آزمون اولیه',{exact:true}).click()
  await page.getByRole('button',{name:'افزودن لوازم',exact:true}).click()
  const accessories=page.getByRole('group',{name:'لوازم همراه'})
  await accessories.getByLabel('عنوان',{exact:true}).last().fill('شارژر مرورگر '+width)
  await accessories.getByLabel('وضعیت',{exact:true}).last().fill('سالم')
  await page.getByRole('button',{name:'تغییر بخش آزمایشی'}).click()
  await page.getByRole('button',{name:'تغییر بخش آزمایشی'}).click()
  assert.equal(await accessories.getByLabel('عنوان',{exact:true}).last().inputValue(),'شارژر مرورگر '+width)
  await page.getByLabel('تصویر',{exact:true}).selectOption(process.env.REPAIR_QA_PHOTO)
  if(await page.getByRole('button',{name:'افزودن تصویر به نسخهٔ پذیرش'}).count())await page.getByRole('button',{name:'افزودن تصویر به نسخهٔ پذیرش'}).click()
  await page.getByLabel('شرح نشانه',{exact:true}).fill('خراش آزمایشی '+width)
  await page.getByLabel('شدت آسیب',{exact:true}).selectOption('severe')
  if(width===390){
   await page.getByLabel('زمان تصویر',{exact:true}).selectOption('delivery')
   await page.getByText('ثبت محل آسیب با صفحه‌کلید',{exact:true}).click()
   await page.getByLabel('فاصله از چپ (درصد)').fill('35')
   await page.getByLabel('فاصله از بالا (درصد)').fill('45')
   await page.getByRole('button',{name:'ثبت نشانه در این محل'}).click()
  }else await page.getByAltText('تصویر اصلی دستگاه برای ثبت محل آسیب').click({position:{x:30,y:30}})
  await page.getByLabel('دلیل ثبت یا اصلاح',{exact:true}).fill('کنترل پذیرش تصویری '+width)
  await page.getByRole('button',{name:'ثبت نسخهٔ جدید پذیرش'}).click()
  await page.waitForFunction(()=>[...document.querySelectorAll('textarea')].some(t=>t.closest('label')?.textContent.includes('دلیل ثبت یا اصلاح')&&t.value===''))
  assert.equal(await page.locator('[role="alert"]').count(),0)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`)
  await page.screenshot({path:`../_deploy/repair-professional-qa/intake-${width}.png`,fullPage:true})
  await page.getByText('تأیید پذیرش با کد پیامکی',{exact:true}).click()
  await page.getByLabel('همراه تأییدکننده',{exact:true}).fill('09123456789')
  await page.getByLabel('مدرک اختیار تأییدکننده',{exact:true}).fill('مدرک مالکیت در آزمون بررسی شد')
  await page.getByText('تأیید جایگزین با امضا و ثبت مسئول',{exact:true}).click()
  await page.getByRole('button',{name:'آماده‌سازی نسخه برای امضا'}).click()
  await page.getByRole('region',{name:'نسخهٔ رسید برای امضا'}).waitFor()
  await page.getByLabel('علت استفاده از روش جایگزین').fill('سرویس واقعی پیامک تنظیم نشده')
  await page.getByLabel('نسبت یا سمت امضاکننده').fill('مالک')
  const signature=page.getByRole('img',{name:'محل رسم امضای تأییدکننده'})
  await signature.scrollIntoViewIfNeeded()
  const box=await signature.boundingBox()
  await page.mouse.move(box.x+20,box.y+20);await page.mouse.down();await page.mouse.move(box.x+80,box.y+45,{steps:5});await page.mouse.up()
  await page.getByRole('button',{name:'ثبت امضای این نسخه',exact:true}).click()
  await page.getByRole('status').filter({hasText:'تأیید روی سند ثبت شد'}).waitFor()
  await page.getByText('تاریخچه و مقایسهٔ تصاویر پذیرش و تحویل',{exact:true}).click()
  await page.getByAltText('نمای ثبت‌شدهٔ نمای عمومی').nth(width===390?1:0).waitFor()
  assert.equal(await page.getByAltText('نمای ثبت‌شدهٔ نمای عمومی').count(),width===390?2:1)
  assert.equal(await page.locator('[role="alert"]').count(),0)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`confirmation overflow at ${width}`)
  await page.screenshot({path:`../_deploy/repair-professional-qa/confirmation-${width}.png`,fullPage:true})

  await queue
  assert.deepEqual(errors,[])
  await page.close()
 }
}finally{await browser.close()}
console.log('Real API/DB identity and evidence browser flow passed at 1440 and 390.')

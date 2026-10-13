import assert from 'node:assert/strict'
import {chromium} from 'playwright'
const roles=JSON.parse(process.env.REPAIR_QA_ROLES),base='http://127.0.0.1:5187',target=process.env.REPAIR_QA_API_URL
const browser=await chromium.launch({headless:true})
try{
 for(const role of roles) for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:950}}),errors=[]
  let queue=Promise.resolve()
  page.on('pageerror',e=>errors.push(e.message))
  await page.route('**/api/**',route=>{queue=queue.then(async()=>{
   const req=route.request(),url=new URL(req.url())
   const response=await page.request.fetch(new URL(url.pathname+url.search,target).href,{method:req.method(),headers:{Authorization:'Bearer '+role.key,'Content-Type':'application/json'},data:req.postDataBuffer()??undefined})
   if(response.status()>=400)errors.push(req.method()+' '+url.pathname+' '+response.status())
   await route.fulfill({response})
  });return queue})
  await page.route(base+'/repair-role-qa',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><div id="root"></div><script type="module">
  import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
  import React from '/node_modules/.vite/deps/react.js';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';import '/src/index.css';import '/src/App.css';import '/src/pages/repair/repair.css';
  const {RepairDeviceIdentity}=await import('/src/pages/repair/RepairDeviceIdentity.tsx');const {RepairTechnicalSummary}=await import('/src/pages/repair/RepairTechnicalSummary.tsx');const api=await import('/src/api.ts');
  function App(){const [row,setRow]=React.useState(null),[error,setError]=React.useState('');const refresh=async()=>setRow(await api.fetchRepairCase('${role.key}','${process.env.REPAIR_QA_CASE}'));React.useEffect(()=>{refresh().catch(e=>setError(e.message))},[]);const props={token:'${role.key}',me:${JSON.stringify({permissions:role.permissions})},row,busy:false,run:async action=>{try{await action()}catch(e){setError(e.message)}},refresh};return React.createElement('main',{style:{padding:16,maxWidth:1000,margin:'auto'}},error&&React.createElement('p',{role:'alert'},error),row&&React.createElement(React.Fragment,null,React.createElement(RepairDeviceIdentity,{...props,deviceId:row.device_id}),React.createElement(RepairTechnicalSummary,props)))}
  ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));</script>`}))
  await page.goto(base+'/repair-role-qa')
  await page.getByText('شناسنامه و مالکیت دستگاه',{exact:true}).click()
  await page.getByRole('button',{name:'چاپ برچسب ثابت دستگاه',exact:true}).waitFor()
  await page.getByText('خلاصهٔ فنی قابل انتقال',{exact:true}).click()
  await page.getByRole('button',{name:'نمایش خلاصه‌های مجاز این مشتری',exact:true}).click()
  await page.getByText('خلاصهٔ مصوبی برای مالک این پرونده در دسترس نیست.',{exact:true}).waitFor()
  const manager=role.key==='manager'
  assert.equal(await page.getByRole('button',{name:'ثبت تصمیم مالکیت',exact:true}).count(),manager?1:0)
  assert.equal(await page.getByRole('button',{name:'آماده‌سازی خلاصه برای مالک فعلی',exact:true}).count(),manager?1:0)
  assert.equal(await page.getByRole('alert').count(),0)
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  assert.deepEqual(errors,[])
  await page.screenshot({path:'../_deploy/repair-professional-qa/role-'+role.key+'-'+width+'.png',fullPage:true})
  await page.unrouteAll({behavior:'wait'});await page.close()
 }
 console.log('4 actual server principals, 2 widths: permitted reads and hidden management passed')
}finally{await browser.close()}

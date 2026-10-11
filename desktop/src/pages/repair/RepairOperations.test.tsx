// @vitest-environment jsdom
import {act} from 'react'
import {createRoot} from 'react-dom/client'
import {expect,it,vi} from 'vitest'
import {RepairOperations} from './RepairOperations'
import type {MeResponse,RepairCase} from '../../api'
const purchases=vi.hoisted(()=>vi.fn())
vi.mock('../../api',async original=>({...await original<typeof import('../../api')>(),can:()=>true,fetchRepairCatalog:async()=>[],fetchRepairTechnicians:async()=>[],fetchContacts:async()=>[],fetchRepairServiceProfiles:async()=>[],fetchPurchaseInvoices:purchases}))
it('keeps service-purchase linking for an outsourced repair while deferring unused purchase data',async()=>{
 (globalThis as Record<string,unknown>).IS_REACT_ACT_ENVIRONMENT=true
 purchases.mockResolvedValue([{id:'purchase',number:1,kind:'service',contact_id:'supplier',voided_at:null}])
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host)
 const row={id:'case',branch_id:'branch',version:1,status:'repairing',owner_snapshot:{name:'مالک'},device_snapshot:{type_id:'type'},outsources:[]} as unknown as RepairCase
 const props={token:'fixture',me:{permissions:{}} as unknown as MeResponse,row,types:[],busy:false,run:async()=>{},refresh:async()=>{},refreshTypes:async()=>{}}
 try{
  await act(async()=>root.render(<RepairOperations {...props}/>));expect(purchases).not.toHaveBeenCalled()
  const outsourced={...row,outsources:[{id:'outsource',vendor_id:'supplier',description:'کار پیمانکار',due_date:'2026-10-07',expected_cost:'0',returned_at:null}]} as unknown as RepairCase
  await act(async()=>root.render(<RepairOperations {...props} row={outsourced}/>))
  expect(purchases).toHaveBeenCalledOnce();expect(host.querySelector('option[value="purchase"]')?.textContent).toContain('خرید')
 }finally{act(()=>root.unmount());host.remove()}
})

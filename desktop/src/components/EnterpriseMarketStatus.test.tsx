// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { EnterpriseMarketStatus } from './EnterpriseMarketStatus'
import * as api from '../api'

vi.mock('../api', () => ({ fetchEnterpriseMarketSyncStatus: vi.fn(), fetchEnterpriseMarketPostingErrors: vi.fn(), fetchItemsLive: vi.fn(), retryEnterpriseMarketPosting: vi.fn(), repairEnterpriseMarketPostingMapping: vi.fn(), approveEnterpriseMarketQuantity:vi.fn(), fetchItemUnits:vi.fn() }))
vi.mock('./TransactionUnitPicker',()=>({TransactionUnitPicker:({onChange}:{onChange:(patch:unknown)=>void})=>createElement('button',{
  onClick:()=>onChange({unitId:'kg',baseQtyPreview:'150',observations:[{rule_id:'measured',from_qty:'36',to_qty:'150'}]})
},'اندازه‌گیری واقعی')}))
let container: HTMLDivElement
let root: Root
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  vi.clearAllMocks()
  vi.mocked(api.fetchEnterpriseMarketSyncStatus).mockResolvedValue({ last_sync_at: '2026-10-01T10:00:00Z', offline: true, access_denied: false })
  vi.mocked(api.fetchEnterpriseMarketPostingErrors).mockResolvedValue([
    {event_id:'buy',order_number:17,side:'buyer',kind:'order',status:'blocked',attempts:2,error_code:'local_posting_failed',error_detail:'دورهٔ مالی بسته است',lines:[]},
    {event_id:'sell',order_number:18,side:'seller',kind:'order',status:'blocked',attempts:1,error_code:'local_posting_failed',error_detail:'خطای سمت فروش',lines:[]},
  ])
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove() })
it('shows offline timestamp and only the current side, then retries the original event', async () => {
  await act(async () => root.render(createElement(EnterpriseMarketStatus, {token:'test',side:'buyer'})))
  expect(container.textContent).toContain('فقط برای مشاهده')
  expect(container.textContent).toContain('۱۴۰۵/۰۷/۰۹')
  expect(container.textContent).toContain('دورهٔ مالی بسته است')
  expect(container.textContent).not.toContain('خطای سمت فروش')
  const retry = [...container.querySelectorAll('button')].find(button => button.textContent?.includes('تلاش دوباره'))!
  await act(async () => retry.click())
  expect(api.retryEnterpriseMarketPosting).toHaveBeenCalledWith('test','buy')
})
it('shows rejected credentials and disables financial retry', async () => {
  vi.mocked(api.fetchEnterpriseMarketSyncStatus).mockResolvedValue({last_sync_at:null,offline:true,access_denied:true})
  await act(async () => root.render(createElement(EnterpriseMarketStatus, {token:'test',side:'buyer'})))
  expect(container.textContent).toContain('اعتبار پیوند رد شده')
  const retry = [...container.querySelectorAll('button')].find(button => button.textContent?.includes('تلاش دوباره'))!
  expect(retry.disabled).toBe(true)
})
it('approves decimal-string measurement only through the local event endpoint',async()=>{
  vi.mocked(api.fetchItemUnits).mockResolvedValue([])
  vi.mocked(api.fetchEnterpriseMarketPostingErrors).mockResolvedValue([{event_id:'measured-event',order_number:1,
    side:'buyer',kind:'order',status:'blocked',attempts:1,error_code:'local_posting_failed',error_detail:'نسبت واقعی لازم است',
    lines:[{market_item_ref:'public-ref',name:'پارچه',unit:'کیلوگرم',qty:'36',local_item_id:'private-item'}]}])
  await act(async()=>root.render(createElement(EnterpriseMarketStatus,{token:'test',side:'buyer'})))
  expect(container.textContent).toContain('۳۶ کیلوگرم')
  const approve=()=>[...container.querySelectorAll('button')].find(button=>button.textContent?.includes('تأیید مقدار'))!
  expect(approve().disabled).toBe(true)
  await act(async()=>[...container.querySelectorAll('button')].find(button=>button.textContent==='اندازه‌گیری واقعی')!.click())
  expect(approve().disabled).toBe(false)
  await act(async()=>approve().click())
  expect(api.approveEnterpriseMarketQuantity).toHaveBeenCalledWith('test','measured-event',{
    line_index:0,unit_id:'kg',observations:[{rule_id:'measured',from_qty:'36',to_qty:'150'}]})
  vi.mocked(api.fetchEnterpriseMarketSyncStatus).mockResolvedValue({last_sync_at:null,offline:true,access_denied:true})
  const refresh=[...container.querySelectorAll('button')].find(button=>button.textContent?.includes('تازه‌سازی وضعیت'))!
  await act(async()=>refresh.click())
  expect(approve().disabled).toBe(true)
})

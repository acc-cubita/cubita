// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { EnterpriseMarketStatus } from './EnterpriseMarketStatus'
import * as api from '../api'

vi.mock('../api', () => ({ fetchEnterpriseMarketSyncStatus: vi.fn(), fetchEnterpriseMarketPostingErrors: vi.fn(), fetchItemsLive: vi.fn(), retryEnterpriseMarketPosting: vi.fn(), repairEnterpriseMarketPostingMapping: vi.fn() }))
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

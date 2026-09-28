import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const origin = process.env.NETWORK_TEST_ORIGIN ?? 'http://127.0.0.1:5520'
const output = path.resolve('../_deploy/enterprise-network-qa')
fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
try {
  for (const [width, theme] of [[1440, 'light'], [1440, 'dark'], [1200, 'light'], [390, 'light']]) {
    const context = await browser.newContext({ viewport: { width, height: 950 } })
    await context.addInitScript(() => {
      window.cubitaConfig = { edition: 'enterprise', serverUrl: null, version: '1.9.5' }
      const inventory = { role: 'server', state: { enabled: false, message: 'نگهداری خودکار شبکه هنوز فعال نشده است.' },
        adapters: [
          { id: 'lan', name: 'Ethernet 12', description: 'Realtek PCIe GbE Family Controller', index: 55, physical: true, kind: 'wired', status: 'Up', dhcp: false, addresses: [{ address: '192.168.91.1', prefix: 24 }], gateways: [], defaultRoute: false, profile: 'Public' },
          { id: 'wifi', name: 'Wireless Network', description: 'Wi-Fi adapter', index: 61, physical: true, kind: 'wifi', status: 'Up', dhcp: true, addresses: [{ address: '10.5.6.20', prefix: 24 }], gateways: ['10.5.6.1'], defaultRoute: true, profile: 'Public' },
        ], suggestions: { lan: { address: '192.168.91.1', prefix: 24, mode: 'keep' }, wifi: { address: '10.5.6.20', prefix: 24, mode: 'keep' } } }
      window.__networkQA = { applies: 0, inventory }
      window.cubita = {
        networkInspect: async () => ({ ok: true, data: inventory }),
        networkPreview: async config => ({ ok: true, data: { config, adapterName: inventory.adapters.find(a => a.id === config.adapterId).name, subnet: config.adapterId === 'lan' ? '192.168.91.0/24' : '10.5.6.0/24', serverUrl: `http://${config.address}:${config.port}`, addAddress: config.mode === 'static', warnings: ['DNS، gateway، مسیر اینترنت و VPN دست‌نخورده می‌مانند.'] } }),
        networkApply: async config => {
          window.__networkQA.applies++
          inventory.state = { enabled: true, config, serverUrl: `http://${config.address}:${config.port}`, message: 'شبکه آماده است؛ اینترنت دست‌نخورده است.' }
          return { ok: true, data: inventory.state }
        },
        networkDisable: async () => ({ ok: true, data: { enabled: false, message: 'غیرفعال شد' } }),
      }
    })
    await context.route('**/api/**', route => route.abort())
    const page = await context.newPage(), errors = []
    page.on('pageerror', e => errors.push(e.message))
    page.on('console', e => { if (e.type() === 'error') errors.push(e.text()) })
    await page.goto(`${origin}/tests/fixtures/enterprise-network.html?theme=${theme}`)
    await page.getByLabel('نوع ارتباط شبکه', { exact: true }).selectOption('direct')
    await page.getByLabel('کارت شبکه', { exact: true }).selectOption('lan')
    await page.getByLabel('تنظیم دستی', { exact: false }).check()
    await page.getByLabel('پورت سرور', { exact: true }).fill('8420')
    await page.getByRole('button', { name: 'بررسی تغییرات، بدون اعمال', exact: true }).click()
    const apply = page.getByRole('button', { name: 'اعمال با تأیید مدیر ویندوز', exact: true })
    assert.equal(await apply.isEnabled(), false)
    await page.getByLabel('این کارت و محدوده', { exact: false }).check()
    async function metrics(state) {
      const m = await page.evaluate(() => ({ overflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), tables: document.querySelectorAll('table:not(.cards-on-mobile):not(.table-plain)').length, cells: document.querySelectorAll('table.cards-on-mobile td:not([data-label]):not(.card-title):not(.card-actions):not(.card-wide):not(.card-full):not(.card-hide)').length }))
      assert.deepEqual(m, { overflow: 0, tables: 0, cells: 0 }); assert.deepEqual(errors, [])
      console.log(`network ${width} ${theme} ${state}: overflow=0 console=0 tables=0 cells=0`)
      await page.screenshot({ path: path.join(output, `${width}-${theme}-${state}.png`), fullPage: true })
    }
    await metrics('preview')
    await apply.click(); await page.getByText('نشانی اتصالِ کلاینت:', { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => window.__networkQA.applies), 1)
    await metrics('applied')
    await page.getByLabel('نوع ارتباط شبکه', { exact: true }).selectOption('wifi-router')
    await page.getByLabel('کارت شبکه', { exact: true }).selectOption('wifi')
    assert.equal(await page.getByLabel('روش تنظیم IP').locator('option[value=static]').count(), 0)
    assert.equal(await page.getByLabel('IP فعلی کارت').inputValue(), '10.5.6.20')
    await metrics('wifi')
    await page.goto(`${origin}/tests/fixtures/enterprise-network.html?theme=${theme}&connect`)
    await page.getByText('تنظیم شبکهٔ این رایانه (خودکار / دستی)', { exact: true }).click()
    await page.getByLabel('نوع ارتباط شبکه').selectOption('direct')
    await page.getByLabel('کارت شبکه', { exact: true }).selectOption('lan')
    await metrics('first-connect')
    await context.close()
  }
} finally { await browser.close() }

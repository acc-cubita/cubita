#!/usr/bin/env node
/** Chromium render probe for the 300-line accountant grid. Requires WEB_ONLY=1 vite. */
import { chromium } from 'playwright'

const url = process.argv[2] ?? 'http://127.0.0.1:5173/'
const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(url)
  const result = await page.evaluate(async () => {
    const React = (await import('/node_modules/.vite/deps/react.js')).default
    const ReactDOM = (await import('/node_modules/.vite/deps/react-dom_client.js')).default
    const { flushSync } = (await import('/node_modules/.vite/deps/react-dom.js')).default
    const { JournalGrid } = await import('/src/components/JournalGrid.tsx')
    const lines = Array.from({ length: 300 }, (_, index) => ({
      accountId: index % 2 ? 'sales' : 'cash',
      debit: index % 2 ? '' : '1000',
      credit: index % 2 ? '1000' : '',
      description: '',
    }))
    const stable = {
      currencyCode: '', costCenterId: '', analyticId: '', tafsiliMode: 'floating',
      tafsiliRequired: new Set(), trackingAllowed: new Set(), costCenters: [], analytics: [],
      postableAccounts: [
        { id: 'cash', code: '101', name: 'نقد' },
        { id: 'sales', code: '401', name: 'فروش' },
      ],
      remaining: null, submitting: false,
      setLineFx() {}, addLine() {}, removeLine() {}, duplicateLine() {},
      copyPreviousInto() {}, applyRemaining() {}, submit() {},
    }
    const mounts = []
    for (let run = 0; run < 5; run++) {
      const host = document.createElement('div')
      document.body.appendChild(host)
      const root = ReactDOM.createRoot(host)
      const start = performance.now()
      flushSync(() => root.render(React.createElement(JournalGrid, {
        d: { ...stable, lines, updateLine() {} },
      })))
      mounts.push(performance.now() - start)
      flushSync(() => root.unmount())
      host.remove()
    }

    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = ReactDOM.createRoot(host)
    let current = lines
    const updates = []
    function updateLine(index, patch) {
      current = current.map((line, at) => at === index ? { ...line, ...patch } : line)
      const start = performance.now()
      flushSync(() => root.render(React.createElement(JournalGrid, {
        d: { ...stable, lines: current, updateLine },
      })))
      updates.push(performance.now() - start)
    }
    flushSync(() => root.render(React.createElement(JournalGrid, {
      d: { ...stable, lines: current, updateLine },
    })))
    const cell = host.querySelector('[data-cell="149-3"] input')
    if (!cell) throw new Error('ردیف ۱۵۰ در گرید پیدا نشد')
    cell.focus()
    for (const key of '1234567890') {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
      setter.call(cell, cell.value + key)
      cell.dispatchEvent(new Event('input', { bubbles: true }))
    }
    const finalCredit = current[149].credit
    const finalDomValue = cell.value
    if (updates.length !== 10 || finalCredit !== '10001234567890') {
      throw new Error(`Input did not update all 10 times: ${updates.length}, ${finalCredit}, ${finalDomValue}`)
    }
    flushSync(() => root.unmount())
    host.remove()
    const median = (values) => values.slice().sort((a, b) => a - b)[Math.floor(values.length / 2)]
    return { mountMedianMs: median(mounts), mountSamplesMs: mounts, updateMedianMs: median(updates), updateSamplesMs: updates, finalCredit }
  })
  console.log(JSON.stringify({ url, ...result }))
} finally {
  await browser.close()
}

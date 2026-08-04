/*
 * کلاینتِ API فروشگاه — فقط سطحِ عمومیِ /api/shop/*.
 * هویت با هدرهای X-Shop-Slug + X-Shop-Key (از config.js).
 */
(function () {
  const cfg = window.SHOP || {}
  const base = (cfg.apiBase || '').replace(/\/$/, '')

  // ── حالتِ دمو ─────────────────────────────────────────────────────────────
  // برای نمایشِ زنده‌ی قالب روی VPS بدونِ هیچ بک‌اند: config.js مقدارِ demo:true و
  // داده‌ی نمونه (window.SHOP_DEMO) می‌گذارد و همه‌چیز از حافظه سِرو می‌شود.
  if (cfg.demo && window.SHOP_DEMO) {
    const D = window.SHOP_DEMO
    const find = (slug) => (D.catalog || []).find((p) => p.slug === slug)
    const wait = (v) => new Promise((res) => setTimeout(() => res(v), 120))
    window.ShopApi = {
      info: () => wait(D.info || {}),
      catalog: () => wait(D.catalog || []),
      categories: () => wait(D.categories || []),
      product: (slug) => (find(slug) ? wait(find(slug)) : Promise.reject(new Error('یافت نشد'))),
      placeOrder: (order) =>
        wait({ id: 'demo', order_number: Math.floor(Math.random() * 900 + 100), tracking_code: 'DEMO' + Date.now().toString(36).toUpperCase(), total: (order.lines || []).reduce((s, l) => s + (find(l.slug) ? find(l.slug).price * l.qty : 0), 0), payment_status: 'pending' }),
      pay: () => Promise.reject(new Error('دمو')),
      ShopError: Error,
    }
    return
  }

  function headers() {
    return { 'X-Shop-Slug': cfg.slug || '', 'X-Shop-Key': cfg.key || '' }
  }

  async function get(path) {
    const res = await fetch(base + path, { headers: headers() })
    if (!res.ok) throw new ShopError(await detail(res), res.status)
    return res.json()
  }

  async function post(path, body) {
    const res = await fetch(base + path, {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, headers()),
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new ShopError(await detail(res), res.status)
    return res.json()
  }

  async function detail(res) {
    try {
      const b = await res.json()
      return b.detail || 'خطایی رخ داد'
    } catch (e) {
      return 'خطا در ارتباط با سرور'
    }
  }

  class ShopError extends Error {
    constructor(message, status) {
      super(message)
      this.status = status
    }
  }

  window.ShopApi = {
    info: () => get('/api/shop/info'),
    catalog: () => get('/api/shop/catalog'),
    categories: () => get('/api/shop/categories'),
    product: (slug) => get('/api/shop/product/' + encodeURIComponent(slug)),
    placeOrder: (order) => post('/api/shop/orders', order),
    pay: (orderId) => post('/api/shop/orders/' + encodeURIComponent(orderId) + '/pay', {}),
    ShopError,
  }
})()

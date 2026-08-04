/*
 * کلاینتِ API فروشگاه — فقط سطحِ عمومیِ /api/shop/*.
 * هویت با هدرهای X-Shop-Slug + X-Shop-Key (از config.js).
 */
(function () {
  const cfg = window.SHOP || {}
  const base = (cfg.apiBase || '').replace(/\/$/, '')

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
    ShopError,
  }
})()

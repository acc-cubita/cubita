/*
 * اپِ فروشگاه — وانیلا، بدونِ بیلد، قابلِ آپلود روی هر هاست. داده از /api/shop/*.
 * قالبِ «عمومی» و بی‌نام‌ونشان؛ برند/رنگ/نام از تنظیماتِ همان کسب‌وکار می‌آید.
 */
(function () {
  const api = window.ShopApi
  const cfg = window.SHOP || {}
  const app = document.getElementById('app')

  let INFO = null
  let CATALOG = []

  // ── سبد (localStorage، مختصِ همین فروشگاه) ──────────────────────────────
  const CART_KEY = 'cubita_cart_' + (cfg.slug || 'shop')
  const loadCart = () => { try { return JSON.parse(localStorage.getItem(CART_KEY)) || [] } catch (e) { return [] } }
  const saveCart = (c) => { localStorage.setItem(CART_KEY, JSON.stringify(c)); updateBadge() }
  const cartCount = () => loadCart().reduce((s, i) => s + i.qty, 0)
  const cartTotal = () => loadCart().reduce((s, i) => s + i.qty * i.price, 0)

  function updateBadge() {
    const b = document.getElementById('cart-badge')
    const n = cartCount()
    if (n > 0) { b.hidden = false; b.textContent = fa(n) } else { b.hidden = true }
  }

  // ── کمک‌ها ──────────────────────────────────────────────────────────────
  const fa = (n) => Number(n || 0).toLocaleString('fa-IR')
  // توجه: قیمت‌ها از حسابداری می‌آیند؛ واحدِ نمایش («تومان») باید با کسب‌وکار تأیید شود.
  const money = (n) => fa(n) + ' تومان'
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
  const img0 = (p) => (p.images && p.images[0]) || ''

  function errorBox(e) {
    const msg = (e && e.message) || 'خطا'
    const hint = e && e.status === 401
      ? 'کلید یا شناسه‌ی فروشگاه درست تنظیم نشده است (assets/config.js).'
      : e && e.status === 403
      ? 'این فروشگاه هنوز منتشر نشده است.'
      : ''
    return `<div class="empty"><h2>فروشگاه در دسترس نیست</h2><p class="muted">${esc(msg)}</p>${hint ? `<p class="muted">${hint}</p>` : ''}</div>`
  }

  function toast(text) {
    const t = document.createElement('div')
    t.className = 'toast'
    t.textContent = text
    document.body.appendChild(t)
    setTimeout(() => t.classList.add('show'), 10)
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300) }, 1800)
  }

  // ── برند ────────────────────────────────────────────────────────────────
  function applyBrand(info) {
    const brand = (info.theme_config && info.theme_config.brand_name) || info.seo_title || 'فروشگاه'
    document.title = brand
    document.documentElement.style.setProperty('--brand', (info.theme_config && info.theme_config.primary) || '#E31F24')
    document.getElementById('brand-name').textContent = brand
    document.getElementById('brand-logo').textContent = (brand.trim()[0] || 'ف')
    document.getElementById('footer-name').textContent = brand
    if (info.seo_description) { const m = document.querySelector('meta[name=description]'); if (m) m.content = info.seo_description }
    const phone = info.contact_block && info.contact_block.phone
    if (phone) document.getElementById('footer-phone').textContent = 'تماس: ' + phone
  }

  function categoriesOf(list) {
    const set = []
    list.forEach((p) => { if (p.category && set.indexOf(p.category) < 0) set.push(p.category) })
    return set
  }

  function renderNav() {
    const cats = categoriesOf(CATALOG)
    const cur = new URLSearchParams((location.hash.split('?')[1] || '')).get('cat') || ''
    const chip = (label, cat) => `<a class="nav-chip${cat === cur ? ' active' : ''}" href="#/${cat ? '?cat=' + encodeURIComponent(cat) : ''}">${esc(label)}</a>`
    document.getElementById('nav-inner').innerHTML = chip('همه', '') + cats.map((c) => chip(c, c)).join('')
  }

  // ── کارتِ محصول ───────────────────────────────────────────────────────────
  function card(p) {
    const im = img0(p)
    return `<a class="card" href="#/product/${encodeURIComponent(p.slug)}">
      <div class="card-img">${im ? `<img src="${esc(im)}" alt="${esc(p.title)}" loading="lazy">` : `<span class="noimg">${esc((p.title || '؟')[0])}</span>`}</div>
      <div class="card-body">
        ${p.badge ? `<span class="badge">${esc(p.badge)}</span>` : ''}
        <h3>${esc(p.title)}</h3>
        <div class="card-foot"><span class="price">${p.out_of_stock ? '<span class="oos">ناموجود</span>' : money(p.price)}</span></div>
      </div>
    </a>`
  }

  // ── صفحه‌ها ────────────────────────────────────────────────────────────────
  async function renderHome(query) {
    app.innerHTML = '<div class="skeleton">در حال بارگذاری…</div>'
    try { if (!CATALOG.length) CATALOG = await api.catalog() } catch (e) { app.innerHTML = errorBox(e); return }
    renderNav()
    const cat = query.get('cat') || ''
    const q = (query.get('q') || '').trim()
    let items = CATALOG
    if (cat) items = items.filter((p) => p.category === cat)
    if (q) items = items.filter((p) => p.title.includes(q))
    const grid = items.length ? `<div class="grid">${items.map(card).join('')}</div>` : '<div class="empty">کالایی یافت نشد.</div>'
    app.innerHTML = `
      <section class="hero"><h1>${esc(INFO.seo_title || 'فروشگاه')}</h1>${INFO.seo_description ? `<p class="muted">${esc(INFO.seo_description)}</p>` : ''}</section>
      ${q ? `<p class="result-note">نتایجِ «${esc(q)}» (${fa(items.length)})</p>` : ''}
      ${grid}`
  }

  async function renderProduct(slug) {
    app.innerHTML = '<div class="skeleton">در حال بارگذاری…</div>'
    let p
    try { p = await api.product(slug) } catch (e) { app.innerHTML = errorBox(e); return }
    renderNav()
    const im = img0(p)
    app.innerHTML = `
      <nav class="crumbs"><a href="#/">خانه</a> <span>/</span> ${esc(p.title)}</nav>
      <div class="product">
        <div class="product-media">${im ? `<img src="${esc(im)}" alt="${esc(p.title)}">` : `<span class="noimg big">${esc((p.title || '؟')[0])}</span>`}</div>
        <div class="product-info">
          ${p.badge ? `<span class="badge">${esc(p.badge)}</span>` : ''}
          <h1>${esc(p.title)}</h1>
          <div class="price big">${p.out_of_stock ? '<span class="oos">ناموجود</span>' : money(p.price)}</div>
          ${p.description ? `<p class="desc">${esc(p.description)}</p>` : ''}
          ${p.out_of_stock ? '<p class="muted">این کالا فعلاً موجود نیست.</p>' : `
            <div class="buy">
              <div class="qty"><button data-q="-" aria-label="کمتر">−</button><span id="q">۱</span><button data-q="+" aria-label="بیشتر">+</button></div>
              <button class="btn-primary" id="add">افزودن به سبد</button>
            </div>`}
        </div>
      </div>`
    if (!p.out_of_stock) {
      let qty = 1
      const qEl = document.getElementById('q')
      app.querySelectorAll('[data-q]').forEach((b) => (b.onclick = () => {
        qty = Math.max(1, qty + (b.dataset.q === '+' ? 1 : -1))
        if (p.stock) qty = Math.min(qty, p.stock)
        qEl.textContent = fa(qty)
      }))
      document.getElementById('add').onclick = () => { addToCart(p, qty); toast('به سبد اضافه شد') }
    }
  }

  function addToCart(p, qty) {
    const cart = loadCart()
    const found = cart.find((i) => i.slug === p.slug)
    if (found) found.qty += qty
    else cart.push({ slug: p.slug, title: p.title, price: p.price, image: img0(p), qty })
    saveCart(cart)
  }

  function renderCart() {
    renderNav()
    const cart = loadCart()
    if (!cart.length) { app.innerHTML = '<div class="empty"><h2>سبد خالی است</h2><a class="btn-primary" href="#/">بازگشت به فروشگاه</a></div>'; return }
    app.innerHTML = `
      <h1 class="page-title">سبد خرید</h1>
      <div class="cart">
        <div class="cart-list">
          ${cart.map((i) => `
            <div class="cart-row" data-slug="${esc(i.slug)}">
              <div class="cart-thumb">${i.image ? `<img src="${esc(i.image)}" alt="">` : `<span class="noimg">${esc((i.title || '؟')[0])}</span>`}</div>
              <div class="cart-main"><a href="#/product/${encodeURIComponent(i.slug)}">${esc(i.title)}</a><div class="muted">${money(i.price)}</div></div>
              <div class="qty small"><button data-a="-">−</button><span>${fa(i.qty)}</span><button data-a="+">+</button></div>
              <div class="cart-line">${money(i.price * i.qty)}</div>
              <button class="cart-del" data-del aria-label="حذف">×</button>
            </div>`).join('')}
        </div>
        <aside class="cart-summary">
          <div class="row"><span>جمع کل</span><strong>${money(cartTotal())}</strong></div>
          <a class="btn-primary block" href="#/checkout">ادامه‌ی خرید</a>
        </aside>
      </div>`
    app.querySelectorAll('.cart-row').forEach((row) => {
      const slug = row.dataset.slug
      row.querySelectorAll('[data-a]').forEach((b) => (b.onclick = () => changeQty(slug, b.dataset.a === '+' ? 1 : -1)))
      row.querySelector('[data-del]').onclick = () => removeItem(slug)
    })
  }

  function changeQty(slug, d) {
    const cart = loadCart()
    const it = cart.find((i) => i.slug === slug)
    if (!it) return
    it.qty = Math.max(1, it.qty + d)
    saveCart(cart)
    renderCart()
  }
  function removeItem(slug) { saveCart(loadCart().filter((i) => i.slug !== slug)); renderCart() }

  function renderCheckout() {
    renderNav()
    const cart = loadCart()
    if (!cart.length) { location.hash = '#/'; return }
    app.innerHTML = `
      <h1 class="page-title">تسویه‌ی حساب</h1>
      <div class="checkout">
        <form id="checkout-form" class="checkout-form">
          <label>نام و نام خانوادگی <input name="customer_name" required></label>
          <label>شماره‌ی تماس <input name="customer_phone" dir="ltr" required placeholder="0912…"></label>
          <label>ایمیل (اختیاری) <input name="customer_email" dir="ltr" type="email"></label>
          <label>نشانیِ ارسال <textarea name="shipping_address" rows="3" required></textarea></label>
          <label>توضیح (اختیاری) <textarea name="note" rows="2"></textarea></label>
          <button type="submit" class="btn-primary block" id="place">ثبتِ سفارش</button>
          <p class="err" id="checkout-err" hidden></p>
        </form>
        <aside class="cart-summary">
          <h3>سفارشِ شما</h3>
          ${cart.map((i) => `<div class="row small"><span>${esc(i.title)} × ${fa(i.qty)}</span><span>${money(i.price * i.qty)}</span></div>`).join('')}
          <div class="row total"><span>جمع کل</span><strong>${money(cartTotal())}</strong></div>
        </aside>
      </div>`
    document.getElementById('checkout-form').onsubmit = async (ev) => {
      ev.preventDefault()
      const fd = new FormData(ev.target)
      const btn = document.getElementById('place')
      const err = document.getElementById('checkout-err')
      err.hidden = true
      btn.disabled = true; btn.textContent = 'در حال ثبت…'
      try {
        const order = await api.placeOrder({
          customer_name: fd.get('customer_name'),
          customer_phone: fd.get('customer_phone'),
          customer_email: fd.get('customer_email') || '',
          shipping_address: fd.get('shipping_address'),
          note: fd.get('note') || '',
          lines: cart.map((i) => ({ slug: i.slug, qty: i.qty })),
        })
        if (INFO.has_online_payment) {
          try {
            const r = await api.pay(order.id)
            saveCart([])
            window.location.href = r.redirect_url
            return
          } catch (e2) {
            // سفارش ثبت شد ولی شروعِ پرداختِ آنلاین نشد؛ به‌عنوان سفارشِ در انتظار نمایش بده
            saveCart([])
            renderOrderPlaced(order)
            return
          }
        }
        saveCart([])
        renderOrderPlaced(order)
      } catch (e) {
        err.hidden = false
        err.textContent = (e && e.message) || 'ثبتِ سفارش ناموفق بود'
        btn.disabled = false; btn.textContent = 'ثبتِ سفارش'
      }
    }
  }

  function renderOrderPlaced(order) {
    app.innerHTML = `
      <div class="order-done">
        <div class="check">✓</div>
        <h1>سفارش ثبت شد</h1>
        <p>شماره‌ی سفارش: <strong>${fa(order.order_number)}</strong></p>
        <p>کدِ پیگیری: <strong dir="ltr">${esc(order.tracking_code)}</strong></p>
        <p>مبلغِ قابلِ پرداخت: <strong>${money(order.total)}</strong></p>
        <p class="muted">سفارشِ شما در انتظارِ تأیید/پرداخت است. به‌زودی با شما تماس می‌گیریم.</p>
        <a class="btn-primary" href="#/">بازگشت به فروشگاه</a>
      </div>`
  }

  function renderOrderResult(query) {
    renderNav()
    const ok = query.get('status') === 'ok'
    const code = query.get('code') || ''
    app.innerHTML = ok
      ? `<div class="order-done">
          <div class="check">✓</div>
          <h1>پرداخت موفق بود</h1>
          ${code ? `<p>کدِ پیگیری: <strong dir="ltr">${esc(code)}</strong></p>` : ''}
          <p class="muted">سفارشِ شما ثبت و پرداخت شد. سپاس‌گزاریم!</p>
          <a class="btn-primary" href="#/">بازگشت به فروشگاه</a>
        </div>`
      : `<div class="order-done">
          <div class="check fail">×</div>
          <h1>پرداخت ناموفق بود</h1>
          <p class="muted">مبلغی از حسابِ شما کسر نشد. می‌توانید دوباره تلاش کنید.</p>
          <a class="btn-primary" href="#/cart">بازگشت به سبد</a>
        </div>`
  }

  // ── روتر ────────────────────────────────────────────────────────────────
  function route() {
    const h = (location.hash.replace(/^#/, '') || '/')
    const [path, qs] = h.split('?')
    const parts = path.split('/').filter(Boolean)
    const query = new URLSearchParams(qs || '')
    window.scrollTo(0, 0)
    if (parts[0] === 'product' && parts[1]) return renderProduct(decodeURIComponent(parts[1]))
    if (parts[0] === 'cart') return renderCart()
    if (parts[0] === 'checkout') return renderCheckout()
    if (parts[0] === 'order-result') return renderOrderResult(query)
    return renderHome(query)
  }

  async function boot() {
    try { INFO = await api.info(); applyBrand(INFO) } catch (e) { app.innerHTML = errorBox(e); return }
    updateBadge()
    document.getElementById('search-form').onsubmit = (ev) => {
      ev.preventDefault()
      const v = document.getElementById('search-input').value.trim()
      location.hash = v ? '#/?q=' + encodeURIComponent(v) : '#/'
    }
    window.addEventListener('hashchange', route)
    route()
  }

  boot()
})()

"""پیش‌رندرِ سئوِ زمانِ بیلد برای فروشگاهِ استاتیک.

سایت یک SPAی هش‌روت است؛ خزنده‌ها بدونِ اجرای JS فقط `#app`ِ خالی می‌بینند. این ماژول
هنگامِ ساختِ ZIP یک **اسنپ‌شاتِ استاتیک** تولید می‌کند:

- `index.html` غنی می‌شود: متاهای OG/Twitter/canonical + JSON-LD (Store + ItemList) و
  یک بلوکِ پیش‌رندرشده از کالاها داخلِ `#app` که خزنده می‌بیند و پس از بارِ JS با
  محتوای زنده جایگزین می‌شود.
- برای هر کالا یک صفحه‌ی استاتیکِ خزنده‌پذیر `p/<slug>/index.html` با JSON-LDِ Product و
  متای OG ساخته می‌شود (انسان‌ها با یک ری‌دایرکتِ نرم به SPA می‌روند).
- `robots.txt`، `sitemap.xml`، `llms.txt`.

اسنپ‌شات عکسِ لحظه‌ی بیلد است؛ داده‌ی زنده همیشه از API می‌آید. با تغییرِ چشمگیرِ
کاتالوگ، مستأجر دوباره «ساخت سایت» می‌زند.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass, field

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(n) -> str:
    return f"{int(n or 0):,}".translate(_FA_DIGITS)


def _e(s) -> str:
    """escape برای متنِ HTML."""
    return html.escape(str(s or ""))


def _attr(s) -> str:
    """escape برای مقدارِ attribute (کوتیشن هم)."""
    return html.escape(str(s or ""), quote=True)


@dataclass
class SeoProduct:
    slug: str
    title: str
    price: int
    description: str
    image: str
    category: str
    in_stock: bool


@dataclass
class SeoContext:
    slug: str
    brand: str
    seo_title: str
    seo_description: str
    primary: str
    phone: str
    origin: str  # allowed_origin (بدونِ / انتها)؛ ممکن است خالی باشد
    currency: str  # toman | rial
    products: list[SeoProduct] = field(default_factory=list)

    @property
    def base(self) -> str:
        return (self.origin or "").rstrip("/")

    def product_url(self, p: SeoProduct) -> str:
        """URLِ خزنده‌پذیرِ صفحه‌ی استاتیکِ کالا (نسبی اگر origin نداریم)."""
        return f"{self.base}/p/{p.slug}/" if self.base else f"/p/{p.slug}/"

    def spa_url(self, p: SeoProduct) -> str:
        return f"{self.base}/#/product/{p.slug}" if self.base else f"/#/product/{p.slug}"

    def price_irr(self, p: SeoProduct) -> int:
        # priceCurrency در schema.org باید IRR (ریال) باشد؛ تومان×۱۰.
        return p.price if self.currency == "rial" else p.price * 10

    def money(self, p: SeoProduct) -> str:
        unit = "ریال" if self.currency == "rial" else "تومان"
        return f"{_fa(p.price)} {unit}"


def _meta_head(ctx: SeoContext, *, title: str, description: str, url: str, image: str, jsonld: list[dict]) -> str:
    """قطعه‌ی مشترکِ متای OG/Twitter/canonical + JSON-LD برای هر صفحه."""
    parts = [
        f'<meta property="og:site_name" content="{_attr(ctx.brand)}">',
        f'<meta property="og:title" content="{_attr(title)}">',
        f'<meta property="og:description" content="{_attr(description)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:locale" content="fa_IR">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_attr(title)}">',
        f'<meta name="twitter:description" content="{_attr(description)}">',
        f'<meta name="theme-color" content="{_attr(ctx.primary)}">',
    ]
    if url:
        parts.append(f'<link rel="canonical" href="{_attr(url)}">')
        parts.append(f'<meta property="og:url" content="{_attr(url)}">')
    if image:
        parts.append(f'<meta property="og:image" content="{_attr(image)}">')
        parts.append(f'<meta name="twitter:image" content="{_attr(image)}">')
    for block in jsonld:
        parts.append(
            '<script type="application/ld+json">'
            + json.dumps(block, ensure_ascii=False, separators=(",", ":"))
            + "</script>"
        )
    return "\n  ".join(parts)


def _store_jsonld(ctx: SeoContext) -> dict:
    data: dict = {"@context": "https://schema.org", "@type": "Store", "name": ctx.brand}
    if ctx.seo_description:
        data["description"] = ctx.seo_description
    if ctx.base:
        data["url"] = ctx.base + "/"
    if ctx.phone:
        data["telephone"] = ctx.phone
    return data


def _itemlist_jsonld(ctx: SeoContext) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": ctx.product_url(p), "name": p.title}
            for i, p in enumerate(ctx.products)
        ],
    }


def _product_jsonld(ctx: SeoContext, p: SeoProduct) -> dict:
    offer = {
        "@type": "Offer",
        "priceCurrency": "IRR",
        "price": ctx.price_irr(p),
        "availability": "https://schema.org/InStock" if p.in_stock else "https://schema.org/OutOfStock",
    }
    if ctx.base:
        offer["url"] = ctx.product_url(p)
    data: dict = {"@context": "https://schema.org", "@type": "Product", "name": p.title, "offers": offer}
    if p.description:
        data["description"] = p.description
    if p.image:
        data["image"] = [p.image]
    if p.category:
        data["category"] = p.category
    return data


def _breadcrumb_jsonld(ctx: SeoContext, p: SeoProduct) -> dict:
    home = ctx.base + "/" if ctx.base else "/"
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "خانه", "item": home},
            {"@type": "ListItem", "position": 2, "name": p.title, "item": ctx.product_url(p)},
        ],
    }


def _prerender_grid(ctx: SeoContext) -> str:
    """بلوکِ پیش‌رندرِ کالاها برای داخلِ `#app` — خزنده می‌بیند، JS جایگزینش می‌کند."""
    cards = []
    for p in ctx.products:
        img = (
            f'<img src="{_attr(p.image)}" alt="{_attr(p.title)}" loading="lazy" width="300" height="300">'
            if p.image
            else ""
        )
        price = f'<span class="price">{_e(ctx.money(p))}</span>' if p.in_stock else '<span class="oos">ناموجود</span>'
        cards.append(
            f'<a class="card" href="#/product/{_attr(p.slug)}">'
            f'<div class="card-img">{img}</div>'
            f'<div class="card-body"><h3>{_e(p.title)}</h3>'
            f'<div class="card-foot">{price}</div></div></a>'
        )
    heading = f"<h1>{_e(ctx.seo_title or ctx.brand)}</h1>"
    intro = f'<p class="muted">{_e(ctx.seo_description)}</p>' if ctx.seo_description else ""
    grid = f'<div class="grid">{"".join(cards)}</div>' if cards else ""
    return f'<section class="hero">{heading}{intro}</section>{grid}'


def enrich_index(template_html: str, ctx: SeoContext) -> str:
    """متای سئو را به `<head>` و بلوکِ پیش‌رندر را به `#app`ِ index.html تزریق می‌کند."""
    head = _meta_head(
        ctx,
        title=ctx.seo_title or ctx.brand,
        description=ctx.seo_description or ctx.brand,
        url=(ctx.base + "/") if ctx.base else "",
        image=(ctx.products[0].image if ctx.products and ctx.products[0].image else ""),
        jsonld=[_store_jsonld(ctx), _itemlist_jsonld(ctx)],
    )
    out = template_html.replace("</head>", f"  {head}\n</head>", 1)

    prerender = _prerender_grid(ctx)
    marker = '<main id="app" class="container">'
    idx = out.find(marker)
    if idx >= 0:
        start = idx + len(marker)
        end = out.find("</main>", start)
        if end >= 0:
            out = out[:start] + prerender + out[end:]
    return out


def _product_page(ctx: SeoContext, p: SeoProduct) -> str:
    head = _meta_head(
        ctx,
        title=f"{p.title} | {ctx.brand}",
        description=p.description or p.title,
        url=ctx.product_url(p) if ctx.base else "",
        image=p.image,
        jsonld=[_product_jsonld(ctx, p), _breadcrumb_jsonld(ctx, p)],
    )
    img = f'<img src="{_attr(p.image)}" alt="{_attr(p.title)}" width="420" height="420">' if p.image else ""
    price = _e(ctx.money(p)) if p.in_stock else "ناموجود"
    desc = f'<p style="white-space:pre-line">{_e(p.description)}</p>' if p.description else ""
    spa = _attr(ctx.spa_url(p))
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(p.title)} | {_e(ctx.brand)}</title>
  <meta name="description" content="{_attr(p.description or p.title)}">
  {head}
  <style>body{{font-family:Vazirmatn,Tahoma,sans-serif;max-width:760px;margin:0 auto;padding:24px;color:#1c2333}}
  img{{max-width:100%;height:auto;border-radius:12px}}.price{{color:{_attr(ctx.primary)};font-weight:800;font-size:20px}}
  a.btn{{display:inline-block;background:{_attr(ctx.primary)};color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:700;margin-top:14px}}</style>
</head>
<body>
  <nav><a href="{('/' if not ctx.base else ctx.base + '/')}">خانه</a> / {_e(p.title)}</nav>
  <main>
    <h1>{_e(p.title)}</h1>
    {img}
    <p class="price">{price}</p>
    {desc}
    <a class="btn" href="{spa}">مشاهده و خرید در فروشگاه</a>
  </main>
  <script>window.location.replace({json.dumps(ctx.spa_url(p))})</script>
</body>
</html>
"""


def _robots(ctx: SeoContext) -> str:
    lines = ["User-agent: *", "Allow: /"]
    if ctx.base:
        lines.append(f"Sitemap: {ctx.base}/sitemap.xml")
    return "\n".join(lines) + "\n"


def _sitemap(ctx: SeoContext) -> str:
    urls = [ctx.base + "/"] + [ctx.product_url(p) for p in ctx.products]
    body = "\n".join(f"  <url><loc>{_attr(u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )


def _llms(ctx: SeoContext) -> str:
    lines = [f"# {ctx.brand}", ""]
    if ctx.seo_description:
        lines += [ctx.seo_description, ""]
    lines.append("## کالاها")
    for p in ctx.products:
        price = ctx.money(p) if p.in_stock else "ناموجود"
        lines.append(f"- [{p.title}]({ctx.product_url(p)}) — {price}")
    if ctx.phone:
        lines += ["", f"تماس: {ctx.phone}"]
    lines += ["", "قدرت‌گرفته از حسابداریِ کوبیتا."]
    return "\n".join(lines) + "\n"


def extra_files(ctx: SeoContext) -> dict[str, str]:
    """فایل‌های اضافیِ سئو که کنارِ قالب در ZIP نوشته می‌شوند."""
    files: dict[str, str] = {"robots.txt": _robots(ctx), "llms.txt": _llms(ctx)}
    if ctx.base:  # sitemap فقط با آدرسِ مطلق معنی دارد
        files["sitemap.xml"] = _sitemap(ctx)
    for p in ctx.products:
        files[f"p/{p.slug}/index.html"] = _product_page(ctx, p)
    return files

/*
 * دموی زنده‌ی قالبِ فروشگاهِ کوبیتا — بدونِ هیچ بک‌اند.
 * این فایل جای assets/config.js می‌نشیند و کلِ داده را از حافظه سِرو می‌کند
 * (api.js وقتی demo:true ببیند، از window.SHOP_DEMO می‌خواند).
 */
window.SHOP = { demo: true, slug: 'demo' }
;(function () {
  // تصویرِ محصول به‌صورتِ SVGِ درون‌خطی (data-URI) تا دمو کاملاً خوداتکا و بدونِ میزبانِ عکس باشد.
  const svg = (title, c1, c2) =>
    'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600">' +
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0" stop-color="' + c1 + '"/><stop offset="1" stop-color="' + c2 + '"/>' +
        '</linearGradient></defs><rect width="600" height="600" fill="url(#g)"/>' +
        '<text x="300" y="315" font-family="Vazirmatn,Tahoma,sans-serif" font-size="40" fill="#fff" ' +
        'text-anchor="middle" font-weight="bold">' + title + '</text></svg>'
    )
  const P = (slug, title, price, category, badge, description, c1, c2) => ({
    id: slug, slug, title, category, price,
    images: [svg(title, c1, c2)], badge: badge || '', description: description || '',
    stock: 25, out_of_stock: false,
  })

  window.SHOP_DEMO = {
    info: {
      theme_id: 'general',
      theme_config: { brand_name: 'فروشگاهِ نمونه', primary: '#6d28d9', currency: 'toman' },
      seo_title: 'فروشگاهِ نمونه — قالبِ آماده‌ی کوبیتا',
      seo_description: 'این یک نمایشِ زنده از قالبِ فروشگاهِ کوبیتاست؛ همه‌ی کالاها و قیمت‌ها نمونه‌اند و از برنامه‌ی حسابداری خوانده می‌شوند.',
      contact_block: { phone: '۰۲۱–۱۲۳۴۵۶۷۸' },
      has_online_payment: false,
    },
    categories: [],
    catalog: [
      P('headphone', 'هدفونِ بی‌سیم', 2450000, 'صوتی', 'پرفروش', 'هدفونِ بلوتوثی با حذفِ نویز و ۳۰ ساعت شارژدهی.', '#7c3aed', '#4f46e5'),
      P('smartwatch', 'ساعتِ هوشمند', 3890000, 'دیجیتال', 'جدید', 'نمایشگرِ AMOLED، سنجشِ ضربان و اکسیژنِ خون، مقاوم در برابرِ آب.', '#2563eb', '#0ea5e9'),
      P('sneaker', 'کفشِ ورزشی', 1650000, 'پوشاک', '', 'سبک و تنفس‌پذیر، مناسبِ دویدن و پیاده‌رویِ روزانه.', '#059669', '#10b981'),
      P('perfume', 'عطرِ مردانه', 1290000, 'زیبایی', 'تخفیف', 'رایحه‌ی چوبی–مرکباتی با ماندگاریِ بالا؛ حجمِ ۱۰۰ میل.', '#db2777', '#f43f5e'),
      P('backpack', 'کوله‌پشتیِ لپ‌تاپ', 980000, 'پوشاک', '', 'ضدِآب با جایگاهِ مخصوصِ لپ‌تاپِ ۱۵ اینچ و پورتِ USB.', '#ea580c', '#f59e0b'),
      P('lamp', 'لامپِ هوشمند', 540000, 'دیجیتال', '', 'کنترل با اپلیکیشن، ۱۶ میلیون رنگ، سازگار با دستیارِ صوتی.', '#7c3aed', '#a855f7'),
      P('speaker', 'اسپیکرِ بلوتوثی', 1750000, 'صوتی', 'پرفروش', 'صدای فراگیر، باتریِ ۱۲ ساعته و بدنه‌ی ضدِآب.', '#0891b2', '#22d3ee'),
      P('mug', 'ماگِ حرارتی', 320000, 'خانه', '', 'نگهدارنده‌ی دمای نوشیدنی تا ۶ ساعت؛ استیلِ ضدِزنگ.', '#4b5563', '#6b7280'),
    ],
  }
})()

import { ENTERPRISE_FAQS } from '../content/enterprise'
import { FEATURES, type FeaturePage } from '../content/features'
import { HOME_FAQS } from '../content/home'
import { DOWNLOAD_FAQS } from '../content/download'
import { ENTERPRISE_DOWNLOAD_URL } from '../content/links'
import { ORGANIZATION_LD, SITE_URL, faqLd, type PageMeta } from './meta'

/**
 * فرادادهٔ همه‌ی صفحه‌ها. ترتیب همان ترتیبِ نقشهٔ سایت است.
 * صفحه‌ی تازه یعنی یک ردیف این‌جا + یک `<Route>` در `routes.tsx`؛ `prerender.mjs` هر دو را می‌سنجد.
 */

export const HOME_META: PageMeta = {
  path: '/',
  title: 'نرم‌افزار حسابداری کوبیتا | ابری، آفلاین و نسخه سازمانی رایگان',
  description:
    'کوبیتا نرم‌افزار حسابداری فارسی برای کسب‌وکارهای ایرانی است: فاکتور فروش و خرید، انبارداری، حسابداری دوطرفه، چک و بانک و حقوق و دستمزد؛ روی وب، ویندوز و اندروید، و نسخه سازمانی رایگان تا ۳ کاربر.',
  priority: 1,
  changefreq: 'weekly',
  jsonLd: [
    ORGANIZATION_LD,
    { '@type': 'WebSite', '@id': `${SITE_URL}/#site`, name: 'کوبیتا', url: `${SITE_URL}/`, inLanguage: 'fa-IR', publisher: { '@id': `${SITE_URL}/#org` } },
    {
      '@type': 'SoftwareApplication',
      name: 'کوبیتا',
      applicationCategory: 'BusinessApplication',
      applicationSubCategory: 'Accounting',
      operatingSystem: 'Windows 10, Windows 11, Android, Web',
      url: `${SITE_URL}/`,
      inLanguage: 'fa-IR',
      description:
        'نرم‌افزار حسابداری ابری و آفلاین برای کسب‌وکارهای ایرانی — فاکتور فروش و خرید، انبارداری، حسابداری دوطرفه، چک و بانک، حقوق و دستمزد.',
      publisher: { '@id': `${SITE_URL}/#org` },
    },
    faqLd(HOME_FAQS),
  ],
}

export const ENTERPRISE_META: PageMeta = {
  path: '/enterprise',
  title: 'کوبیتا سازمانی | نرم‌افزار حسابداری تحت شبکه رایگان',
  description:
    'نرم‌افزار حسابداری تحت شبکه رایگان برای شرکت‌ها: سرور در خود شرکت، حسابدارها روی شبکه داخلی، داده درون‌سازمانی. رایگان و همیشگی تا ۳ کاربر با یک ثبت‌نام ساده؛ دانلود برای ویندوز ۱۰ و ۱۱.',
  priority: 0.9,
  changefreq: 'monthly',
  breadcrumb: [{ name: 'کوبیتا سازمانی', path: '/enterprise' }],
  jsonLd: [
    {
      '@type': 'SoftwareApplication',
      name: 'کوبیتا سازمانی',
      alternateName: 'Cubita Enterprise',
      applicationCategory: 'BusinessApplication',
      applicationSubCategory: 'Accounting',
      operatingSystem: 'Windows 10, Windows 11',
      softwareRequirements: 'Windows 10 or 11, 64-bit',
      downloadUrl: ENTERPRISE_DOWNLOAD_URL,
      url: `${SITE_URL}/enterprise`,
      inLanguage: 'fa-IR',
      offers: { '@type': 'Offer', price: '0', priceCurrency: 'IRR', description: 'رایگان تا ۳ کاربر' },
      publisher: { '@id': `${SITE_URL}/#org` },
    },
    faqLd(ENTERPRISE_FAQS),
  ],
}

export const DOWNLOAD_META: PageMeta = {
  path: '/download',
  title: 'دانلود نرم‌افزار حسابداری کوبیتا | ویندوز، اندروید و نسخه سازمانی',
  description:
    'دانلود نرم‌افزار حسابداری کوبیتا: نسخه سازمانی رایگان تحت شبکه، نسخه ویندوز با کار آفلاین، اپ اندروید و نسخه وب بدون نصب. راهنمای انتخاب نسخه و نصب.',
  priority: 0.9,
  changefreq: 'monthly',
  breadcrumb: [{ name: 'دانلود', path: '/download' }],
  jsonLd: [faqLd(DOWNLOAD_FAQS)],
}

export const FEATURES_META: PageMeta = {
  path: '/features',
  title: 'امکانات نرم‌افزار حسابداری کوبیتا',
  description:
    'امکانات کوبیتا: حسابداری دوطرفه، فاکتور فروش، انبارداری، چک و بانک، حقوق و دستمزد، صندوق فروشگاهی و اتصال به سامانه مودیان — همه یکپارچه و با سند خودکار.',
  priority: 0.8,
  changefreq: 'monthly',
  breadcrumb: [{ name: 'امکانات', path: '/features' }],
}

export const featureMeta = (f: FeaturePage): PageMeta => ({
  path: `/features/${f.slug}`,
  title: f.title,
  description: f.description,
  priority: 0.7,
  changefreq: 'monthly',
  breadcrumb: [
    { name: 'امکانات', path: '/features' },
    { name: f.name, path: `/features/${f.slug}` },
  ],
  jsonLd: [faqLd(f.faqs)],
})

export const TERMS_META: PageMeta = {
  path: '/terms',
  title: 'شرایط استفاده از خدمات | کوبیتا',
  description:
    'شرایط استفاده از نرم‌افزار حسابداری کوبیتا: توصیف خدمات، حساب کاربری، پلن‌ها و پرداخت، مالکیت داده‌های شما، محدودیت مسئولیت و تعلیق یا لغو.',
  priority: 0.3,
  changefreq: 'yearly',
}

export const PRIVACY_META: PageMeta = {
  path: '/privacy',
  title: 'حریم خصوصی | کوبیتا',
  description:
    'حریم خصوصی در کوبیتا: چه اطلاعاتی جمع‌آوری می‌شود، داده‌های مالی کسب‌وکار شما، پرداخت، آنالیتیکس و کوکی، اپ اندروید، اشخاص ثالث و حذف داده‌ها.',
  priority: 0.3,
  changefreq: 'yearly',
}

export const CHECKOUT_META: PageMeta = {
  path: '/checkout-result',
  title: 'نتیجه پرداخت | کوبیتا',
  description: 'نتیجه‌ی پرداخت در کوبیتا.',
  noindex: true,
}

//: نشانیِ قدیمیِ صفحه‌ی اصلی؛ همان صفحه را نشان می‌دهد ولی canonicalش صفحه‌ی اصلی است.
export const CONCEPT_META: PageMeta = { ...HOME_META, path: '/concept', canonical: '/', noindex: true, jsonLd: [] }

export const NOT_FOUND_META: PageMeta = {
  path: '/404',
  title: 'صفحه پیدا نشد | کوبیتا',
  description: 'صفحه‌ای که دنبالش بودید پیدا نشد.',
  noindex: true,
}

export const FEATURE_METAS = FEATURES.map(featureMeta)

export const ALL_PAGES: PageMeta[] = [
  HOME_META,
  ENTERPRISE_META,
  DOWNLOAD_META,
  FEATURES_META,
  ...FEATURE_METAS,
  TERMS_META,
  PRIVACY_META,
  CHECKOUT_META,
  CONCEPT_META,
]

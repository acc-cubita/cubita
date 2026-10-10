import { useEffect, useState } from 'react'
import { CheckCircle2, LoaderCircle, XCircle } from 'lucide-react'
import { SiteFooter, SiteHeader } from '../concept/SiteChrome'
import { applyMeta } from '../seo/meta'
import { CHECKOUT_META } from '../seo/pages'
import '../concept/concept.css'

/**
 * نتیجه‌ی پرداخت. وضعیت از query می‌آید که پیش‌رندر نمی‌بیندش، پس تا اجرای کد در مرورگر حالتِ
 * «در حال بررسی» نشان داده می‌شود — خواندنِ `window` هنگامِ رندر پیش‌رندر را می‌شکست و نتیجه‌ی
 * پیش‌رندرشده (همیشه «ناموفق») با مرورگر نمی‌خواند. صفحه `noindex` است (`CHECKOUT_META`).
 */
export function CheckoutResultPage() {
  const [success, setSuccess] = useState<boolean | null>(null)

  useEffect(() => {
    setSuccess(new URLSearchParams(window.location.search).get('status') === 'success')
  }, [])

  useEffect(() => {
    applyMeta({ ...CHECKOUT_META, title: success ? 'پرداخت موفق | کوبیتا' : success === false ? 'پرداخت ناموفق | کوبیتا' : CHECKOUT_META.title })
  }, [success])

  return (
    <div className="cc-root" dir="rtl">
      <SiteHeader />
      <main className="cc-result">
        <div className="cc-result-card">
          {success === null ? (
            <>
              <div className="cc-result-icon">
                <LoaderCircle size={32} />
              </div>
              <h1 className="cc-result-title">در حال بررسیِ نتیجه‌ی پرداخت…</h1>
            </>
          ) : success ? (
            <>
              <div className="cc-result-icon is-success">
                <CheckCircle2 size={32} />
              </div>
              <h1 className="cc-result-title">پرداخت با موفقیت انجام شد</h1>
              <p>
                کسب‌وکار اختصاصی‌تان همین الان ساخته شد. لینک تعیین رمز عبور به ایمیلی که وارد کردید ارسال شده —
                آن را باز کنید تا وارد نسخه‌ی خودتان شوید.
              </p>
            </>
          ) : (
            <>
              <div className="cc-result-icon is-failed">
                <XCircle size={32} />
              </div>
              <h1 className="cc-result-title">پرداخت ناموفق بود</h1>
              <p>تراکنش تکمیل نشد یا لغو شد. مبلغی از حساب شما کسر نشده است؛ می‌توانید دوباره تلاش کنید.</p>
            </>
          )}
          <a href="/" className="cc-btn cc-btn-primary">
            بازگشت به صفحه‌ی اصلی
          </a>
        </div>
      </main>
      <SiteFooter />
    </div>
  )
}

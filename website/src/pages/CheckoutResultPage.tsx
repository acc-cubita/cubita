import { useEffect } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { LightStreakBackground } from '../components/LightStreakBackground'
import { Header } from '../components/Header'
import { Footer } from '../components/Footer'

export function CheckoutResultPage() {
  const params = new URLSearchParams(window.location.search)
  const success = params.get('status') === 'success'

  useEffect(() => {
    document.title = success ? 'پرداخت موفق | کوبیتا' : 'پرداخت ناموفق | کوبیتا'
    // صفحه‌ی تراکنشی است، نه محتوایی — نباید در نتایج جستجو ایندکس شود.
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex'
    document.head.appendChild(meta)
    return () => {
      document.head.removeChild(meta)
    }
  }, [success])

  return (
    <>
      <LightStreakBackground />
      <Header />
      <div className="result-page">
        <div className="result-card">
          {success ? (
            <>
              <div className="result-icon success">
                <CheckCircle2 size={32} />
              </div>
              <h2>پرداخت با موفقیت انجام شد</h2>
              <p>
                کسب‌وکار اختصاصی‌تان همین الان ساخته شد. لینک تعیین رمز عبور به ایمیلی که وارد کردید ارسال شده —
                آن را باز کنید تا وارد نسخه‌ی خودتان شوید.
              </p>
            </>
          ) : (
            <>
              <div className="result-icon failed">
                <XCircle size={32} />
              </div>
              <h2>پرداخت ناموفق بود</h2>
              <p>تراکنش تکمیل نشد یا لغو شد. مبلغی از حساب شما کسر نشده است؛ می‌توانید دوباره تلاش کنید.</p>
            </>
          )}
          <a href="/" className="btn btn-primary">
            بازگشت به صفحه‌ی اصلی
          </a>
        </div>
      </div>
      <Footer />
    </>
  )
}
